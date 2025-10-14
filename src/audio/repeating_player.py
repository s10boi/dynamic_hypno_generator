from __future__ import annotations

from typing import TYPE_CHECKING, final

from pedalboard.io import AudioStream

from src.audio.line_player import AudioFile

if TYPE_CHECKING:
    from pathlib import Path


@final
class RepeatingAudioPlayer:
    """Repeatedly plays an audio file in a loop in a background thread."""

    def __init__(self, audio_filepath: Path) -> None:
        """Initialize the RepeatingAudioPlayer with a file path."""
        self.audio_filepath = audio_filepath

    def play_audio_file(self, chunk_size: int) -> None:
        """Play the audio file in a loop."""
        with AudioStream(output_device_name=AudioStream.default_output_device_name) as stream:  # pyright: ignore[reportUnknownArgumentType]
            while True:
                with AudioFile(str(self.audio_filepath), "r").resampled_to(stream.sample_rate) as audio_file:
                    while audio_file.tell() < audio_file.frames:
                        # Process and play the audio in chunks
                        audio = audio_file.read(chunk_size)
                        stream.write(audio, stream.sample_rate)
