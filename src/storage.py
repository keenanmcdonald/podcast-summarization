from pathlib import Path

MOCK_ROOT = Path(__file__).resolve().parents[1] / "mock"


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
    return path.read_text(encoding="utf-8")
