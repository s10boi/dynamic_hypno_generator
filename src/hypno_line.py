from hashlib import sha256
from pathlib import Path
from typing import Self, final, override

from loguru import logger
from pedalboard.io import AudioFile


@final
class HypnoLine:
    """Represents a line of hypnotic text and its associated audio file.

    Attributes:
        text (str): The text of the line.
        filepath (Path): The file path to the audio file generated from this line.
        duration (float | None): The duration of the audio file in seconds, if known.
    """

    text: str
    filepath: Path
    duration: float | None

    def __init__(self, text: str, filepath: Path, duration: float | None = None) -> None:  # noqa: D107
        self.text = text
        self.filepath = filepath
        self.duration = duration

    @classmethod
    def from_text(cls, text: str, output_audio_dir: Path) -> Self:
        return cls(text=text, filepath=get_filepath_from_line(text, output_audio_dir))

    @override
    def __eq__(self, value: object) -> bool:
        if isinstance(value, HypnoLine):
            return self.text == value.text
        return False

    @override
    def __hash__(self) -> int:
        return hash(self.text)

    def set_duration(self) -> None:
        """Sets the duration of the audio file associated with this HypnoLine.

        Raises:
            FileNotFoundError: If the audio file does not exist.
        """
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
    return text.strip().rstrip(".").strip()


def get_filepath_from_line(text: str, output_audio_dir: Path) -> Path:
    """Generates a file path for the audio file corresponding to the given text."""
    hashed_text = sha256(text.encode("utf-8")).hexdigest()
    return output_audio_dir / f"{hashed_text}.wav"
