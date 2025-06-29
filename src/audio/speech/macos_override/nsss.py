import objc
from AppKit import NSSpeechSynthesizer  # type: ignore
from Foundation import *  # type: ignore # noqa: F403
from PyObjCTools import AppHelper
from pyttsx3.voice import Voice


def buildDriver(proxy):  # type: ignore # noqa: N802
    return HypnoNSSpeechDriver.alloc().initWithProxy(proxy)  # type: ignore


class HypnoNSSpeechDriver(NSObject):  # type: ignore # noqa: F405
    @objc.python_method
    def initWithProxy(self, proxy):  # type: ignore # noqa: N802
        self = objc.super(HypnoNSSpeechDriver, self).init()  # type: ignore  # noqa: PLW0642
        if self:
            self._proxy = proxy
            self._tts = NSSpeechSynthesizer.alloc().initWithVoice_(None)  # type: ignore
            self._tts.setDelegate_(self)  # type: ignore
            # default rate
            self._tts.setRate_(200)  # type: ignore
            self._completed = True
        return self  # type: ignore

    def destroy(self):
        self._tts.setDelegate_(None)  # type: ignore
        del self._tts

    def onPumpFirst_(self, timer):  # type: ignore # noqa: N802, ARG002
        self._proxy.setBusy(False)  # type: ignore

    def startLoop(self):  # noqa: N802
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(0.0, self, "onPumpFirst:", None, False)  # type: ignore # noqa: F405, FBT003
        AppHelper.runConsoleEventLoop()  # type: ignore

    def endLoop(self):  # noqa: PLR6301, N802
        AppHelper.stopEventLoop()  # type: ignore

    def iterate(self):
        self._proxy.setBusy(False)  # type: ignore
        yield

    @objc.python_method
    def say(self, text):  # type: ignore
        self._proxy.setBusy(True)  # type: ignore
        self._completed = True
        self._proxy.notify("started-utterance")  # type: ignore
        self._tts.startSpeakingString_(text)  # type: ignore

    def stop(self):
        if self._proxy.isBusy():  # type: ignore
            self._completed = False
        self._tts.stopSpeaking()  # type: ignore

    @objc.python_method
    def _toVoice(self, attr):  # type: ignore # noqa: PLR6301, N802
        try:
            lang = attr["VoiceLocaleIdentifier"]  # type: ignore
        except KeyError:
            lang = attr["VoiceLanguage"]  # type: ignore
        return Voice(attr["VoiceIdentifier"], attr["VoiceName"], [lang], attr["VoiceGender"], attr["VoiceAge"])  # type: ignore

    @objc.python_method
    def getProperty(self, name):  # type: ignore # noqa: N802
        if name == "voices":
            return [
                self._toVoice(NSSpeechSynthesizer.attributesForVoice_(v))  # type: ignore
                for v in list(NSSpeechSynthesizer.availableVoices())  # type: ignore
            ]
        if name == "voice":
            return self._tts.voice()  # type: ignore
        if name == "rate":
            return self._tts.rate()  # type: ignore
        if name == "volume":
            return self._tts.volume()  # type: ignore
        raise KeyError("unknown property %s" % name)  # type: ignore # noqa: UP031

    @objc.python_method
    def setProperty(self, name, value):  # type: ignore # noqa: N802
        if name == "voice":
            # vol/rate gets reset, so store and restore it
            vol = self._tts.volume()  # type: ignore
            rate = self._tts.rate()  # type: ignore
            self._tts.setVoice_(value)  # type: ignore
            self._tts.setRate_(rate)  # type: ignore
            self._tts.setVolume_(vol)  # type: ignore
        elif name == "rate":
            self._tts.setRate_(value)  # type: ignore
        elif name == "volume":
            self._tts.setVolume_(value)  # type: ignore
        else:
            raise KeyError("unknown property %s" % name)  # type: ignore  # noqa: UP031

    @objc.python_method
    def save_to_file(self, text, filename):  # type: ignore
        self._proxy.setBusy(True)  # type: ignore
        self._completed = True
        url = Foundation.NSURL.fileURLWithPath_(filename)  # type: ignore # noqa: F405
        self._tts.startSpeakingString_toURL_(text, url)  # type: ignore

    def speechSynthesizer_didFinishSpeaking_(self, tts, success):  # type: ignore # noqa: N802, ARG002
        success = bool(self._completed)
        self._proxy.notify("finished-utterance", completed=success)  # type: ignore
        self._proxy.setBusy(False)  # type: ignore

    def speechSynthesizer_willSpeakWord_ofString_(self, tts, rng, text):  # type: ignore # noqa: N802, ARG002
        self._proxy.notify("started-word", location=rng.location, length=rng.length)  # type: ignore
