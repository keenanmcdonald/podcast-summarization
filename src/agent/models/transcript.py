from pydantic import BaseModel, Field


class TranscriptTurn(BaseModel):
    timestamp: str
    speaker: str
    text: str
    section: str | None = None


class Transcript(BaseModel):
    turns: list[TranscriptTurn]
    episode_id: str | None = None
    title: str | None = None
    host: str | None = None
    guests: list[str] = Field(default_factory=list)

    @classmethod
    def parse(cls, contents: str, file_format: str) -> "Transcript":
        raise NotImplementedError("Transcript parsers await review")
