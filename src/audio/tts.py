from __future__ import annotations

import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from pydub import AudioSegment

from src.audio.speech import get_engine
from src.hypno_line import HypnoLine, clean_line
from src.log import configure_logger

if TYPE_CHECKING:
    import multiprocessing.synchronize
    from collections.abc import MutableMapping

FILE_WRITE_WAIT = 2
SLEEP_PERIOD = 5
PAUSE_PATTERN = re.compile(r"\[pause\s+(\d+(?:\.\d+)?)\s+seconds?\]", re.IGNORECASE)


def _parse_line_segments(line: str) -> list[tuple[str, str]]:
    """Parse a line into ('speech', text) and ('pause', seconds) segments.

    Returns a sequence preserving order. Pause segments store the numeric seconds as a string.
    """
    segments: list[tuple[str, str]] = []
    last_index = 0

    for match in PAUSE_PATTERN.finditer(line):
        start, end = match.span()
        # Speech before this pause
        speech_chunk = line[last_index:start].strip()
        if speech_chunk:
            segments.append(("speech", speech_chunk))
        # Pause
        seconds = match.group(1)
        segments.append(("pause", seconds))
        last_index = end

    # Remaining speech
    tail = line[last_index:].strip()
    if tail:
        segments.append(("speech", tail))

    # If the line was only a pause directive (unlikely given formatting), we still return the pause
    if not segments and PAUSE_PATTERN.fullmatch(line.strip()):
        seconds = PAUSE_PATTERN.fullmatch(line.strip()).group(1)  # type: ignore[reportOptionalCall]
        segments.append(("pause", seconds))

    return segments


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

            # For lines containing pauses we will assemble the final audio after TTS generation of speech segments.
            combine_jobs: list[tuple[HypnoLine, list[tuple[str, str]], list[Path]]] = []

            for line in lines:
                hypno_line = hypno_line_mapping.get(line) or HypnoLine.from_text(
                    text=line,
                    output_audio_dir=output_audio_dir,
                )

                # Parse segments for pause directives
                segments = _parse_line_segments(line)
                has_pause = any(kind == "pause" for kind, _ in segments)

                if not hypno_line.filepath.exists():
                    if has_pause:
                        temp_paths: list[Path] = []
                        # Queue TTS generation for each speech segment only
                        for idx, (kind, value) in enumerate(segments):
                            if kind == "speech":
                                temp_path = hypno_line.filepath.parent / f"{hypno_line.filepath.stem}_seg{idx}.tmp.wav"
                                engine.save_to_file(value, str(temp_path))
                                temp_paths.append(temp_path)
                        if temp_paths:
                            new_lines += 1  # Count as one new composite line
                        combine_jobs.append((hypno_line, segments, temp_paths))
                    else:
                        # No pauses, single segment line
                        if segments and segments[0][0] == "speech":
                            engine.save_to_file(segments[0][1], str(hypno_line.filepath))
                            new_lines += 1
                        else:
                            # Empty line after cleaning and parsing: skip
                            logger.debug(f"Skipping empty or pause-only line: {line}")

                new_exported_files[line] = hypno_line

            # Save all queued up audio files
            if new_lines:
                logger.debug(f"Saving {new_lines} new (including composite) audio files to disk.")
                engine.runAndWait()

                # Wait until all speech segment audio files exist and are non-empty
                while not all(
                    (
                        (hypno_line.filepath.exists() and hypno_line.filepath.stat().st_size > 0)
                        if not any(kind == "pause" for kind, _ in _parse_line_segments(hypno_line.text))
                        else all(p.exists() and p.stat().st_size > 0 for p in temp_paths)
                    )
                    for hypno_line, segments, temp_paths in combine_jobs
                ):
                    logger.debug("Waiting for all speech segment audio files to be fully written...")
                    time.sleep(FILE_WRITE_WAIT)

                # Combine jobs (assemble pauses + speech)
                for hypno_line, segments, temp_paths in combine_jobs:
                    has_pause = any(kind == "pause" for kind, _ in segments)
                    if not has_pause:
                        # No combination needed
                        continue

                    # Build final audio
                    combined = AudioSegment.silent(duration=0)
                    temp_index = 0
                    for kind, value in segments:
                        if kind == "speech":
                            try:
                                seg_audio = AudioSegment.from_file(temp_paths[temp_index])
                            except Exception as exc:  # noqa: BLE001
                                logger.error(f"Failed loading speech segment for line '{hypno_line.text}': {exc}")
                                seg_audio = AudioSegment.silent(duration=0)
                            combined += seg_audio
                            temp_index += 1
                        else:  # pause
                            try:
                                seconds = float(value)
                            except ValueError:
                                logger.warning(f"Invalid pause duration '{value}' in line '{hypno_line.text}', skipping pause.")
                                continue
                            combined += AudioSegment.silent(duration=int(seconds * 1000))

                    # Export combined to final filepath
                    try:
                        combined.export(hypno_line.filepath, format="wav")
                    except Exception as exc:  # noqa: BLE001
                        logger.error(f"Failed exporting combined line '{hypno_line.text}': {exc}")
                    finally:
                        # Clean up temp segment files
                        for p in temp_paths:
                            try:
                                p.unlink(missing_ok=True)
                            except Exception:  # noqa: BLE001
                                pass

            else:
                logger.debug("No new audio files to save.")

            # Getting all duration values for the lines
            for hypno_line in new_exported_files.values():
                if not hypno_line.duration and hypno_line.filepath.exists():
                    try:
                        hypno_line.set_duration()
                    except FileNotFoundError:
                        logger.error(f"Expected audio file missing for line: {hypno_line.text}")

            logger.debug("All audio files are now saved and non-empty.")

            with hypno_lines_lock:
                hypno_line_mapping.clear()
                hypno_line_mapping.update(new_exported_files)
            logger.debug(f"Available files is now {len(hypno_line_mapping)}")
        else:
            logger.debug("No changes detected, waiting before checking again.")
            time.sleep(SLEEP_PERIOD)


