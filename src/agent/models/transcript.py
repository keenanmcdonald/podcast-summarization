import json
import re
from typing import Self

from pydantic import BaseModel, Field, model_validator

TURN_PATTERN = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\] ([^:]+): (.*)$")
MAX_TRANSCRIPT_CHARS = 80_000


def timestamp_seconds(timestamp: str) -> int:
    parts = timestamp.split(":")
    if len(parts) not in (2, 3) or any(not part.isdigit() or len(part) != 2 for part in parts):
        raise ValueError(f"Invalid timestamp: {timestamp}")
    hours, minutes, seconds = (0, *map(int, parts)) if len(parts) == 2 else map(int, parts)
    if (len(parts) == 3 and minutes >= 60) or seconds >= 60:
        raise ValueError(f"Invalid timestamp: {timestamp}")
    return hours * 3600 + minutes * 60 + seconds


class TranscriptTurn(BaseModel):
    timestamp: str
    speaker: str
    text: str
    section: str | None = None


class Transcript(BaseModel):
    turns: list[TranscriptTurn] = Field(min_length=1)
    episode_id: str | None = None
    title: str | None = None
    host: str | None = None
    guests: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_turns(self) -> Self:
        times = [timestamp_seconds(turn.timestamp) for turn in self.turns]
        if times != sorted(set(times)):
            raise ValueError("Turn timestamps must be strictly increasing and unique")
        if any(not turn.speaker.strip() or not turn.text.strip() for turn in self.turns):
            raise ValueError("Turns require a speaker and text")
        return self

    def resolve_span(self, start: str, end: str) -> list[TranscriptTurn]:
        start_time, end_time = timestamp_seconds(start), timestamp_seconds(end)
        times = {timestamp_seconds(turn.timestamp) for turn in self.turns}
        if start_time not in times or end_time not in times or start_time > end_time:
            raise ValueError(f"Unknown or reversed transcript span: {start}–{end}")
        return [turn for turn in self.turns if start_time <= timestamp_seconds(turn.timestamp) <= end_time]

    @classmethod
    def parse(cls, contents: str, file_format: str) -> Self:
        if len(contents) > MAX_TRANSCRIPT_CHARS:
            raise ValueError("Transcript exceeds model input limit")
        if file_format == ".json":
            data = json.loads(contents)
            return cls(
                turns=[TranscriptTurn.model_validate(turn) for turn in data["transcript"]],
                episode_id=data.get("episode_id"),
                title=data.get("title"),
                host=data.get("host"),
                guests=data.get("guests", []),
            )
        if file_format == ".txt":
            turns = []
            for line in contents.splitlines():
                match = TURN_PATTERN.fullmatch(line)
                if match:
                    turns.append(TranscriptTurn(timestamp=match[1], speaker=match[2], text=match[3]))
                elif line.strip():
                    if not turns:
                        raise ValueError("Text transcript must start with a timestamped turn")
                    turns[-1].text += " " + line.strip()
            return cls(turns=turns)
        raise ValueError(f"Unsupported transcript format: {file_format}")
