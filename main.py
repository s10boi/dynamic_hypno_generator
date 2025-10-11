from __future__ import annotations

import argparse
import multiprocessing
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from pydantic import ValidationError
from pydub import AudioSegment
import numpy as np
from pedalboard import Pedalboard, PitchShift, Gain, Delay, Mix  # offline effect processing

from src.audio.line_player import LinePlayer
from src.audio.repeating_player import RepeatingAudioPlayer
from src.audio.tts import generate_audio, generate_lines_once  # added generate_lines_once
from src.config import Config, read_args
from src.hypno_queue import (
    get_random_lines,
    get_sequential_lines,
    get_sequential_refreshing_lines,
    get_shuffled_lines,
    queue_hypno_lines,
)
from src.log import configure_logger
from src.hypno_line import HypnoLine, clean_line  # new import for mix ordering

if TYPE_CHECKING:
    from src.hypno_queue import (
        HypnoLineChooserFn,
    )

DEFAULT_CONFIG_PATH = Path("./config.json")
DEFAULT_TEXT_PATH = Path("./lines.txt")
BACKGROUND_CHUNK_SIZE = 8000
LINE_CHUNK_SIZE = 96_000
LINE_DIR = Path("./import/lines")

BACKGROUND_AUDIO: dict[str, Path] = {
    "tone": Path("./import/background/tone.wav"),
    "noise": Path("./import/background/noise.wav"),
}

LINE_CHOOSERS: dict[str, HypnoLineChooserFn] = {
    "sequential": get_sequential_lines,
    "sequential_refreshing": get_sequential_refreshing_lines,
    "shuffled": get_shuffled_lines,
    "random": get_random_lines,
}


# Helper to apply a HypnoLineChooserFn exactly once to collect a unique ordered list
# (the chooser functions are designed to be infinite streams)
def _get_unique_line_order_for_mix(
    *,
    hypno_line_chooser: HypnoLineChooserFn,
    hypno_line_mapping: dict[str, HypnoLine],
) -> list[HypnoLine]:
    if not hypno_line_mapping:
        return []

    manager = multiprocessing.Manager()
    lock = manager.Lock()  # chooser API expects a multiprocessing lock

    iterator = hypno_line_chooser(hypno_line_mapping, lock)

    needed = len(hypno_line_mapping)
    seen: set[str] = set()
    ordered: list[HypnoLine] = []

    # Safeguard to avoid infinite loops in case of unexpected chooser behaviour
    max_iterations = needed * 20
    while len(seen) < needed and max_iterations > 0:
        hypno_line = next(iterator)
        if hypno_line.text not in seen:
            ordered.append(hypno_line)
            seen.add(hypno_line.text)
        max_iterations -= 1

    if len(ordered) < needed:
        logger.warning(
            "Did not collect all lines via chooser (collected {collected}/{needed}). Falling back to remaining lines in insertion order.",
            collected=len(ordered),
            needed=needed,
        )
        # Append any missing lines in the original mapping order
        for text, line in hypno_line_mapping.items():
            if text not in seen:
                ordered.append(line)
    return ordered


