from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CC_BASE_URL = "http://127.0.0.1:8000"
BG = "#0b0f14"
PANEL = "#111823"
PANEL2 = "#161f2b"
PANEL3 = "#1b2633"
LINE = "#273241"
TEXT = "#e8edf2"
MUTED = "#8c9aaa"
ACCENT = "#64b5f6"
SUCCESS = "#66bb6a"
ERROR = "#ef5350"
WARNING = "#ffca28"
CODE_BG = "#0a0d12"
HOVER = "#223042"
ACTIVE = "#21364a"
STAGES = ["crawl", "clean", "dedupe", "weight", "tokenize", "shard", "train", "export"]
