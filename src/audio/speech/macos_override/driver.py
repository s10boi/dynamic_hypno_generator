import weakref
from typing import final

from pyttsx3.driver import DriverProxy

from src.audio.speech.macos_override.nsss import buildDriver  # pyright: ignore[reportUnknownVariableType]


@final
class HypnoDriverProxy(DriverProxy):
    """Quick override of the DriverProxy class to fix issues with macOS TTS."""

    def __init__(self, engine, driverName, debug):  # pyright: ignore[reportMissingSuperCall, reportUnknownParameterType, reportMissingParameterType]  # noqa: ARG002, N803
        """Initialize the HypnoDriverProxy."""
        self._driver = buildDriver(weakref.proxy(self))
        # initialize refs
        self._engine = engine
        self._queue = []
        self._busy = True
        self._name = None
        self._iterator = None
        self._debug = debug
