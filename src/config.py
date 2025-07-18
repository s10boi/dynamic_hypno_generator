import argparse
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Self, cast

from loguru import logger
from pydantic import BaseModel, Field, ValidationError, ValidationInfo, field_validator

DEFAULT_BACKGROUND_AUDIO = "tone"
DEFAULT_LINE_CHOOSER = "sequential"
DEFAULT_TEXT_PATH = Path("./lines.txt")


class Config(BaseModel):
    """Configuration for controlling various settings for hypno generation."""

    background_audio: str | None = Field(
        default=DEFAULT_BACKGROUND_AUDIO,
        description="Type of background audio to play.",
    )
    line_chooser: str = Field(
        default=DEFAULT_LINE_CHOOSER,
        description="Function to choose hypno lines.",
    )
    initial_line_delay: float = Field(
        default=15.0,
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
        le=3,
        description="Maximum number of echoes to play for each line.",
    )
    echo_delay: float = Field(
        default=1.5,
        ge=0.0,
        description="Delay in seconds between echoes.",
    )
    mantra_filepath: Path | None = Field(
        default=None,
        description="Path to the mantra audio file. If None, no mantra will be played.",
    )
    mantra_start_delay: float = Field(
        default=45.0,
        ge=0.0,
        description="Delay in seconds after the lines start playing, before starting to play the mantra audio.",
    )

    @field_validator("background_audio", mode="after")
    @classmethod
    def validate_background_audio(cls, value: str | None, info: ValidationInfo) -> str | None:
        """Validate the background audio type against available options.

        Raises:
            ValueError: If the provided background audio type is not valid.
        """
        if not value or value.lower().strip() == "none":
            return None

        if isinstance(info.context, dict):
            available_backgrounds = cast("Iterable[str]", info.context.get("available_backgrounds", []))
            if value not in available_backgrounds:
                msg = f"Invalid background audio type: {value}. Available options: {', '.join(available_backgrounds)}"
                raise ValueError(msg)
            return value
        msg = f"Invalid context for background audio validation: {info.context}"
        raise ValueError(msg)

    @field_validator("line_chooser", mode="after")
    @classmethod
    def validate_line_chooser_fn(cls, value: str, info: ValidationInfo) -> str:
        """Validate the line chooser function against available options.

        Raises:
            ValueError: If the provided line chooser function is not valid.
        """
        if isinstance(info.context, dict):
            available_line_choosers = cast("Iterable[str]", info.context.get("available_line_choosers", []))
            if value not in available_line_choosers:
                msg = f"Invalid line chooser function: {value}. Available options: {', '.join(available_line_choosers)}"
                raise ValueError(msg)
            return value
        msg = f"Invalid context for line chooser function validation: {info.context}"
        raise ValueError(msg)

    @field_validator("mantra_filepath", mode="before")
    @classmethod
    def validate_mantra_filepath(cls, value: Any) -> Any:  # noqa: ANN401
        if isinstance(value, str):
            value = value.strip()

            if value.lower() == "none":
                return None

        return value

    @classmethod
    def from_args(
        cls,
        *,
        json_filepath: Path,
        available_backgrounds: Iterable[str],
        available_line_choosers: Iterable[str],
    ) -> Self:
        """Create a Config instance from a provided JSON file path and text file path.

        If settings are unavailable in the JSON file, default values will be used.

        Args:
            json_filepath (Path): Path to the JSON configuration file.
            available_backgrounds (Iterable[str]): Available background audio types for validation.
            available_line_choosers (Iterable[str]): Available line chooser functions for validation.

        Returns:
            Config: An instance of the Config class with settings loaded from the JSON file.

        Raises:
            FileNotFoundError: If the JSON configuration file does not exist.
            ValidationError: If the JSON file does not conform to the expected schema.
        """
        if json_filepath.exists():
            try:
                logger.debug(f"Loading configuration from {json_filepath}")
                config = cls.model_validate_json(
                    json_filepath.read_text(encoding="utf-8"),
                    context={
                        "available_backgrounds": available_backgrounds,
                        "available_line_choosers": available_line_choosers,
                    },
                )
                logger.debug(f"Configuration loaded: {config}")
            except ValidationError as e:
                raise ValidationError(
                    e.errors(),
                    cls,
                    json_filepath,
                ) from e
        else:
            msg = f"Configuration file {json_filepath} not found."
            raise FileNotFoundError(msg)

        return config


def read_args(*, default_config_path: Path, default_text_path: Path) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hypno Audio Generation and Playback")
    _ = parser.add_argument(
        "-c",
        "--config_filepath",
        type=Path,
        default=default_config_path,
        help="Path to a JSON file containing configuration settings.",
    )
    _ = parser.add_argument(
        "-t",
        "--text_filepath",
        type=Path,
        default=default_text_path,
        help="Path to the text file containing lines to be converted to audio.",
    )
    _ = parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args()
