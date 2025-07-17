import multiprocessing
from pathlib import Path

import pytest

from src.hypno_line import HypnoLine
from src.hypno_queue import get_random_lines, get_sequential_lines, get_sequential_refreshing_lines, get_shuffled_lines


@pytest.fixture
def lock() -> multiprocessing.synchronize.Lock:  # pyright: ignore[reportAttributeAccessIssue, reportUnknownParameterType]
    """Fixture to provide a multiprocessing lock."""
    manager = multiprocessing.Manager()
    return manager.Lock()


# SEQUENTIAL LINES TESTS
# ======================
def test_get_sequential_lines_single(lock: multiprocessing.synchronize.Lock) -> None:  # pyright: ignore[reportAttributeAccessIssue, reportUnknownParameterType]
    hypno_line = HypnoLine(text="1", filepath=Path("1.wav"))

    mapping: dict[str, HypnoLine] = {
        "1": hypno_line,
    }

    line_generator = get_sequential_lines(hypno_line_mapping=mapping, hypno_lines_lock=lock)  # pyright: ignore[reportUnknownArgumentType]

    # Checking that the same HypnoLine instance is returned
    assert next(line_generator) == hypno_line
    assert next(line_generator) == hypno_line


def test_get_sequential_lines_multiple(lock: multiprocessing.synchronize.Lock) -> None:  # pyright: ignore[reportAttributeAccessIssue, reportUnknownParameterType]
    hypno_line1 = HypnoLine(text="1", filepath=Path("1.wav"))
    hypno_line2 = HypnoLine(text="2", filepath=Path("2.wav"))

    mapping: dict[str, HypnoLine] = {
        "1": hypno_line1,
        "2": hypno_line2,
    }

    line_generator = get_sequential_lines(hypno_line_mapping=mapping, hypno_lines_lock=lock)  # pyright: ignore[reportUnknownArgumentType]

    # Checking that the generator returns the correct HypnoLines in order
    assert next(line_generator) == hypno_line1
    assert next(line_generator) == hypno_line2
    assert next(line_generator) == hypno_line1  # Should loop back to the first line


def test_get_sequential_lines_changing_lines(lock: multiprocessing.synchronize.Lock) -> None:  # pyright: ignore[reportAttributeAccessIssue, reportUnknownParameterType]
    hypno_line1 = HypnoLine(text="1", filepath=Path("1.wav"))
    hypno_line2 = HypnoLine(text="2", filepath=Path("2.wav"))

    mapping: dict[str, HypnoLine] = {
        "1": hypno_line1,
        "2": hypno_line2,
    }

    line_generator = get_sequential_lines(hypno_line_mapping=mapping, hypno_lines_lock=lock)  # pyright: ignore[reportUnknownArgumentType]

    assert next(line_generator) == hypno_line1

    # Change the mapping to a new set of lines
    hypno_line3 = HypnoLine(text="3", filepath=Path("3.wav"))
    mapping["3"] = hypno_line3

    # The generator should continue the current sequence and finish it before starting the new line
    assert next(line_generator) == hypno_line2
    assert next(line_generator) == hypno_line1  # Should loop back to the first
    assert next(line_generator) == hypno_line2  # Now it should return the second again
    assert next(line_generator) == hypno_line3  # Should loop back to the first again


# SEQUENTIAL REFRESHING LINES TESTS
# =================================
def test_get_sequential_refreshing_lines_single(lock: multiprocessing.synchronize.Lock) -> None:  # pyright: ignore[reportAttributeAccessIssue, reportUnknownParameterType]
    hypno_line = HypnoLine(text="1", filepath=Path("1.wav"))

    mapping: dict[str, HypnoLine] = {
        "1": hypno_line,
    }

    line_generator = get_sequential_refreshing_lines(hypno_line_mapping=mapping, hypno_lines_lock=lock)  # pyright: ignore[reportUnknownArgumentType]

    # Checking that the same HypnoLine instance is returned
    assert next(line_generator) == hypno_line
    assert next(line_generator) == hypno_line


def test_get_sequential_refreshing_lines_multiple(lock: multiprocessing.synchronize.Lock) -> None:  # pyright: ignore[reportAttributeAccessIssue, reportUnknownParameterType]
    hypno_line1 = HypnoLine(text="1", filepath=Path("1.wav"))
    hypno_line2 = HypnoLine(text="2", filepath=Path("2.wav"))

    mapping: dict[str, HypnoLine] = {
        "1": hypno_line1,
        "2": hypno_line2,
    }

    line_generator = get_sequential_refreshing_lines(hypno_line_mapping=mapping, hypno_lines_lock=lock)  # pyright: ignore[reportUnknownArgumentType]

    # Checking that the generator returns the correct HypnoLines in order
    assert next(line_generator) == hypno_line1
    assert next(line_generator) == hypno_line2
    assert next(line_generator) == hypno_line1  # Should loop back to the first


