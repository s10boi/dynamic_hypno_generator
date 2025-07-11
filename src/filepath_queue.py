import multiprocessing
import multiprocessing.synchronize
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Protocol

from src.audio.line_player import LinePlayer


class AudioFilepathGenerator(Protocol):
    def generate_filepaths_with_lock(
        self,
        audio_filepaths: dict[str, Path],
        audio_filepaths_lock: multiprocessing.synchronize.Lock,
    ) -> Iterator[tuple[str, Path]]: ...


def queue_filepaths(
    *,
    generator: AudioFilepathGenerator,
    line_players: Iterable[LinePlayer],
    audio_filepaths: dict[str, Path],
    audio_filepaths_lock: multiprocessing.synchronize.Lock,
) -> None:
    """Queue audio file paths from the generator to the line players, using a lock for safe access."""
    for line, filepath in generator.generate_filepaths_with_lock(audio_filepaths, audio_filepaths_lock):
        print(f"Playing {line}")
        for line_player in line_players:
            while line_player.queue.full():
                time.sleep(1)
            line_player.queue.put(filepath)
