import multiprocessing
import multiprocessing.synchronize
import random
import time
from collections.abc import Callable, Iterable, Iterator, Mapping

from src.audio.line_player import LinePlayer
from src.hypno_line import HypnoLine

type HypnoLineChooserFn = Callable[
    [Mapping[str, HypnoLine], multiprocessing.synchronize.Lock],
    Iterator[HypnoLine],
]

SLEEP_PERIOD = 1


def queue_hypno_lines(
    *,
    hypno_line_chooser: HypnoLineChooserFn,
    line_players: Iterable[LinePlayer],
    hypno_line_mapping: dict[str, HypnoLine],
    hypno_lines_lock: multiprocessing.synchronize.Lock,
) -> None:
    """Queue audio filepaths from the generator to the line players, using a lock for safe access."""
    for hypno_line in hypno_line_chooser(hypno_line_mapping, hypno_lines_lock):
        print(f"Playing {hypno_line.text}")
        for line_player in line_players:
            while line_player.queue.full():
                time.sleep(1)
            line_player.queue.put(hypno_line)


def get_sequential_lines(
    hypno_line_mapping: Mapping[str, HypnoLine],
    hypno_lines_lock: multiprocessing.synchronize.Lock,
) -> Iterator[HypnoLine]:
    """Infinitely yield HypnoLine objects in the order, only checking for changes once all items have been yielded.

    Args:
        hypno_line_mapping (Mapping[str, HypnoLine]): A mapping of lines to their corresponding HypnoLine objects.
        hypno_lines_lock (multiprocessing.synchronize.Lock): A lock to ensure thread-safe access to the hypno lines.

    Yields:
        HypnoLine: The next HypnoLine object from the hypno line mapping.
    """
    while True:
        with hypno_lines_lock:
            hypno_lines = list(hypno_line_mapping.values())

        # No lines available, so wait before checking again
        if not hypno_lines:
            time.sleep(SLEEP_PERIOD)
            continue

        yield from hypno_lines


def get_sequential_refreshing_lines(
    hypno_line_mapping: Mapping[str, HypnoLine],
    hypno_lines_lock: multiprocessing.synchronize.Lock,
) -> Iterator[HypnoLine]:
    """Infinitely yield HypnoLine objects in the order, checking for changes in the mapping during iteration.

    Note that if the mapping changes during iteration, it will restart the iteration (new lines will be immediately
    available to be played).

    Args:
        hypno_line_mapping (Mapping[str, HypnoLine]): A mapping of lines to their corresponding HypnoLine objects.
        hypno_lines_lock (multiprocessing.synchronize.Lock): A lock to ensure thread-safe access to the hypno lines.

    Yields:
        HypnoLine: The next HypnoLine object from the hypno line mapping.
    """
    last_keys = None

    while True:
        with hypno_lines_lock:
            hypno_lines = list(hypno_line_mapping.values())
            current_keys = tuple(hypno_line_mapping.keys())

        if not hypno_lines:
            time.sleep(SLEEP_PERIOD)
            continue

        if last_keys is not None and current_keys != last_keys:
            # Dict changed, restart iteration
            last_keys = current_keys
            continue

        last_keys = current_keys
        for hypno_line in hypno_lines:
            with hypno_lines_lock:
                # Check if dict changed during iteration
                if tuple(hypno_line_mapping.keys()) != last_keys:
                    break  # Restart outer while loop
            yield hypno_line


def get_shuffled_lines(
    hypno_line_mapping: Mapping[str, HypnoLine],
    hypno_lines_lock: multiprocessing.synchronize.Lock,
) -> Iterator[HypnoLine]:
    """Infinitely yield HypnoLine objects in a random order, playing all lines before shuffling again.

    Note that repetition of the same line in quick succession is avoided.

    Args:
        hypno_line_mapping (Mapping[str, HypnoLine]): A mapping of lines to their corresponding HypnoLine objects.
        hypno_lines_lock (multiprocessing.synchronize.Lock): A lock to ensure thread-safe access to the hypno lines.

    Yields:
        HypnoLine: The next HypnoLine object from the hypno line mapping in a random order.
    """
    last_hypno_line = None

    while True:
        with hypno_lines_lock:
            hypno_lines = list(hypno_line_mapping.values())

        if not hypno_lines:
            time.sleep(SLEEP_PERIOD)
            continue

        random.shuffle(hypno_lines)

        for hypno_line in hypno_lines:
            # There's a chance that the last hypno from the previous iteration is the same as the current one,
            # so we skip yielding it to avoid duplicates in quick succession.
            if (len(hypno_lines) > 1 and hypno_line != last_hypno_line) or len(hypno_lines) == 1:
                yield hypno_line

            last_hypno_line = hypno_line


def get_random_lines(
    hypno_line_mapping: Mapping[str, HypnoLine],
    hypno_lines_lock: multiprocessing.synchronize.Lock,
) -> Iterator[HypnoLine]:
    """Infinitely yield HypnoLine objects in a random order, rechecking for changes after each line.

    Note that repetition of the same line in quick succession is avoided.

    Args:
        hypno_line_mapping (Mapping[str, HypnoLine]): A mapping of lines to their corresponding HypnoLine objects.
        hypno_lines_lock (multiprocessing.synchronize.Lock): A lock to ensure thread-safe access to the hypno lines.

    Yields:
        HypnoLine: The next HypnoLine object from the hypno line mapping in a random order.
    """
    last_hypno_line = None

    while True:
        with hypno_lines_lock:
            hypno_lines = list(hypno_line_mapping.values())

        if not hypno_lines:
            time.sleep(SLEEP_PERIOD)
            continue

        hypno_line = random.choice(hypno_lines)  # noqa: S311

        if (len(hypno_lines) > 1 and hypno_line != last_hypno_line) or len(hypno_lines) == 1:
            yield hypno_line

        last_hypno_line = hypno_line
