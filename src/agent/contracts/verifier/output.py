from typing import Literal

from pydantic import BaseModel


class VerifierOutput(BaseModel):
    verdict: Literal["verified_true", "possibly_outdated_inaccurate", "unverifiable"]
    rationale: str
    source_urls: list[str]
