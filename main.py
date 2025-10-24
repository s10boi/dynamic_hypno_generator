from __future__ import annotations

import multiprocessing
import sys
import threading
import time
from pathlib import Path

from loguru import logger
from pydantic import ValidationError

from src.audio.line_player import LinePlayer
from src.audio.repeating_player import RepeatingAudioPlayer
from src.audio.tts import generate_audio
from src.config import Config, read_args
from src.hypno_queue import (
    queue_hypno_lines,
)
from src.log import configure_logger

DEFAULT_CONFIG_PATH = Path("./config.json")
DEFAULT_TEXT_PATH = Path("./lines.txt")
BACKGROUND_CHUNK_SIZE = 8000
LINE_CHUNK_SIZE = 96_000
LINE_DIR = Path("./import/lines")

BACKGROUND_AUDIO: dict[str, Path] = {
    "tone": Path("./import/background/tone.wav"),
    "noise": Path("./import/background/noise.wav"),
}


def main() -> None:
    # SETUP
    # =====
    # Get settings
    args = read_args(
        default_config_path=DEFAULT_CONFIG_PATH,
        default_text_path=DEFAULT_TEXT_PATH,
    )

    configure_logger(debug=args.debug)

    # Load configuration
    try:
        config = Config.from_args(
            json_filepath=args.config_filepath,
            available_backgrounds=BACKGROUND_AUDIO.keys(),
        )
    except (FileNotFoundError, ValidationError) as e:
        logger.critical(
            f"Failed to load configuration: {e}. Please check the configuration file at {args.config_filepath}.",
        )
        sys.exit(1)

    # HYPNO LINE GENERATION
    # =====================
    # Start generating audio files from the lines in the source text file
    if not args.text_filepath.exists():
        logger.critical(f"Text file {args.text_filepath} not found. Please ensure it exists.")
        sys.exit(1)

    manager = multiprocessing.Manager()
    hypno_line_mapping = manager.dict()
    hypno_lines_lock = manager.Lock()

    audio_generator_process = multiprocessing.Process(
        target=generate_audio,
        kwargs={
            "text_filepath": args.text_filepath,
            "output_audio_dir": LINE_DIR,
            "hypno_line_mapping": hypno_line_mapping,
            "hypno_lines_lock": hypno_lines_lock,
            # needed because the audio generator process is a separate process, so the logger needs to be set up again
            "debug": args.debug,
        },
        daemon=True,
    )

    audio_generator_process.start()

    # Wait for the audio generator to finish generating lines the first time
    while not hypno_line_mapping:
        time.sleep(0.1)

    # BACKGROUND AUDIO
    # ================
    if config.background_audio:
        background_player = RepeatingAudioPlayer(audio_filepath=BACKGROUND_AUDIO[config.background_audio])
        background_player_thread = threading.Thread(
            target=background_player.play_audio_file,
            kwargs={"chunk_size": BACKGROUND_CHUNK_SIZE},
            daemon=True,
        )
        background_player_thread.start()

        # If there's a background audio file, delay before starting to play the hypno lines
        time.sleep(config.initial_line_delay)

    # HYPNO LINE PLAYBACK
    # ===================
    # Two line players are needed - one starting just after the first line is played, but while it's still playing the
    # echoes
    line_players = [
        LinePlayer.from_config(config),
        LinePlayer.from_config(config),
    ]

    filepath_queue_thread = threading.Thread(
        target=queue_hypno_lines,
        kwargs={
            "hypno_line_chooser": config.line_chooser,
            "line_players": line_players,
            "hypno_line_mapping": hypno_line_mapping,
            "hypno_lines_lock": hypno_lines_lock,
        },
        daemon=True,
    )
    filepath_queue_thread.start()

    for line_player in line_players:
        line_player_thread = threading.Thread(
            target=line_player.play_audio_files,
            kwargs={
                "chunk_size": LINE_CHUNK_SIZE,
                "max_delay": config.max_echoes * config.echo_delay,
            },
        )
        line_player_thread.start()

    # MANTRA PLAYBACK
    # ================
    if config.mantra_filepath:
        time.sleep(config.mantra_start_delay)

        mantra_player = RepeatingAudioPlayer(audio_filepath=config.mantra_filepath)
        mantra_player_thread = threading.Thread(
            target=mantra_player.play_audio_file,
            kwargs={"chunk_size": BACKGROUND_CHUNK_SIZE},
            daemon=True,
        )
        mantra_player_thread.start()


if __name__ == "__main__":
    main()
