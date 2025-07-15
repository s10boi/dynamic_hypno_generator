import argparse
from pathlib import Path
from typing import Self

from loguru import logger
from pydantic import BaseModel, Field, ValidationError


class Config(BaseModel):
    """Configuration for controlling various settings for hypno generation."""

    text_filepath: Path = Field(
        default=Path("./import/text/lines.txt"),
        description="Path to the text file containing lines.",
    )
    line_dir: Path = Field(
        default=Path("./import/audio/lines"),
        description="Directory where audio files for lines will be stored.",
    )
    play_background_audio: bool = Field(
        default=True,
        description="Whether to play background audio.",
    )
    background_chunk_size: int = Field(
        default=8000,
        gt=0,
        description="Number of frames to read at a time for background audio.",
    )
    initial_line_delay: float = Field(
        default=3.0,
        ge=0.0,
        description="Initial delay in seconds before starting to play lines.",
    )
    initial_pitch_shift: float = Field(
        default=-1.44,
        description="Initial pitch shift for the audio lines.",
    )
    max_echoes: int = Field(
        default=2,
        ge=0,
        description="Maximum number of echoes to play for each line.",
    )
    echo_delay: float = Field(
        default=1.0,
        ge=0.0,
        description="Delay in seconds between echoes.",
    )
    line_chunk_size: int = Field(
        default=96_000,
        gt=0,
        description="Number of frames to read at a time for line audio.",
    )
    play_mantra: bool = Field(
        default=True,
        description="Whether to play the mantra audio.",
    )
    mantra_start_delay: float = Field(
        default=10.0,
        ge=0.0,
        description="Delay in seconds after the lines start playing, before starting to play the mantra audio.",
    )

    @classmethod
    def from_args(cls, *, json_filepath: Path | None, text_filepath: Path | None) -> Self:
        """Create a Config instance from a provided JSON file path and text file path.

        If settings are unavailable in the JSON file, default values will be used.

        Args:
            json_filepath (Path | None): Path to the JSON configuration file.
            text_filepath (Path | None): Path to the text file containing lines.

        Returns:
            Config: An instance of the Config class with settings loaded from the JSON file, using the provided text
            file path if available.
        """
        if json_filepath and json_filepath.exists():
            try:
                logger.debug(f"Loading configuration from {json_filepath}")
                config = cls.model_validate_json(json_filepath.read_text())
            except ValidationError as e:
                print(f"Validation error reading {json_filepath}: {e}")
                config = cls()
        else:
            config = cls()

        if text_filepath and text_filepath.exists():
            config.text_filepath = text_filepath

        return config


def read_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hypno Audio Generation and Playback")
    _ = parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=None,
        help="Path to a JSON file containing configuration settings.",
    )
    _ = parser.add_argument(
        "-t",
        "--text_filepath",
        type=Path,
        default=None,
        help="Path to the text file containing lines to be converted to audio.",
    )
    return parser.parse_args()
