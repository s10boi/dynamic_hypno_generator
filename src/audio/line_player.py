from __future__ import annotations

from queue import Queue
from typing import TYPE_CHECKING, Self, final

import numpy as np
from loguru import logger
from pedalboard import (
    Delay,
    Gain,
    Mix,
    Pedalboard,  # pyright: ignore[reportPrivateImportUsage]
    PitchShift,
)
from pedalboard.io import AudioFile, AudioStream

from src.hypno_line import HypnoLine

if TYPE_CHECKING:
    from src.config import Config


@final
class LinePlayer:
    """A class that manages playback of audio files with a audio effects and initial delay.

    Attributes:
        queue (Queue[Path]): A queue to hold audio file paths for playback.
        pedalboard (Pedalboard): The Pedalboard instance containing audio effects.
    """

    def __init__(self, *, pedalboard: Pedalboard) -> None:
        """Initialize a LinePlayer with a pedalboard.

        Args:
            pedalboard (Pedalboard): The Pedalboard instance containing audio effects.
        """
        self.pedalboard = pedalboard
        self.queue = Queue[HypnoLine](maxsize=1)

    def play_audio_files(self, chunk_size: int, max_delay: int) -> None:
        """Play audio files from the queue with audio effects and an initial delay.

        Args:
            chunk_size (int): The number of frames to read at a time.
            max_delay (int): The maximum delay in seconds to add at the end of the audio.
        """
        with AudioStream(output_device_name=AudioStream.default_output_device_name) as stream:  # pyright: ignore[reportUnknownArgumentType]
            while True:
                hypno_line = self.queue.get()
                self._play_file(
                    hypno_line=hypno_line,
                    stream=stream,
                    chunk_size=chunk_size,
                    max_delay=max_delay,
                )

    def _play_file(self, *, hypno_line: HypnoLine, stream: AudioStream, chunk_size: int, max_delay: int) -> None:
        """Play a single audio file with the pedalboard effects."""
        print(hypno_line.text)

        with AudioFile(str(hypno_line.filepath), "r").resampled_to(stream.sample_rate) as audio_file:
            try:
                audio_data = audio_file.read(audio_file.frames)
            except ValueError as e:
                logger.error(f"Error reading audio file {hypno_line.filepath}: {e}")
            else:
                # Add MAX_DELAY silence at the end (so that all delays can be heard)
                audio_data = np.pad(
                    audio_data,
                    [(0, 0), (0, int((max_delay) * audio_file.samplerate))],
                )

                # Chunk the audio data to avoid memory issues
                for start in range(0, len(audio_data), chunk_size):
                    end = min(start + chunk_size, len(audio_data))
                    chunk = audio_data[start:end]
                    processed_chunk = self.pedalboard(chunk, audio_file.samplerate)
                    stream.write(processed_chunk, stream.sample_rate)

    @classmethod
    def from_config(cls, config: Config) -> Self:
        """Return a LinePlayer instance configured with audio effects for echoes based on the provided configuration."""
        boards = [
            # Main voice with a pitch shift
            Pedalboard([PitchShift(semitones=config.initial_pitch_shift)]),
        ]

        # Add echoes with decreasing pitch shift and volume, and increasing delay
        boards.extend(
            Pedalboard([
                PitchShift(semitones=config.initial_pitch_shift - (i * 0.5)),  # Decrease pitch for each echo
                Gain(gain_db=-12 * i),  # Decrease volume for each echo
                Delay(delay_seconds=i * config.echo_delay, mix=0.5),  # Increase delay for each echo
            ])
            for i in range(1, config.max_echoes + 1)
        )

        return cls(pedalboard=Pedalboard([Mix(boards)]))  # pyright: ignore[reportArgumentType]
