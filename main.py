import multiprocessing
import sys
import threading
import time
from pathlib import Path

from loguru import logger

from src.audio.line_player import get_line_players
from src.audio.repeating_player import RepeatingAudioPlayer
from src.audio.tts import generate_audio
from src.config import Config, read_args
from src.hypno_queue import get_shuffled_lines, queue_hypno_lines
from src.utils import wait_until_next_second

DEFAULT_CONFIG_PATH = Path("./import/settings/default.json")


def main() -> None:
    # Logging
    logger.remove(0)
    _ = logger.add(
        sys.stderr,
        level="DEBUG",
    )

    # Get settings
    args = read_args()
    config = Config.from_args(
        json_filepath=args.config or DEFAULT_CONFIG_PATH,
        text_filepath=args.text_filepath,
    )

    # Start generating audio files from the lines in the source text file
    manager = multiprocessing.Manager()
    hypno_line_mapping = manager.dict()
    hypno_lines_lock = manager.Lock()

    audio_generator_process = multiprocessing.Process(
        target=generate_audio,
        kwargs={
            "text_filepath": config.text_filepath,
            "output_audio_dir": config.line_dir,
            "hypno_line_mapping": hypno_line_mapping,
            "hypno_lines_lock": hypno_lines_lock,
        },
        daemon=True,
    )

    audio_generator_process.start()

    wait_until_next_second()

    if config.play_background_audio:
        # Start playing the background tone/noise
        background_player = RepeatingAudioPlayer(audio_filepath=Path("./import/audio/background/tone.wav"))
        background_player_thread = threading.Thread(
            target=background_player.play_audio_file,
            args=(config.background_chunk_size,),
            daemon=True,
        )
        background_player_thread.start()

        # Playback of main audio lines
        time.sleep(config.initial_line_delay)  # Initial delay before starting the line players

    line_players = get_line_players(initial_pitch_shift=config.initial_pitch_shift, echoes=config.max_echoes)

    filepath_queue_thread = threading.Thread(
        target=queue_hypno_lines,
        kwargs={
            "hypno_line_chooser": get_shuffled_lines,
            "line_players": line_players,
            "hypno_line_mapping": hypno_line_mapping,
            "hypno_lines_lock": hypno_lines_lock,
        },
        daemon=True,
    )
    filepath_queue_thread.start()

    for line_player in line_players:
        line_player_thread = threading.Thread(target=line_player.play_audio_files, args=(config.line_chunk_size,))
        line_player_thread.start()

    if config.play_mantra:
        time.sleep(config.mantra_start_delay)  # Delay before starting the mantra

        mantra_player = RepeatingAudioPlayer(audio_filepath=Path("./import/audio/mantras/mantra.mp3"))
        mantra_player_thread = threading.Thread(
            target=mantra_player.play_audio_file,
            args=(config.background_chunk_size,),
            daemon=True,
        )
        mantra_player_thread.start()


if __name__ == "__main__":
    main()
