import multiprocessing
import threading
import time
from pathlib import Path

from src.audio.repeating_player import RepeatingAudioPlayer
from src.audio.tts import generate_audio
from src.config import Config, read_args
from src.hypno_queue import LinePlayer, get_random_lines, queue_hypno_lines
from src.log import configure_logger

DEFAULT_CONFIG_PATH = Path("./config.json")

BACKGROUND_AUDIO: dict[str, Path] = {
    "tone": Path("./import/audio/background/tone.wav"),
    "noise": Path("./import/audio/background/noise.wav"),
}


def main() -> None:
    # SETUP
    # =====
    # Get settings
    args = read_args()

    configure_logger(debug=args.debug)

    # Load configuration
    config = Config.from_args(
        json_filepath=args.config or DEFAULT_CONFIG_PATH,
        text_filepath=args.text_filepath,
        available_backgrounds=BACKGROUND_AUDIO.keys(),
    )

    # HYPNO LINE GENERATION
    # =====================
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
            kwargs={"chunk_size": config.background_chunk_size},
            daemon=True,
        )
        background_player_thread.start()

        # If there's a background audio file, delay before starting to play the hypno lines
        time.sleep(config.initial_line_delay)

    # HYPNO LINE PLAYBACK
    # ===================
    line_players = [
        LinePlayer.from_config(config),
        LinePlayer.from_config(config),
    ]

    filepath_queue_thread = threading.Thread(
        target=queue_hypno_lines,
        kwargs={
            "hypno_line_chooser": get_random_lines,
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
                "chunk_size": config.line_chunk_size,
                "max_delay": config.max_echoes * config.echo_delay,
            },
        )
        line_player_thread.start()

    # MANTRA PLAYBACK
    # ================
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
