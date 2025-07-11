import multiprocessing
import multiprocessing.synchronize
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import final, override

from src.shared import clean_line


class TextFileBasedFilePathGenerator(ABC):
    def generate_filepaths_with_lock(
        self,
        audio_filepaths: dict[str, Path],
        audio_filepaths_lock: multiprocessing.synchronize.Lock,
    ) -> Iterator[tuple[str, Path]]:
        for raw_line in self.get_text_lines():
            line = clean_line(raw_line)
            while True:
                with audio_filepaths_lock:
                    try:
                        audio_filepath = audio_filepaths[line]
                    except KeyError:
                        audio_filepath = None
                if audio_filepath and audio_filepath.exists() and audio_filepath.stat().st_size > 0:
                    yield line, audio_filepath
                    break
                else:
                    time.sleep(0.1)

    """Abstract base class for generating audio file paths from lines in a text file."""

    def __init__(self, text_filepath: Path, output_audio_dir: Path, output_audio_file_extension: str = "wav") -> None:  # pyright: ignore[reportMissingSuperCall]
        """Initialize the generator with a text file and file extension.

        Args:
            text_filepath (Path): The path to the text file containing lines to use to create audio files.
            output_audio_dir (Path): The directory where the created audio files will be saved.
            output_audio_file_extension (str): The file extension of the created audio files.
        """
        self.text_filepath = text_filepath
        self.output_audio_dir = output_audio_dir
        self.output_audio_file_extension = output_audio_file_extension

    def generate_filepaths(self, audio_filepaths: dict[str, Path]) -> Iterator[tuple[str, Path]]:
        for line in self.get_text_lines():
            line = clean_line(line)  # noqa: PLW2901
            try:
                audio_filepath = audio_filepaths[line]
            except KeyError:
                print(f"Unable to find audio file for line: {line}")
            else:
                yield line, audio_filepath

    @abstractmethod
    def get_text_lines(self) -> Iterator[str]:
        """Yield lines from the text file."""


@final
class SequentialTextFileBasedFilePathGenerator(TextFileBasedFilePathGenerator):
    """Generates audio file paths from lines in a text file in order.

    Note that all lines are played in order before any changes to the text file are detected.
    """

    @override
    def get_text_lines(self) -> Iterator[str]:
        """Yield lines from the text file in order.

        Yields:
            Iterator[str]: An iterator that yields lines from the text file.

        Raises:
            ValueError: If the text file is empty or contains no valid lines.
        """
        while True:
            with self.text_filepath.open("r", encoding="utf-8") as file:
                if not (raw_lines := file.readlines()):
                    msg = f"Text file {self.text_filepath} is empty or does not exist."
                    raise ValueError(msg)

                else:
                    lines = [line.strip() for line in raw_lines if line.strip()]
                    if not lines:
                        msg = f"Text file {self.text_filepath} contains no valid lines."
                        raise ValueError(msg)

                    yield from lines


@final
class ShuffledTextFileBasedFilePathGenerator(TextFileBasedFilePathGenerator):
    """Generates audio file paths from lines in a text file in random order.

    ALL lines are played once before any changes to the text file are detected. If the same line appears twice in a row,
    it is skipped.
    """

    @override
    def get_text_lines(self) -> Iterator[str]:
        """Yield lines from the text file in random order.

        Yields:
            Iterator[str]: An iterator that yields lines from the text file in random order.

        Raises:
            ValueError: If the text file is empty or contains no valid lines.
        """
        last_line: str | None = None

        while True:
            with self.text_filepath.open("r", encoding="utf-8") as file:
                if not (raw_lines := file.readlines()):
                    msg = f"Text file {self.text_filepath} is empty or does not exist."
                    raise ValueError(msg)

                else:
                    lines = [line.strip() for line in raw_lines if line.strip()]
                    if not lines:
                        msg = f"Text file {self.text_filepath} contains no valid lines."
                        raise ValueError(msg)

                    random.shuffle(lines)
                    for line in lines:
                        # Skip the same line if it was the last one yielded
                        if line != last_line:
                            last_line = line
                            yield line


@final
class RandomTextFileBasedFilePathGenerator(TextFileBasedFilePathGenerator):
    """Generates audio file paths from lines in a text file in random order.

    The file is read EACH time a line is requested, so it can be updated live. If the same line appears twice in a row,
    it is skipped. This allows for dynamic updates to the text file while the generator is running
    """

    @override
    def get_text_lines(self) -> Iterator[str]:
        last_line: str | None = None

        while True:
            with self.text_filepath.open("r", encoding="utf-8") as file:
                if not (raw_lines := file.readlines()):
                    msg = f"Text file {self.text_filepath} is empty or does not exist."
                    raise ValueError(msg)

                else:
                    chosen_line = random.choice(raw_lines).strip()  # noqa: S311
                    if chosen_line and chosen_line != last_line:
                        last_line = chosen_line
                        yield last_line
