import multiprocessing
import multiprocessing.synchronize
import random
import time
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

from src.audio.line_player import LinePlayer

type FilePathChooserFn = Callable[[dict[str, Path], multiprocessing.synchronize.Lock], Iterator[tuple[str, Path]]]


def queue_filepaths(
    *,
    filepath_chooser: FilePathChooserFn,
    line_players: Iterable[LinePlayer],
    audio_filepaths: dict[str, Path],
    audio_filepaths_lock: multiprocessing.synchronize.Lock,
) -> None:
    """Queue audio filepaths from the generator to the line players, using a lock for safe access."""
    for line, filepath in filepath_chooser(audio_filepaths, audio_filepaths_lock):
        print(f"Playing {line}")
        for line_player in line_players:
            while line_player.queue.full():
                time.sleep(1)
            line_player.queue.put(filepath)


def get_sequential_complete_filepaths(
    audio_filepaths: dict[str, Path],
    audio_filepaths_lock: multiprocessing.synchronize.Lock,
) -> Iterator[tuple[str, Path]]:
    """Infinitely yield audio filepaths, playing in order and finishing the entire queue before starting over.

    Note that if the audio filepaths change while this is running, it will not restart the iteration until the next
    complete cycle.

    Args:
        audio_filepaths (dict[str, Path]): A dictionary mapping lines to their corresponding audio filepaths.
        audio_filepaths_lock (multiprocessing.synchronize.Lock): A lock to ensure thread-safe access to the audio file
            paths.

    Yields:
        tuple[str, Path]: A tuple containing the line and its corresponding audio filepath.
    """
    while True:
        with audio_filepaths_lock:
            items = list(audio_filepaths.items())
        if not items:
            time.sleep(1)
            continue
        yield from items


def get_sequential_refreshing_filepaths(
    audio_filepaths: dict[str, Path],
    audio_filepaths_lock: multiprocessing.synchronize.Lock,
) -> Iterator[tuple[str, Path]]:
    """Infinitely yield audio filepaths, starting again if the available filepaths change.

    Args:
        audio_filepaths (dict[str, Path]): A dictionary mapping lines to their corresponding audio filepaths.
        audio_filepaths_lock (multiprocessing.synchronize.Lock): A lock to ensure thread-safe access to the audio file
            paths.

    Yields:
        tuple[str, Path]: A tuple containing the line and its corresponding audio filepath.
    """
    last_keys = None

    while True:
        with audio_filepaths_lock:
            items = list(audio_filepaths.items())
            current_keys = tuple(audio_filepaths.keys())

        if not items:
            time.sleep(1)
            continue

        if last_keys is not None and current_keys != last_keys:
            # Dict changed, restart iteration
            last_keys = current_keys
            continue

        last_keys = current_keys
        for line, filepath in items:
            with audio_filepaths_lock:
                # Check if dict changed during iteration
                if tuple(audio_filepaths.keys()) != last_keys:
                    break  # Restart outer while loop
            yield line, filepath


def get_shuffled_filepaths(
    audio_filepaths: dict[str, Path],
    audio_filepaths_lock: multiprocessing.synchronize.Lock,
) -> Iterator[tuple[str, Path]]:
    """Infinitely yield audio filepaths in a random order, playing ALL items before checking for changes.

    Note that if the same filepath is yielded in quick succession, it will be skipped to avoid duplicates.

    Args:
        audio_filepaths (dict[str, Path]): A dictionary mapping lines to their corresponding audio filepaths.
        audio_filepaths_lock (multiprocessing.synchronize.Lock): A lock to ensure thread-safe access to the audio file
            paths.

    Yields:
        tuple[str, Path]: A tuple containing the line and its corresponding audio filepath.
    """
    last_filepath = None
    while True:
        with audio_filepaths_lock:
            items = list(audio_filepaths.items())

        if not items:
            time.sleep(1)
            continue

        random.shuffle(items)

        for line, filepath in items:
            # There's a chance that the last filepath from the previous iteration is the same as the current one,
            # so we skip yielding it to avoid duplicates in quick succession.
            if len(items) > 1 and filepath != last_filepath:
                yield line, filepath

            last_filepath = filepath


def get_random_filepath(
    audio_filepaths: dict[str, Path],
    audio_filepaths_lock: multiprocessing.synchronize.Lock,
) -> Iterator[tuple[str, Path]]:
    """Infinitely yield a random audio filepath, checking for changes in the available filepaths each time.

    Args:
        audio_filepaths (dict[str, Path]): A dictionary mapping lines to their corresponding audio filepaths.
        audio_filepaths_lock (multiprocessing.synchronize.Lock): A lock to ensure thread-safe access to the audio file
            paths.

    Yields:
        tuple[str, Path]: A tuple containing the line and its corresponding audio filepath.
    """
    last_filepath = None
    while True:
        with audio_filepaths_lock:
            items = list(audio_filepaths.items())

        if not items:
            time.sleep(1)
            continue

        chosen = random.choice(items)  # noqa: S311
        line, filepath = chosen

        if len(items) > 1:
            # There's a chance that the last filepath from the previous iteration is the same as the current one,
            # so we skip yielding it to avoid duplicates in quick succession.
            if filepath != last_filepath:
                yield line, filepath
                last_filepath = filepath
        else:
            # If there's only one item, we yield it regardless of whether it's the same as the last one.
            last_filepath = filepath
            yield line, filepath
