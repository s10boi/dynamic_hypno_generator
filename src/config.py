from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self, cast

from loguru import logger
from pydantic import BaseModel, Field, ValidationError, field_validator

from src.hypno_queue import HypnoLineChooserFn, get_default_line_chooser, get_line_choosers  # noqa: TC001

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pydantic import ValidationInfo


DEFAULT_BACKGROUND_AUDIO = "tone"
DEFAULT_TEXT_PATH = Path("./lines.txt")


class Config(BaseModel):
    """Configuration for controlling various settings for hypno generation."""

    background_audio: str | None = Field(
        default=DEFAULT_BACKGROUND_AUDIO,
        description="Type of background audio to play.",
    )
    line_chooser: HypnoLineChooserFn = Field(
        default_factory=get_default_line_chooser,
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

    @field_validator("line_chooser", mode="before")
    @classmethod
    def validate_line_chooser_fn(cls, value: str | HypnoLineChooserFn) -> HypnoLineChooserFn:
        """Validate the line chooser function against available options.

        Returns:
            HypnoLineChooserFn: The validated line chooser function.

        Raises:
            ValueError: If the provided line chooser function is not valid.
        """
        line_choosers = get_line_choosers()

        if isinstance(value, str):
            if not (line_chooser_fn := line_choosers.get(value)):
                msg = f"Invalid line chooser function: {value}. Available options: {', '.join(line_choosers.keys())}"
                raise ValueError(msg)
            return line_chooser_fn
        return value

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
    ) -> Self:
        """Create a Config instance from a provided JSON file path and text file path.

        If settings are unavailable in the JSON file, default values will be used.

        Args:
            json_filepath (Path): Path to the JSON configuration file.
            available_backgrounds (Iterable[str]): Available background audio types for validation.

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
                    },
                )
                logger.debug(f"Configuration loaded: {config}")
            except ValidationError as e:
                logger.error(f"Failed to validate configuration from {json_filepath}: {e}")
                raise
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
