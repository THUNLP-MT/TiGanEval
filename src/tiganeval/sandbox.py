"Small, fail-closed process sandbox used by code-executing tasks."

from __future__ import annotations

import os
import platform
import shutil
import signal
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


class SandboxUnavailable(RuntimeError):
    "Raised when a restricted process cannot be started safely."


@dataclass(frozen=True, slots=True)
class SandboxPolicy:
    "The intentionally small policy required by benchmark diagnostics."

    private_roots: tuple[Path, ...] = ()
    readable_roots: tuple[Path, ...] = ()
    writable_roots: tuple[Path, ...] = ()


MACOS_BACKEND = "macos-seatbelt"
LINUX_BACKEND = "linux-bubblewrap"


_BUBBLEWRAP_TMPFS = "/tmp"


_SETUP_FAULT_PREFIXES = ("bwrap:",)


_BPF_LD = 0x00
_BPF_W = 0x00
_BPF_ABS = 0x20
_BPF_JMP = 0x05
_BPF_JA = 0x00
_BPF_JEQ = 0x10
_BPF_JSET = 0x40
_BPF_K = 0x00
_BPF_RET = 0x06

_LOAD_WORD = _BPF_LD | _BPF_W | _BPF_ABS
_JUMP_IF_EQUAL = _BPF_JMP | _BPF_JEQ | _BPF_K
_JUMP_IF_BITS_SET = _BPF_JMP | _BPF_JSET | _BPF_K
_JUMP_ALWAYS = _BPF_JMP | _BPF_JA | _BPF_K
_RETURN_CONSTANT = _BPF_RET | _BPF_K


_SECCOMP_RET_KILL_PROCESS = 0x80000000
_SECCOMP_RET_ERRNO = 0x00050000
_SECCOMP_RET_ALLOW = 0x7FFF0000


_EPERM = 1
_ENOSYS = 38


_SECCOMP_DATA_NR = 0
_SECCOMP_DATA_ARCH = 4
_SECCOMP_DATA_ARG0_LOW = 16


_AUDIT_ARCH_X86_64 = 0xC000003E
_AUDIT_ARCH_AARCH64 = 0xC00000B7


_X32_SYSCALL_BIT = 0x40000000


_X86_64_CLONE = 56
_X86_64_FORK = 57
_X86_64_VFORK = 58
_AARCH64_CLONE = 220
_CLONE3 = 435


_CLONE_THREAD = 0x00010000


_AT_X86_64_BLOCK = 3
_AT_AARCH64_BLOCK = 10
_AT_CLONE_FLAGS = 14
_AT_RETURN_EPERM = 16
_AT_RETURN_ENOSYS = 17
_AT_RETURN_ALLOW = 18
_AT_RETURN_KILL = 19
_SECCOMP_FILTER_LENGTH = 20


_FILTERED_MACHINES = frozenset({"x86_64", "amd64", "aarch64", "arm64"})


def _errno_action(errno: int) -> int:
    "SECCOMP_RET_ERRNO carrying one errno in SECCOMP_RET_DATA."

    return _SECCOMP_RET_ERRNO | errno


def _jump(here: int, target: int) -> int:
    "Displacement classic BPF wants: counted from the following instruction."

    displacement = target - here - 1
    if not 0 <= displacement <= 255:
        raise ValueError(f"unencodable BPF jump {here} -> {target}")
    return displacement


