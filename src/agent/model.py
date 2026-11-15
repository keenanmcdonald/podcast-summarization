from pathlib import Path

from langchain_openai import ChatOpenAI

PROMPTS = Path(__file__).resolve().parent / "prompts"


def build_model(model: str, reasoning_effort: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        reasoning={"effort": reasoning_effort, "summary": "auto"},
        use_responses_api=True,
        timeout=30,
        max_retries=2,
    )


def system_prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
