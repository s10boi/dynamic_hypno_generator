import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Protocol

from src.audio.line_player import LinePlayer


class AudioFilepathGenerator(Protocol):
    def generate_filepaths(self, audio_filepaths: dict[str, Path]) -> Iterator[tuple[str, Path]]: ...


def queue_filepaths(
    *,
    generator: AudioFilepathGenerator,
    line_players: Iterable[LinePlayer],
    audio_filepaths: dict[str, Path],
) -> None:
    """Queue audio file paths from the generator to the line players."""
    for line, filepath in generator.generate_filepaths(audio_filepaths):
        print(f"Playing {line}")
        for line_player in line_players:
            while line_player.queue.full():
                time.sleep(1)
            line_player.queue.put(filepath)
