from __future__ import annotations

NAV_ITEMS = [
    ("dashboard", "Dashboard"),
    ("dataset", "Datasets"),
    ("sources", "Sources"),
    ("crawler", "Crawler"),
    ("pipeline", "Pipeline"),
    ("training", "Training"),
    ("outputs", "Outputs"),
    ("diagnostics", "Diagnostics"),
    ("logs", "Logs"),
    ("system", "System"),
    ("configuration", "Configuration"),
    ("credentials", "Credentials"),
    ("command_center", "Command Center"),
]

def current_screen() -> str:
    from . import state
    return str(state.get("screen", "dashboard"))

def navigate(screen: str) -> str:
    from . import state
    from .events import emit
    valid = {name for name, _ in NAV_ITEMS}
    if screen not in valid:
        raise ValueError(f"Unknown UI screen: {screen}")
    state.set("screen", screen)
    emit("navigation", screen)
    return screen
