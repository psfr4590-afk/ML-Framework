"""Tkinter desktop application for the Model Lab control surface."""
from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from tkinter import ttk
from pathlib import Path

from .config import BG, PANEL, TEXT, MUTED, ACCENT, SUCCESS, ERROR, STAGES
from . import navigation, state

ROOT = Path(__file__).resolve().parents[2]
WINDOW_SIZE = "1100x720"


class Application(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Model Lab")
        self.geometry(WINDOW_SIZE)
        self.configure(bg=BG)
        self._build()

    def _build(self) -> None:
        header = tk.Frame(self, bg=PANEL, padx=20, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="M²S CONTROL SURFACE", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(header, text="Model Lab", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 20, "bold")).pack(anchor="w")

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=20)

        nav = tk.Frame(body, bg=PANEL, width=180)
        nav.pack(side="left", fill="y", padx=(0, 16))
        nav.pack_propagate(False)
        for screen, label in navigation.NAV_ITEMS:
            tk.Button(nav, text=label, anchor="w", relief="flat", bd=0,
                      bg=PANEL, fg=TEXT, activebackground=PANEL, activeforeground=ACCENT,
                      command=lambda s=screen: self._select(s)).pack(fill="x", padx=8, pady=3)

        content = tk.Frame(body, bg=BG)
        content.pack(side="left", fill="both", expand=True)
        tk.Label(content, text="Pipeline", bg=BG, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(content, text="End-to-end training stages", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 18))

        for stage in STAGES:
            row = tk.Frame(content, bg=PANEL, padx=12, pady=10)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=stage.upper(), bg=PANEL, fg=TEXT,
                     font=("Consolas", 10, "bold"), width=12, anchor="w").pack(side="left")
            tk.Label(row, text="READY", bg=PANEL, fg=SUCCESS,
                     font=("Consolas", 9, "bold")).pack(side="right")

        state.set("screen", "dashboard")

    def _select(self, screen: str) -> None:
        navigation.navigate(screen)
        state.set("message", f"Selected {screen}")


def main() -> int:
    Application().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
