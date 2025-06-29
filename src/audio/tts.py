import datetime
import time
from hashlib import sha256
from pathlib import Path

from src.audio.speech.speech import get_engine
from src.shared import clean_line


def generate_audio(
    text_filepath: Path,
    output_audio_dir: Path,
    exported_files: dict[str, Path],
    check_interval: int,
    output_audio_file_extension: str = "wav",
) -> None:
    last_generation_time: datetime.datetime | None = None

    while True:  # noqa: PLR1702
        last_save_time = text_filepath.stat().st_mtime

        # If the file has changed since the last generation, process it
        if last_generation_time is None or last_save_time > last_generation_time.timestamp():
            last_generation_time = datetime.datetime.fromtimestamp(last_save_time, tz=datetime.UTC)

            with text_filepath.open(encoding="utf-8") as file:
                lines = file.readlines()

                for line in lines:
                    line = clean_line(line)  # noqa: PLW2901
                    hashed_text = sha256(line.encode("utf-8")).hexdigest()
                    audio_filepath = output_audio_dir / f"{hashed_text}.{output_audio_file_extension}"

                    if line not in exported_files:
                        if not audio_filepath.exists():
                            engine = get_engine()
                            engine.save_to_file(line, str(audio_filepath))
                            engine.runAndWait()
                            time.sleep(0.1)
                        exported_files[line] = audio_filepath
        else:
            # If the file has not changed, wait for a while before checking again to save resources
            time.sleep(check_interval)