def _seccomp_filter_program() -> bytes:
    "Assemble the classic-BPF program that denies new processes."

    instructions: list[tuple[int, int, int, int]] = [
        (_LOAD_WORD, 0, 0, _SECCOMP_DATA_ARCH),
        (
            _JUMP_IF_EQUAL,
            _jump(1, _AT_X86_64_BLOCK),
            0,
            _AUDIT_ARCH_X86_64,
        ),
        (
            _JUMP_IF_EQUAL,
            _jump(2, _AT_AARCH64_BLOCK),
            _jump(2, _AT_RETURN_KILL),
            _AUDIT_ARCH_AARCH64,
        ),
        (_LOAD_WORD, 0, 0, _SECCOMP_DATA_NR),
        (_JUMP_IF_BITS_SET, _jump(4, _AT_RETURN_KILL), 0, _X32_SYSCALL_BIT),
        (_JUMP_IF_EQUAL, _jump(5, _AT_RETURN_EPERM), 0, _X86_64_FORK),
        (_JUMP_IF_EQUAL, _jump(6, _AT_RETURN_EPERM), 0, _X86_64_VFORK),
        (_JUMP_IF_EQUAL, _jump(7, _AT_CLONE_FLAGS), 0, _X86_64_CLONE),
        (_JUMP_IF_EQUAL, _jump(8, _AT_RETURN_ENOSYS), 0, _CLONE3),
        (_JUMP_ALWAYS, 0, 0, _jump(9, _AT_RETURN_ALLOW)),
        (_LOAD_WORD, 0, 0, _SECCOMP_DATA_NR),
        (_JUMP_IF_EQUAL, _jump(11, _AT_CLONE_FLAGS), 0, _AARCH64_CLONE),
        (_JUMP_IF_EQUAL, _jump(12, _AT_RETURN_ENOSYS), 0, _CLONE3),
        (_JUMP_ALWAYS, 0, 0, _jump(13, _AT_RETURN_ALLOW)),
        (_LOAD_WORD, 0, 0, _SECCOMP_DATA_ARG0_LOW),
        (_JUMP_IF_BITS_SET, _jump(15, _AT_RETURN_ALLOW), 0, _CLONE_THREAD),
        (_RETURN_CONSTANT, 0, 0, _errno_action(_EPERM)),
        (_RETURN_CONSTANT, 0, 0, _errno_action(_ENOSYS)),
        (_RETURN_CONSTANT, 0, 0, _SECCOMP_RET_ALLOW),
        (_RETURN_CONSTANT, 0, 0, _SECCOMP_RET_KILL_PROCESS),
    ]
    if len(instructions) != _SECCOMP_FILTER_LENGTH:
        raise ValueError("the seccomp filter layout and its labels disagree")

    return b"".join(
        struct.pack("HBBI", code, jt, jf, k) for code, jt, jf, k in instructions
    )


def _require_filtered_architecture() -> None:
    "Refuse a Linux host whose syscall table the filter does not describe."

    machine = platform.machine()
    if machine.lower() not in _FILTERED_MACHINES:
        raise SandboxUnavailable(
            "the Linux sandbox denies process creation with a seccomp filter "
            "written for the x86_64 and aarch64 syscall tables, and kills any "
            f"process that speaks another one; this host reports {machine!r}, "
            "so every sandboxed process would be killed before running a "
            "line. Run the benchmark on an x86_64 or aarch64 Linux host (a "
            "64-bit interpreter on a 64-bit kernel), or on macOS."
        )


def backend_name() -> str | None:
    if sys.platform == "darwin" and shutil.which("sandbox-exec"):
        return MACOS_BACKEND
    if sys.platform.startswith("linux") and shutil.which("bwrap"):
        return LINUX_BACKEND
    return None


def require_backend() -> str:
    backend = backend_name()
    if backend is None:
        raise SandboxUnavailable(
            "Install bubblewrap on Linux (apt install bubblewrap), or use macOS "
            "with sandbox-exec on PATH. Then run: tiganeval sandbox-check"
        )
    if backend == LINUX_BACKEND:
        _require_filtered_architecture()
    return backend


def _resolved_existing_roots(roots: Sequence[Path]) -> tuple[Path, ...]:
    "Resolve policy roots, drop duplicates, and drop what is not there."

    resolved = (Path(root).expanduser().resolve() for root in roots)
    return tuple(path for path in dict.fromkeys(resolved) if path.exists())


