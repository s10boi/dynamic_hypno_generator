from __future__ import annotations

import multiprocessing.synchronize
import random
import time
from collections.abc import Callable, Iterator, Mapping
from typing import TYPE_CHECKING

from src.hypno_line import HypnoLine

if TYPE_CHECKING:
    from src.audio.line_player import LinePlayer

type HypnoLineChooserFn = Callable[
    [Mapping[str, HypnoLine], multiprocessing.synchronize.Lock],
    Iterator[HypnoLine],
]

SLEEP_PERIOD = 1


def queue_hypno_lines(
    *,
    hypno_line_chooser: HypnoLineChooserFn,
    line_players: list[LinePlayer],
    hypno_line_mapping: dict[str, HypnoLine],
    hypno_lines_lock: multiprocessing.synchronize.Lock,
) -> None:
    """Queue HypnoLines from the generator to the line players.

    Args:
        hypno_line_chooser (HypnoLineChooserFn): A function that returns an iterator of HypnoLine objects.
        line_players (list[LinePlayer]): A list of LinePlayer instances to queue the HypnoLines to.
        hypno_line_mapping (dict[str, HypnoLine]): A mapping of line identifiers to HypnoLine objects.
        hypno_lines_lock (multiprocessing.synchronize.Lock): A lock to ensure thread-safe access to the hypno lines.
    """
    hypno_line_iterator = hypno_line_chooser(hypno_line_mapping, hypno_lines_lock)
    current_player_index = 0

    for hypno_line in hypno_line_iterator:
        # Ensure the hypno line has duration set
        if hypno_line.duration is None:
            try:
                hypno_line.set_duration()
            except FileNotFoundError:
                print(f"Audio file not ready for: {hypno_line.text}")
                continue

        current_player = line_players[current_player_index]

        # Wait for the current player's queue to have space
        while current_player.queue.full():
            time.sleep(0.1)

        current_player.queue.put(hypno_line)

        # Schedule the next assignment after this line's duration
        if hypno_line.duration:
            # Move to next player in round-robin fashion
            current_player_index = (current_player_index + 1) % len(line_players)

            # Wait for the duration of the current audio before queuing the next one
            time.sleep(hypno_line.duration)


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
                last_hypno_line = hypno_line
                yield hypno_line


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
