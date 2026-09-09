from __future__ import annotations
from threading import RLock

_lock = RLock()
_state = {"screen": "dashboard", "selected_dataset": None, "running": False, "message": "Ready"}

def get(key, default=None):
    with _lock:
        return _state.get(key, default)

def set(key, value):
    with _lock:
        _state[key] = value
        return value

def snapshot():
    with _lock:
        return dict(_state)
