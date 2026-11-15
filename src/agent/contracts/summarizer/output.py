from pydantic import BaseModel, Field


class Quote(BaseModel):
    text: str
    speaker: str
    timestamp: str


class SummarizerOutput(BaseModel):
    summary: str = Field(
        description="Approximately 200–300 words covering the episode's core themes, discussions, and outcomes or opinions."
    )
    takeaways: list[str] = Field(min_length=5, max_length=5)
    quotes: list[Quote]
    topics: list[str]
