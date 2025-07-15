import time
from pathlib import Path
from queue import Queue
from typing import final

from pedalboard import (
    Gain,
    Pedalboard,  # pyright: ignore[reportPrivateImportUsage]
    PitchShift,
)
from pedalboard.io import AudioFile, AudioStream

from src.hypno_line import HypnoLine


@final
class LinePlayer:
    """A class that manages playback of audio files with a audio effects and initial delay.

    Attributes:
        queue (Queue[Path]): A queue to hold audio file paths for playback.
        pedalboard (Pedalboard): The Pedalboard instance containing audio effects.
        initial_delay (float): The initial delay in seconds before playback starts.
    """

    def __init__(self, *, pedalboard: Pedalboard, initial_delay: float) -> None:
        """Initialize a LinePlayer with a pedalboard and an initial delay.

        Args:
            pedalboard (Pedalboard): The Pedalboard instance containing audio effects.
            initial_delay (float): The initial delay in seconds before playback starts.
        """
        self.pedalboard = pedalboard
        self.initial_delay = initial_delay
        self.queue = Queue[HypnoLine](maxsize=1)
        self.next_file_play_time = None

    def play_audio_files(self, chunk_size: int) -> None:
        """Play audio files from the queue with audio effects and an initial delay.

        Args:
            chunk_size (int): The number of frames to read at a time.
        """
        with AudioStream(output_device_name=AudioStream.default_output_device_name) as stream:  # pyright: ignore[reportUnknownArgumentType]
            # Add the initial delay of the voice echoes so that each starts at the right time
            time.sleep(self.initial_delay)

            while True:
                hypno_line = self.queue.get()
                # Only try to play the file if it is time to play it
                if self.next_file_play_time:
                    while time.time() < self.next_file_play_time:
                        time.sleep(0.1)
                self._play_file(audio_filepath=hypno_line.filepath, stream=stream, chunk_size=chunk_size)

    def _play_file(self, *, audio_filepath: Path, stream: AudioStream, chunk_size: int) -> None:
        """Play a single audio file with the pedalboard effects."""
        with AudioFile(str(audio_filepath), "r").resampled_to(stream.sample_rate) as audio_file:  # pyright: ignore[reportArgumentType, reportAttributeAccessIssue, reportUnknownVariableType]
            self.next_file_play_time = time.time() + audio_file.duration
            while audio_file.tell() < audio_file.frames:
                # Process and play the audio in chunks
                audio = audio_file.read(chunk_size)  # pyright: ignore[reportUnknownVariableType]
                processed = self.pedalboard(audio, audio_file.samplerate)  # pyright: ignore[reportUnknownArgumentType]
                stream.write(processed, stream.sample_rate)


def get_line_players(*, initial_pitch_shift: float, echoes: int) -> list[LinePlayer]:
    """Create a list of LinePlayers with different audio effects.

    Args:
        initial_pitch_shift (float): The initial pitch shift in semitones for the main voice.
        echoes (int): The number of echoes to create, each with decreasing pitch shift and gain and increasing delay.

    Returns:
        list[LinePlayer]: LinePlayers configured with the specified audio effects.
    """
    line_players = [
        LinePlayer(
            pedalboard=Pedalboard([
                PitchShift(semitones=initial_pitch_shift),
            ]),
            initial_delay=0,
        ),
    ]
    line_players.extend(
        LinePlayer(
            pedalboard=Pedalboard([
                PitchShift(semitones=initial_pitch_shift - i * 0.5),  # Decrease pitch shift for each echo
                Gain(gain_db=-12 * i),  # Decrease gain for each echo
            ]),
            initial_delay=i * 1.5,  # Increase delay for each echo
        )
        for i in range(1, echoes + 1)
    )

    return line_players
