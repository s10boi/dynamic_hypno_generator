from hashlib import sha256
from pathlib import Path
from typing import final

from loguru import logger
from pedalboard.io import AudioFile


@final
class HypnoLine:
    text: str
    filepath: Path
    duration: float | None

    def __init__(self, text: str, output_audio_dir: Path) -> None:  # noqa: D107
        self.text = text
        self.filepath = get_filepath_from_line(text, output_audio_dir)
        self.duration = None

    def set_duration(self) -> None:
        if self.filepath.exists():
            logger.debug(f"Setting duration for audio file: {self.text}")
            with AudioFile(str(self.filepath), "r") as audio_file:  # pyright: ignore[reportGeneralTypeIssues, reportArgumentType, reportUnknownVariableType]
                self.duration = audio_file.duration + 1
                logger.debug(f"Duration set to {self.duration} seconds for {self.text}")
        else:
            msg = f"Audio file {self.filepath} does not exist."
            raise FileNotFoundError(msg)


def clean_line(text: str) -> str:
    """Standardises the line text to avoid duplicates."""
    return text.lower().strip().rstrip(".").strip()


def get_filepath_from_line(text: str, output_audio_dir: Path) -> Path:
    """Generates a file path for the audio file corresponding to the given text."""
    hashed_text = sha256(text.encode("utf-8")).hexdigest()
    return output_audio_dir / f"{hashed_text}.wav"
