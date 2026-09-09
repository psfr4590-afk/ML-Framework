from __future__ import annotations
from collections import defaultdict
from typing import Any, Callable

_handlers: dict[str, list[Callable[[Any], None]]] = defaultdict(list)

def on(name: str, handler: Callable[[Any], None]) -> Callable[[Any], None]:
    _handlers[name].append(handler)
    return handler

def emit(name: str, payload: Any = None) -> None:
    for handler in tuple(_handlers.get(name, ())):
        handler(payload)

def clear(name: str | None = None) -> None:
    if name is None:
        _handlers.clear()
    else:
        _handlers.pop(name, None)
