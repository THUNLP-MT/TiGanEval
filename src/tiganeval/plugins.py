from __future__ import annotations

import hashlib
import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any


class PluginError(RuntimeError):
    pass


def load_symbol(reference: str, base_dir: Path) -> Any:
    if ":" not in reference:
        raise PluginError(
            f"plugin reference must be 'module:symbol' or 'path.py:symbol': {reference}"
        )
    target, attribute = reference.rsplit(":", 1)
    if not target or not attribute:
        raise PluginError(f"invalid plugin reference: {reference}")

    looks_like_path = target.endswith(".py") or "/" in target or "\\" in target
    if looks_like_path:
        path = Path(target).expanduser()
        if not path.is_absolute():
            path = (base_dir / path).resolve()
        if not path.is_file():
            raise PluginError(f"plugin module file not found: {path}")
        package_parts = [path.stem]
        package_root = path.parent
        while (package_root / "__init__.py").is_file():
            package_parts.insert(0, package_root.name)
            package_root = package_root.parent
        if len(package_parts) > 1:
            module_name = ".".join(package_parts)
            root_text = str(package_root)
            if root_text not in sys.path:
                sys.path.insert(0, root_text)
        else:
            digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:12]
            module_name = f"tiganeval_external_{digest}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise PluginError(f"could not load plugin module: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        try:
            module = importlib.import_module(target)
        except ImportError as exc:
            raise PluginError(f"could not import plugin module {target!r}") from exc

    try:
        return getattr(module, attribute)
    except AttributeError as exc:
        raise PluginError(f"plugin {target!r} has no symbol {attribute!r}") from exc