def _seatbelt_profile(policy: SandboxPolicy) -> str:
    rules = [
        "(version 1)",
        "(allow default)",
        "(deny network*)",
        "(deny process-fork)",
        "(deny file-write*)",
    ]
    for index, _ in enumerate(policy.private_roots):
        rules.append(f'(deny file-read* (subpath (param "PRIVATE_ROOT_{index}")))')
    for index, _ in enumerate(policy.readable_roots):
        rules.append(
            f'(allow file-read* (literal (param "READABLE_ROOT_{index}")) '
            f'(subpath (param "READABLE_ROOT_{index}")))'
        )
        rules.append(
            f'(allow file-read-metadata (literal (param "READABLE_PARENT_{index}")))'
        )
    for index, _ in enumerate(policy.writable_roots):
        rules.append(
            f'(allow file-write* (literal (param "WRITABLE_ROOT_{index}")) '
            f'(subpath (param "WRITABLE_ROOT_{index}")))'
        )
        rules.append(
            f'(allow file-read-metadata (literal (param "WRITABLE_PARENT_{index}")))'
        )
    return "\n".join(rules)


def _seatbelt_command(
    argv: Sequence[str], *, executable: str, policy: SandboxPolicy
) -> list[str]:
    "``sandbox-exec`` invocation carrying the policy as profile parameters."

    command = [executable]
    roots = tuple(Path(root).expanduser().resolve() for root in policy.private_roots)
    for index, root in enumerate(roots):
        command.extend(("-D", f"PRIVATE_ROOT_{index}={root}"))
    readable_roots = tuple(
        Path(root).expanduser().resolve() for root in policy.readable_roots
    )
    for index, root in enumerate(readable_roots):
        command.extend(("-D", f"READABLE_ROOT_{index}={root}"))
        command.extend(("-D", f"READABLE_PARENT_{index}={root.parent}"))
    writable_roots = tuple(
        Path(root).expanduser().resolve() for root in policy.writable_roots
    )
    for index, root in enumerate(writable_roots):
        command.extend(("-D", f"WRITABLE_ROOT_{index}={root}"))
        command.extend(("-D", f"WRITABLE_PARENT_{index}={root.parent}"))
    command.extend(("-p", _seatbelt_profile(policy), *map(str, argv)))
    return command


def _bubblewrap_command(
    argv: Sequence[str],
    *,
    executable: str,
    seccomp_fd: int,
    cwd: str | Path,
    policy: SandboxPolicy,
) -> list[str]:
    "``bwrap`` invocation carrying the policy as mount operations."

    command = [
        executable,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--seccomp",
        str(seccomp_fd),
        "--ro-bind",
        "/",
        "/",
        "--dev",
        "/dev",
        "--proc",
        "/proc",
        "--tmpfs",
        _BUBBLEWRAP_TMPFS,
    ]
    already_hidden = Path(_BUBBLEWRAP_TMPFS).resolve()
    for root in _resolved_existing_roots(policy.private_roots):
        if root == already_hidden:
            continue
        command.extend(("--tmpfs", str(root)))
    for root in _resolved_existing_roots(policy.readable_roots):
        command.extend(("--ro-bind", str(root), str(root)))
    for root in _resolved_existing_roots(policy.writable_roots):
        command.extend(("--bind", str(root), str(root)))
    command.extend(("--chdir", str(Path(cwd).resolve()), "--", *map(str, argv)))
    return command


