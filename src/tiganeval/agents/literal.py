from tiganeval.prompts import load_prompt

from .react import ReActAgent


def build_literal_system_prompt(
    *, submissions: int, turns: int, tool_calls: int
) -> str:
    return load_prompt(
        "literal", submissions=submissions, turns=turns, tool_calls=tool_calls
    )


class LiteralAgent(ReActAgent):
    build_system_prompt = staticmethod(build_literal_system_prompt)

    def reset(self, system_prompt, tools):
        super().reset(system_prompt, tuple(t for t in tools if t.name != "ask_user"))
