"""SDK test fixtures and mock generators."""

from pathlib import Path


class MockJournalWriter:
    """Simulates Elite Dangerous journal log generation for integration tests."""

    def __init__(self, target_directory: Path | str) -> None:
        self.target_directory = Path(target_directory)

    def write_entry(self, filename: str, line: str) -> Path:
        """Write a single event line to the mock journal file."""
        self.target_directory.mkdir(parents=True, exist_ok=True)
        file_path = self.target_directory / filename
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"{line}\n")
        return file_path
