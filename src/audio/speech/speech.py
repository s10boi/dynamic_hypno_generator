import sys

import pyttsx3


def get_engine() -> pyttsx3.Engine:
    """Overrides default pyttsx3 engine to fix issues with macOS TTS."""
    if sys.platform == "darwin":
        from src.audio.speech.macos_override.engine import get_hypno_engine  # type: ignore  # noqa: PLC0415

        engine = get_hypno_engine()
    else:
        engine = pyttsx3.init()  # type: ignore

    engine.setProperty("rate", 110)
    engine.setProperty("volume", 0.8)

    return engine
