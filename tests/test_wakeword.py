from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class DummyConfig:

    def __init__(self, settings_dict):
        self._settings = settings_dict

    def get(self, key, default=None):
        return self._settings.get(key, default)


class DummyVoiceManager:

    def __init__(self):
        self.state = "idle"
        self._state_changed_listeners = []
        self.toggled_listening_count = 0

    def add_state_changed_listener(self, listener):
        self._state_changed_listeners.append(listener)

    def toggle_listening(self):
        self.toggled_listening_count += 1
        if self.state == "idle":
            self.state = "listening"
        else:
            self.state = "idle"
        for listener in self._state_changed_listeners:
            listener(self.state)


def test_wakeword_service_lifecycle():
    from backend.voice.wake_word import WakeWordService

    config = DummyConfig({"wake_word_enabled": True})
    voice_manager = DummyVoiceManager()

    service = WakeWordService(voice_manager, config)
    assert not service._is_running

    # Start and verify
    service.start()
    assert service._is_running

    # Pause and resume
    service.pause()
    assert service._paused

    service.resume()
    assert not service._paused

    # Stop and verify
    service.stop()
    assert not service._is_running