def render_full_mix(
    *,
    lines_dir: Path,
    background_path: Path | None,
    mantra_path: Path | None,
    output_path: Path,
    text_filepath: Path,
    hypno_line_chooser: HypnoLineChooserFn,
    mantra_start_delay: float = 0.0,
    initial_line_delay: float = 0.0,
    initial_pitch_shift: float = 0.0,
    max_echoes: int = 0,
    echo_delay: float = 0.0,
) -> None:
    """Render a full static mix of all line audio files ordered via the configured line chooser.

    Added: offline application of pitch shift + echo chain mirroring realtime playback,
    initial silence respecting `initial_line_delay`, and mantra looping.
    """
    if not text_filepath.exists():
        logger.error(f"Text file {text_filepath} not found; cannot render mix.")
        return

    # Build unique ordered list of raw lines (with pause directives intact) from file
    lines: list[str] = []
    with text_filepath.open(encoding="utf-8") as f:
        for raw in f:
            if (clean := clean_line(raw)) and clean not in lines:
                lines.append(clean)

    generated_mapping = generate_lines_once(lines, lines_dir)
    hypno_line_mapping: dict[str, HypnoLine] = {
        line: generated_mapping.get(line) or HypnoLine.from_text(line, lines_dir) for line in lines
    }

    ordered_lines = _get_unique_line_order_for_mix(
        hypno_line_chooser=hypno_line_chooser,
        hypno_line_mapping=hypno_line_mapping,
    )
    if not ordered_lines:
        logger.error("No hypno lines available to render.")
        return

    # Helper: process a single line with pitch + echoes (sequential, no overlap with next line) offline
    max_tail_seconds = max_echoes * echo_delay if max_echoes > 0 else 0.0

    def _process_line(seg: AudioSegment) -> AudioSegment:
        if max_echoes <= 0 and abs(initial_pitch_shift) < 1e-6:
            return seg  # nothing to do
        try:
            frame_rate = seg.frame_rate
            channels = seg.channels
            samples = np.array(seg.get_array_of_samples())
            if channels > 1:
                samples = samples.reshape((-1, channels))
            else:
                samples = samples.reshape((-1, 1))
            samples = samples.astype(np.float32) / (2 ** 15)
            samples = samples.T  # shape: (channels, n)

            # Pad tail for echoes
            if max_tail_seconds > 0:
                pad_len = int(frame_rate * max_tail_seconds)
                if pad_len > 0:
                    samples = np.pad(samples, ((0, 0), (0, pad_len)))  # type: ignore[arg-type]

            boards = [Pedalboard([PitchShift(semitones=initial_pitch_shift)])]
            for i in range(1, max_echoes + 1):
                boards.append(
                    Pedalboard([
                        PitchShift(semitones=initial_pitch_shift - (i * 0.5)),
                        Gain(gain_db=-12 * i),
                        Delay(delay_seconds=i * echo_delay, mix=0.5),
                    ])
                )
            mix_board = Pedalboard([Mix(boards)]) if len(boards) > 1 else boards[0]
            processed = mix_board(samples, frame_rate)
            # Clip & convert back
            processed = np.clip(processed, -1.0, 1.0)
            processed = (processed.T * (2 ** 15 - 1)).astype(np.int16).tobytes()
            return AudioSegment(
                data=processed,
                sample_width=2,
                frame_rate=frame_rate,
                channels=channels,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed processing line effects offline: {exc}; using original line.")
            return seg

    # Concatenate with processing & initial delay
    full_lines = AudioSegment.silent(duration=int(initial_line_delay * 1000))
    current_position_ms = int(initial_line_delay * 1000)
    for hypno_line in ordered_lines:
        if not hypno_line.filepath.exists():
            logger.warning(f"Missing audio file for line '{hypno_line.text}': {hypno_line.filepath}")
            continue
        try:
            seg = AudioSegment.from_file(hypno_line.filepath)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to load audio for line '{hypno_line.text}': {exc}")
            continue
        dry_len_ms = len(seg)
        processed_with_echoes = _process_line(seg)
        # Ensure base mix is long enough to overlay processed audio including its echo tail
        end_required = current_position_ms + len(processed_with_echoes)
        if len(full_lines) < end_required:
            full_lines += AudioSegment.silent(duration=end_required - len(full_lines))
        full_lines = full_lines.overlay(processed_with_echoes, position=current_position_ms)
        # Advance only by the dry line length so echoes ring underneath next line (maintain rhythm)
        current_position_ms += dry_len_ms

    if len(full_lines) == 0:
        logger.error("Empty mix after processing; aborting.")
        return

    # Background overlay (loop)
    if background_path and background_path.exists():
        try:
            background = AudioSegment.from_file(background_path)
            if len(background) < len(full_lines):
                background = background * (len(full_lines) // len(background) + 1)
            background = background[: len(full_lines)]
            full_lines = full_lines.overlay(background - 10)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to process background audio '{background_path}': {exc}")

    # Mantra overlay (loop after delay)
    if mantra_path and mantra_path.exists():
        try:
            mantra = AudioSegment.from_file(mantra_path)
            delay_ms = int(mantra_start_delay * 1000)
            if delay_ms >= len(full_lines):
                logger.warning(
                    f"Mantra start delay ({mantra_start_delay}s) >= mix length ({len(full_lines)/1000:.2f}s); skipping mantra.",
                )
            else:
                remaining_ms = len(full_lines) - delay_ms
                loops_needed = (remaining_ms + len(mantra) - 1) // len(mantra)
                mantra_looped = (mantra * loops_needed)[:remaining_ms]
                full_lines = full_lines.overlay(mantra_looped - 5, position=delay_ms)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to process mantra audio '{mantra_path}': {exc}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        full_lines.export(output_path, format=output_path.suffix.lstrip('.'))
        logger.info(
            "Exported full mix to %s (duration %.2fs)",
            output_path,
            len(full_lines) / 1000.0,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to export full mix to {output_path}: {exc}")


def read_args_with_render(default_config_path=DEFAULT_CONFIG_PATH, default_text_path=DEFAULT_TEXT_PATH):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-filepath", type=Path, default=default_config_path, help="Path to config file")
    parser.add_argument("--text-filepath", type=Path, default=default_text_path, help="Path to lines text file")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--render-mix", action="store_true", help="Render all lines, tone, and mantra into one file")
    parser.add_argument("--mix-output", type=str, default="full_mix.wav", help="Output file for the mix")
 
    return parser.parse_args()


def main() -> None:
    # =====
    # SETUP
    # =====
    args = read_args_with_render(
        default_config_path=DEFAULT_CONFIG_PATH,
        default_text_path=DEFAULT_TEXT_PATH,
    )

    configure_logger(debug=args.debug)

    # Load configuration
    try:
        config = Config.from_args(
            json_filepath=args.config_filepath,
            available_backgrounds=BACKGROUND_AUDIO.keys(),
            available_line_choosers=LINE_CHOOSERS.keys(),
        )
    except (FileNotFoundError, ValidationError) as e:
        logger.critical(
            f"Failed to load configuration: {e}. Please check the configuration file at {args.config_filepath}.",
        )
        sys.exit(1)

    if args.render_mix:
        logger.info("Rendering full mix using line chooser '%s'", config.line_chooser)
        render_full_mix(
            lines_dir=LINE_DIR,
            background_path=BACKGROUND_AUDIO.get(config.background_audio),
            mantra_path=Path(config.mantra_filepath) if config.mantra_filepath else None,
            output_path=Path(args.mix_output),
            text_filepath=args.text_filepath,
            hypno_line_chooser=LINE_CHOOSERS[config.line_chooser],
            mantra_start_delay=config.mantra_start_delay,
            initial_line_delay=config.initial_line_delay,
            initial_pitch_shift=config.initial_pitch_shift,
            max_echoes=config.max_echoes,
            echo_delay=config.echo_delay,
        )
        return

    # =====================
    # HYPNO LINE GENERATION
    # =====================
    # Start generating audio files from the lines in the source text file
    if not args.text_filepath.exists():
        logger.critical(f"Text file {args.text_filepath} not found. Please ensure it exists.")
        sys.exit(1)

    manager = multiprocessing.Manager()
    hypno_line_mapping = manager.dict()
    hypno_lines_lock = manager.Lock()

    audio_generator_process = multiprocessing.Process(
        target=generate_audio,
        kwargs={
            "text_filepath": args.text_filepath,
            "output_audio_dir": LINE_DIR,
            "hypno_line_mapping": hypno_line_mapping,
            "hypno_lines_lock": hypno_lines_lock,
            # needed because the audio generator process is a separate process, so the logger needs to be set up again
            "debug": args.debug,
        },
        daemon=True,
    )

    audio_generator_process.start()

    # Wait for the audio generator to finish generating lines the first time
    while not hypno_line_mapping:
        time.sleep(0.1)

    # ================
    # BACKGROUND AUDIO
    # ================
    if config.background_audio:
        background_player = RepeatingAudioPlayer(audio_filepath=BACKGROUND_AUDIO[config.background_audio])
        background_player_thread = threading.Thread(
            target=background_player.play_audio_file,
            kwargs={"chunk_size": BACKGROUND_CHUNK_SIZE},
            daemon=True,
        )
        background_player_thread.start()

        # If there's a background audio file, delay before starting to play the hypno lines
        time.sleep(config.initial_line_delay)

    # ===================
    # HYPNO LINE PLAYBACK
    # ===================
    # Two line players are needed - one starting just after the first line is played, but while it's still playing the
    # echoes
    line_players = [
        LinePlayer.from_config(config),
        LinePlayer.from_config(config),
    ]

    filepath_queue_thread = threading.Thread(
        target=queue_hypno_lines,
        kwargs={
            "hypno_line_chooser": LINE_CHOOSERS[config.line_chooser],  # <-- use config value here
            "line_players": line_players,
            "hypno_line_mapping": hypno_line_mapping,
            "hypno_lines_lock": hypno_lines_lock,
        },
        daemon=True,
    )
    filepath_queue_thread.start()

    for line_player in line_players:
        line_player_thread = threading.Thread(
            target=line_player.play_audio_files,
            kwargs={
                "chunk_size": LINE_CHUNK_SIZE,
                "max_delay": config.max_echoes * config.echo_delay,
            },
        )
        line_player_thread.start()

        # ================
    # MANTRA PLAYBACK
    # ================
    if config.mantra_filepath:
        time.sleep(config.mantra_start_delay)

        mantra_player = RepeatingAudioPlayer(audio_filepath=config.mantra_filepath)
        mantra_player_thread = threading.Thread(
            target=mantra_player.play_audio_file,
            kwargs={"chunk_size": BACKGROUND_CHUNK_SIZE},
            daemon=True,
        )
        mantra_player_thread.start()

if __name__ == "__main__":
    main()