def _run_process_group(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    input: str | None,
    timeout: float,
    pass_fds: Sequence[int] = (),
) -> subprocess.CompletedProcess[str]:
    "Run ``command`` as the leader of a new process group, and on a timeout     kill the whole group."

    process = subprocess.Popen(
        list(command),
        cwd=cwd,
        env=dict(env),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        pass_fds=tuple(pass_fds),
    )
    try:
        stdout, stderr = process.communicate(input=input, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _kill_group(process)
        stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(
            exc.cmd, exc.timeout, output=stdout, stderr=stderr
        ) from None
    except BaseException:
        _kill_group(process)
        raise
    return subprocess.CompletedProcess(
        list(command), process.returncode, stdout, stderr
    )


def _kill_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        process.kill()


def _run_seatbelt(
    argv: Sequence[str],
    *,
    cwd: str | Path,
    env: Mapping[str, str],
    input: str | None,
    timeout: float,
    policy: SandboxPolicy,
) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("sandbox-exec")
    if executable is None:
        raise SandboxUnavailable("macOS sandbox-exec is not available")

    completed = _run_process_group(
        _seatbelt_command(argv, executable=executable, policy=policy),
        cwd=Path(cwd),
        env=env,
        input=input,
        timeout=timeout,
    )

    if completed.returncode in {69, 71} or "sandbox_apply:" in completed.stderr:
        detail = completed.stderr.strip() or f"exit code {completed.returncode}"
        raise SandboxUnavailable(f"could not apply process sandbox: {detail}")
    return completed


def _run_bubblewrap_with(
    argv: Sequence[str],
    *,
    executable: str,
    cwd: str | Path,
    env: Mapping[str, str],
    input: str | None,
    timeout: float,
    policy: SandboxPolicy,
) -> subprocess.CompletedProcess[str]:
    environment = dict(env)
    environment["HOME"] = _BUBBLEWRAP_TMPFS

    program = _seccomp_filter_program()
    read_fd, write_fd = os.pipe()
    try:
        try:
            written = os.write(write_fd, program)
        finally:
            os.close(write_fd)
        if written != len(program):
            raise SandboxUnavailable(
                "could not hand the seccomp filter to bubblewrap: wrote "
                f"{written} of {len(program)} bytes"
            )
        completed = _run_process_group(
            _bubblewrap_command(
                argv,
                executable=executable,
                seccomp_fd=read_fd,
                cwd=cwd,
                policy=policy,
            ),
            cwd=Path(cwd),
            env=environment,
            input=input,
            timeout=timeout,
            pass_fds=(read_fd,),
        )
    finally:
        os.close(read_fd)

    if completed.returncode != 0 and completed.stderr.startswith(_SETUP_FAULT_PREFIXES):
        raise SandboxUnavailable(
            f"could not apply process sandbox: {completed.stderr.strip()}"
        )
    return completed


def _run_bubblewrap(
    argv: Sequence[str],
    *,
    cwd: str | Path,
    env: Mapping[str, str],
    input: str | None,
    timeout: float,
    policy: SandboxPolicy,
) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("bwrap")
    if executable is None:
        raise SandboxUnavailable("Linux bubblewrap (bwrap) is not available")
    return _run_bubblewrap_with(
        argv,
        executable=executable,
        cwd=cwd,
        env=env,
        input=input,
        timeout=timeout,
        policy=policy,
    )


_BACKEND_RUNNERS = {
    MACOS_BACKEND: _run_seatbelt,
    LINUX_BACKEND: _run_bubblewrap,
}


def run_sandboxed(
    argv: Sequence[str],
    *,
    cwd: str | Path,
    env: Mapping[str, str],
    input: str | None = None,
    timeout: float,
    policy: SandboxPolicy,
) -> subprocess.CompletedProcess[str]:
    "Run one argv under the selected sandbox; never retry unsandboxed."

    if not argv:
        raise ValueError("sandbox argv must not be empty")
    backend = require_backend()
    runner = _BACKEND_RUNNERS.get(backend)
    if runner is None:
        raise SandboxUnavailable(f"unknown process sandbox backend: {backend}")
    return runner(argv, cwd=cwd, env=env, input=input, timeout=timeout, policy=policy)


def deterministic_environment() -> dict[str, str]:
    "Minimal environment shared by all sandboxed Python processes."

    return {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LC_ALL": "C",
        "LANG": "C",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    }
