import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def test_launcher_targets_desktop_ui(self):
        source = (ROOT / "launch.py").read_text(encoding="utf-8")
        self.assertIn('UI_ENTRYPOINT = ROOT / "ui" / "app.py"', source)
        self.assertIn('subprocess.call([sys.executable, str(UI_ENTRYPOINT)], cwd=ROOT)', source)
        self.assertNotIn('ROOT / "run_command_center.py"', source)


if __name__ == "__main__":
    unittest.main()
