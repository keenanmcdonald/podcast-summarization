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


class Occurrence(BaseModel):
    start: str
    end: str


class Claim(BaseModel):
    text: str
    occurrences: list[Occurrence] = Field(min_length=1)


class VerifierInput(BaseModel):
    claim: Claim
    transcript: TranscriptInput
