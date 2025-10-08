from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from src.audio.speech import get_engine
from src.hypno_line import HypnoLine, clean_line
from src.log import configure_logger

if TYPE_CHECKING:
    import multiprocessing.synchronize
    from collections.abc import MutableMapping

FILE_WRITE_WAIT = 2
SLEEP_PERIOD = 5


def _get_lines_from_file(text_filepath: Path) -> list[str]:
    """Read lines from a text file, cleaning and deduplicating them."""
    lines: list[str] = []

    with text_filepath.open(encoding="utf-8") as file:
        for raw_line in file:
            if (line := clean_line(raw_line)) and line not in lines:
                lines.append(line)
    return lines


def generate_audio(
    *,
    text_filepath: Path,
    output_audio_dir: Path,
    hypno_line_mapping: MutableMapping[str, HypnoLine],
    hypno_lines_lock: multiprocessing.synchronize.Lock,
    debug: bool,
) -> None:
    """Generates audio files for each line in the text file, and updates the available files mapping.

    This function continuously checks the text file for changes, generates audio files for new lines and updates the
    `hypno_line_mapping` with the new audio files. It uses a text-to-speech engine to generate the audio.

    Args:
        text_filepath (Path): The path to the text file containing lines to be converted to audio.
        output_audio_dir (Path): The directory where the generated audio files will be saved.
        hypno_line_mapping (MutableMapping[str, HypnoLine]): Mapping of lines to their corresponding HypnoLine objects.
        hypno_lines_lock (multiprocessing.synchronize.Lock): A lock to synchronize access to the hypno_line_mapping.
        debug (bool): Whether to enable debug logging.
    """
    # Because this function is run in a separate process, we need to configure the logger again
    configure_logger(debug=debug)

    last_generation_time: float | None = None
    engine = get_engine()

    while True:
        logger.debug(f"Checking for changes in {text_filepath}")
        last_save_time = text_filepath.stat().st_mtime

        # If the file has changed since the last generation, process it
        if last_generation_time is None or last_save_time > last_generation_time:
            new_lines = 0
            logger.info(f"File has changed since {last_generation_time}, processing new lines.")

            last_generation_time = last_save_time

            # The existing dictionary of files will be replaced with new files once ALL lines have been processed
            new_exported_files: dict[str, HypnoLine] = {}

            lines = _get_lines_from_file(text_filepath)

            for line in lines:
                hypno_line = hypno_line_mapping.get(line) or HypnoLine.from_text(
                    text=line,
                    output_audio_dir=output_audio_dir,
                )

                if not hypno_line.filepath.exists():
                    logger.debug(f"Generating audio for line: {line.strip()}")
                    engine.save_to_file(line, str(hypno_line.filepath))
                    new_lines += 1

                new_exported_files[line] = hypno_line

            # Save all queued up audio files
            if new_lines:
                logger.debug(f"Saving {new_lines} audio files to disk.")
                engine.runAndWait()

                # Wait until all audio files are confirmed to exist and are non-empty before updating exported_files
                while not all(
                    hypno_line.filepath.exists() and Path(hypno_line.filepath).stat().st_size > 0
                    for hypno_line in new_exported_files.values()
                ):
                    logger.debug("Waiting for audio files to be fully written...")
                    time.sleep(FILE_WRITE_WAIT)
            else:
                logger.debug("No new audio files to save.")

            # Getting all duration values for the lines
            for hypno_line in new_exported_files.values():
                if not hypno_line.duration:
                    hypno_line.set_duration()

            logger.debug("All audio files are now saved and non-empty.")

            with hypno_lines_lock:
                hypno_line_mapping.clear()
                hypno_line_mapping.update(new_exported_files)
            logger.debug(f"Available files is now {len(hypno_line_mapping)}")
        else:
            logger.debug("No changes detected, waiting before checking again.")
            time.sleep(SLEEP_PERIOD)