def test_get_sequential_refreshing_lines_changing_lines(lock: multiprocessing.synchronize.Lock) -> None:  # pyright: ignore[reportAttributeAccessIssue, reportUnknownParameterType]
    hypno_line1 = HypnoLine(text="1", filepath=Path("1.wav"))
    hypno_line2 = HypnoLine(text="2", filepath=Path("2.wav"))

    mapping: dict[str, HypnoLine] = {
        "1": hypno_line1,
        "2": hypno_line2,
    }

    line_generator = get_sequential_refreshing_lines(hypno_line_mapping=mapping, hypno_lines_lock=lock)  # pyright: ignore[reportUnknownArgumentType]

    assert next(line_generator) == hypno_line1
    # Change the mapping to a new set of lines

    hypno_line3 = HypnoLine(text="3", filepath=Path("3.wav"))
    mapping["3"] = hypno_line3

    # The generator should immediately start the new sequence
    assert next(line_generator) == hypno_line1
    assert next(line_generator) == hypno_line2
    assert next(line_generator) == hypno_line3


# SHUFFLED LINES TESTS
# ====================
def test_get_shuffled_lines_single(lock: multiprocessing.synchronize.Lock) -> None:  # pyright: ignore[reportAttributeAccessIssue, reportUnknownParameterType]
    hypno_line = HypnoLine(text="1", filepath=Path("1.wav"))

    mapping: dict[str, HypnoLine] = {
        "1": hypno_line,
    }

    line_generator = get_shuffled_lines(hypno_line_mapping=mapping, hypno_lines_lock=lock)  # pyright: ignore[reportUnknownArgumentType]

    # Checking that the same HypnoLine instance is returned even though it's a repeat (as it's the only one)
    assert next(line_generator) == hypno_line
    assert next(line_generator) == hypno_line


def test_get_shuffled_lines_no_repeat_line(lock: multiprocessing.synchronize.Lock) -> None:  # pyright: ignore[reportAttributeAccessIssue, reportUnknownParameterType]
    hypno_line1 = HypnoLine(text="1", filepath=Path("1.wav"))
    hypno_line2 = HypnoLine(text="2", filepath=Path("2.wav"))

    mapping: dict[str, HypnoLine] = {
        "1": hypno_line1,
        "2": hypno_line2,
    }

    line_generator = get_shuffled_lines(hypno_line_mapping=mapping, hypno_lines_lock=lock)  # pyright: ignore[reportUnknownArgumentType]

    # Checking that the generator never returns the same HypnoLine twice in a row
    for _ in range(1000):  # Check multiple iterations
        initial_line = next(line_generator)
        assert next(line_generator) != initial_line


# RANDOM LINES TESTS
# ==================
def test_get_random_lines_single(lock: multiprocessing.synchronize.Lock) -> None:  # pyright: ignore[reportAttributeAccessIssue, reportUnknownParameterType]
    hypno_line = HypnoLine(text="1", filepath=Path("1.wav"))

    mapping: dict[str, HypnoLine] = {
        "1": hypno_line,
    }

    line_generator = get_random_lines(hypno_line_mapping=mapping, hypno_lines_lock=lock)  # pyright: ignore[reportUnknownArgumentType]

    # Checking that the same HypnoLine instance is returned even though it's a repeat (as it's the only one)
    assert next(line_generator) == hypno_line
    assert next(line_generator) == hypno_line


def test_get_random_lines_multiple(lock: multiprocessing.synchronize.Lock) -> None:  # pyright: ignore[reportAttributeAccessIssue, reportUnknownParameterType]
    hypno_line1 = HypnoLine(text="1", filepath=Path("1.wav"))
    hypno_line2 = HypnoLine(text="2", filepath=Path("2.wav"))

    mapping: dict[str, HypnoLine] = {
        "1": hypno_line1,
        "2": hypno_line2,
    }

    line_generator = get_random_lines(hypno_line_mapping=mapping, hypno_lines_lock=lock)  # pyright: ignore[reportUnknownArgumentType]

    # Checking that the generator never returns the same HypnoLine twice in a row
    for _ in range(1000):  # Check multiple iterations
        initial_line = next(line_generator)
        assert next(line_generator) != initial_line
