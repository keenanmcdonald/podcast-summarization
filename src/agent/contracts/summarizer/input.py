from pydantic import BaseModel, Field


class TranscriptTurn(BaseModel):
    timestamp: str
    speaker: str
    text: str


class TranscriptInput(BaseModel):
    turns: list[TranscriptTurn]
    title: str | None = None
    host: str | None = None
    guests: list[str] = Field(default_factory=list)


class SummarizerInput(BaseModel):
    transcript: TranscriptInput


class SummarizerFeedback(BaseModel):
    errors: list[str]
