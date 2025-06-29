import weakref

from pyttsx3.driver import DriverProxy

from src.audio.speech.macos_override.nsss import buildDriver  # type: ignore


class HypnoDriverProxy(DriverProxy):
    """Quick override of the DriverProxy class to fix issues with macOS TTS."""

    def __init__(self, engine, driverName, debug):  # type: ignore  # noqa: D107, N803, ARG002
        self._driver = buildDriver(weakref.proxy(self))  # type: ignore
        # initialize refs
        self._engine = engine
        self._queue = []
        self._busy = True
        self._name = None
        self._iterator = None
        self._debug = debug
