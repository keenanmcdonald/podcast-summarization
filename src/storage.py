import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from src.contracts.report import Report

MOCK_ROOT = Path(__file__).resolve().parents[1] / "mock"
MAX_TRANSCRIPT_BYTES = 1_000_000


def resolve_transcript(key: str) -> Path:
    if Path(key).is_absolute():
        raise ValueError("Transcript path must be relative to mock/")
    path = (MOCK_ROOT / key).resolve()
    if not path.is_relative_to(MOCK_ROOT.resolve()):
        raise ValueError("Transcript path must remain within mock/")
    return path


def read_transcript(path: Path) -> str:
    if path.suffix.lower() not in {".txt", ".json"}:
        raise ValueError("Supported transcript formats are .txt and .json")
    with path.open("rb") as source:
        data = source.read(MAX_TRANSCRIPT_BYTES + 1)
    if len(data) > MAX_TRANSCRIPT_BYTES:
        raise ValueError("Transcript file exceeds size limit")
    return data.decode("utf-8")


def write_report(transcript_path: Path, report: Report) -> Path:
    target = transcript_path.with_name("report.json")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent, prefix=".report-", delete=False
        ) as output:
            temporary = Path(output.name)
            json.dump(asdict(report), output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target