# Public helper for one-off batch generation (used by --render-mix path)
# Generates audio for provided text lines if missing, respecting pause directives.
# Returns a mapping of line text -> HypnoLine objects (with durations set).

def generate_lines_once(text_lines: list[str], output_audio_dir: Path) -> dict[str, HypnoLine]:
    engine = get_engine()
    new_exported_files: dict[str, HypnoLine] = {}
    combine_jobs: list[tuple[HypnoLine, list[tuple[str, str]], list[Path]]] = []
    queued = 0

    for line in text_lines:
        if not line:
            continue
        hypno_line = HypnoLine.from_text(line, output_audio_dir)
        segments = _parse_line_segments(line)
        has_pause = any(kind == "pause" for kind, _ in segments)

        if not hypno_line.filepath.exists():
            if has_pause:
                temp_paths: list[Path] = []
                for idx, (kind, value) in enumerate(segments):
                    if kind == "speech":
                        temp_path = hypno_line.filepath.parent / f"{hypno_line.filepath.stem}_seg{idx}.tmp.wav"
                        engine.save_to_file(value, str(temp_path))
                        temp_paths.append(temp_path)
                if temp_paths:
                    queued += 1
                combine_jobs.append((hypno_line, segments, temp_paths))
            else:
                if segments and segments[0][0] == "speech":
                    engine.save_to_file(segments[0][1], str(hypno_line.filepath))
                    queued += 1
                else:
                    logger.debug(f"Skipping empty or pause-only line during batch generation: {line}")

        new_exported_files[line] = hypno_line

    if queued:
        logger.debug(f"Batch generating {queued} line audio files for mix render.")
        engine.runAndWait()

        # Wait for all speech segment files to exist (for paused lines) before combining
        wait_attempts = 0
        while not all(
            (
                (hypno_line.filepath.exists() and hypno_line.filepath.stat().st_size > 0)
                if not any(kind == "pause" for kind, _ in _parse_line_segments(hypno_line.text))
                else all(p.exists() and p.stat().st_size > 0 for p in temp_paths)
            )
            for hypno_line, segments, temp_paths in combine_jobs
        ) and wait_attempts < 30:
            time.sleep(FILE_WRITE_WAIT)
            wait_attempts += 1

        # Combine paused lines
        for hypno_line, segments, temp_paths in combine_jobs:
            if not any(kind == "pause" for kind, _ in segments):
                continue
            combined = AudioSegment.silent(duration=0)
            temp_index = 0
            for kind, value in segments:
                if kind == "speech":
                    try:
                        seg_audio = AudioSegment.from_file(temp_paths[temp_index])
                    except Exception as exc:  # noqa: BLE001
                        logger.error(f"Failed loading batch speech segment for line '{hypno_line.text}': {exc}")
                        seg_audio = AudioSegment.silent(duration=0)
                    combined += seg_audio
                    temp_index += 1
                else:
                    try:
                        seconds = float(value)
                    except ValueError:
                        logger.warning(f"Invalid pause duration '{value}' in line '{hypno_line.text}' during batch gen.")
                        continue
                    combined += AudioSegment.silent(duration=int(seconds * 1000))
            try:
                combined.export(hypno_line.filepath, format="wav")
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Failed exporting combined batch line '{hypno_line.text}': {exc}")
            finally:
                for p in temp_paths:
                    try:
                        p.unlink(missing_ok=True)
                    except Exception:  # noqa: BLE001
                        pass

    # Set durations
    for hypno_line in new_exported_files.values():
        if hypno_line.filepath.exists():
            try:
                hypno_line.set_duration()
            except FileNotFoundError:
                logger.error(f"Missing expected generated file for line: {hypno_line.text}")

    return new_exported_files
