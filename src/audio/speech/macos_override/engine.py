import weakref

from pyttsx3.engine import Engine

from . import driver

_activeEngines = weakref.WeakValueDictionary()  # type: ignore # noqa: N816


class HypnoEngine(Engine):
    """Quick override of the Engine class to fix issues with macOS TTS."""

    def __init__(self, driverName=None, debug=False):  # type: ignore # noqa: D107, N803, FBT002
        self.proxy = driver.HypnoDriverProxy(weakref.proxy(self), driverName, debug)  # type: ignore
        # initialize other vars
        self._connects = {}
        self._inLoop = False
        self._driverLoop = True
        self._debug = debug


def get_hypno_engine(driverName=None, debug=False):  # type: ignore # noqa: N803, FBT002
    """Quick override of the pyttsx3 init function to fix issues with macOS TTS."""
    eng = HypnoEngine(driverName, debug)
    _activeEngines[driverName] = eng

    return eng
