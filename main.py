import threading
import time
from pathlib import Path

from src.audio.line_player import get_line_players
from src.audio.repeating_player import RepeatingAudioPlayer
from src.audio.tts import generate_audio
from src.config import Config, read_args
from src.filepath_generators.text_based import ShuffledTextFileBasedFilePathGenerator
from src.filepath_queue import queue_filepaths


def main() -> None:
    # Get settings
    args = read_args()
    config = Config.from_args(json_filepath=args.config, text_filepath=args.text_filepath)

    # Start generating audio files from the lines in the source text file
    audio_filepaths: dict[str, Path] = {}

    audio_generator_thread = threading.Thread(
        target=generate_audio,
        kwargs={
            "text_filepath": config.text_filepath,
            "output_audio_dir": config.line_dir,
            "exported_files": audio_filepaths,
            "output_audio_file_extension": "wav",
            "check_interval": config.text_file_check_interval,
        },
        daemon=True,
    )
    audio_generator_thread.start()

    time.sleep(3)

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

    filepath_generator = ShuffledTextFileBasedFilePathGenerator(
        text_filepath=Path("./import/text/lines.txt"),
        output_audio_dir=config.line_dir,
        output_audio_file_extension="wav",
    )

    filepath_queue_thread = threading.Thread(
        target=queue_filepaths,
        kwargs={
            "generator": filepath_generator,
            "line_players": line_players,
            "audio_filepaths": audio_filepaths,
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
