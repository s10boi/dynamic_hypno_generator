from typing import cast

import pyttsx3  # pyright: ignore[reportMissingTypeStubs]


def get_engine() -> pyttsx3.Engine:
    engine = cast("pyttsx3.Engine", pyttsx3.init())

    engine.setProperty("rate", 110)
    engine.setProperty("volume", 0.8)

    return engine
