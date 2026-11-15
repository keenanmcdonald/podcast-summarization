from pydantic import BaseModel, Field


class Occurrence(BaseModel):
    start: str
    end: str


class Claim(BaseModel):
    text: str
    occurrences: list[Occurrence] = Field(min_length=1)


class ClaimExtractorOutput(BaseModel):
    claims: list[Claim]
