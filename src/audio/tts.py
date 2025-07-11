import multiprocessing
import multiprocessing.synchronize
import time
from hashlib import sha256
from pathlib import Path

from loguru import logger

from src.audio.speech.speech import get_engine
from src.shared import clean_line


def generate_audio(
    text_filepath: Path,
    output_audio_dir: Path,
    exported_files: dict[str, Path],
    exported_files_lock: multiprocessing.synchronize.Lock,
    output_audio_file_extension: str = "wav",
) -> None:
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
            new_exported_files: dict[str, Path] = {}

            with text_filepath.open(encoding="utf-8") as file:
                lines = file.readlines()

            for line in lines:
                line = clean_line(line)  # noqa: PLW2901
                hashed_text = sha256(line.encode("utf-8")).hexdigest()
                audio_filepath = output_audio_dir / f"{hashed_text}.{output_audio_file_extension}"

                if not audio_filepath.exists():
                    logger.debug(f"Generating audio for line: {line.strip()}")
                    engine.save_to_file(line, str(audio_filepath))
                    new_lines += 1

                # All lines are logged and made available for playback, even if they are not generated
                new_exported_files[line] = audio_filepath

            # Save all queued up audio files
            if new_lines:
                logger.debug(f"Saving {new_lines} audio files to disk.")
                engine.runAndWait()
            else:
                logger.debug("No new audio files to save.")

            # Wait until all audio files are confirmed to exist and are non-empty before updating exported_files
            while not all(
                audio_filepath.exists() and Path(audio_filepath).stat().st_size > 0
                for audio_filepath in new_exported_files.values()
            ):
                logger.debug("Waiting for audio files to be fully written...")
                time.sleep(1)

            logger.debug("All audio files are now saved and non-empty.")

            with exported_files_lock:
                exported_files.clear()
                exported_files.update(new_exported_files)
            logger.debug(f"Available files is now {len(exported_files)}")
        else:
            time.sleep(5)
