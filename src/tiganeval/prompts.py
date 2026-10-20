from pathlib import Path


def load_prompt(name: str, **values) -> str:
    text = (Path(__file__).with_name("prompts") / f"{name}.txt").read_text().strip()
    return text.format(**values) if values else text


def build_agent_system_prompt(*, submissions: int, turns: int, tool_calls: int) -> str:
    return load_prompt(
        "agent", submissions=submissions, turns=turns, tool_calls=tool_calls
    )
