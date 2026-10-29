"""Source-free public export checks; never read a real installation."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_auditor():
    path = ROOT / "scripts/verify_public.py"
    if not path.is_file():
        raise AssertionError("public export auditor has not been implemented")
    spec = importlib.util.spec_from_file_location("public_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExportTests(unittest.TestCase):
    def test_candidate_contains_only_allowlisted_public_files(self):
        audit = load_auditor()
        self.assertEqual(audit.audit(ROOT), [])
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/verify_public.py")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("仅安装器", result.stdout)

    def test_allowlist_rejects_core_runtime_archives_and_symlinks(self):
        audit = load_auditor()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in audit.PUBLIC_FILES:
                file = root / relative
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("offline-public-fixture")
            self.assertEqual(audit.audit(root), [])
            for relative in ("app/bot.py", "web/index.html", "hdhive_license/client.py",
                             "server/main.py", "Dockerfile", "tests/core_fixture.py",
                             ".env", "owner-delivered-image.tar", "app/data/config.json"):
                with self.subTest(path=relative):
                    file = root / relative
                    file.parent.mkdir(parents=True, exist_ok=True)
                    file.write_text("must-not-export")
                    self.assertTrue(audit.audit(root))
                    file.unlink()
                    parent = file.parent
                    while parent != root and not any(parent.iterdir()):
                        parent.rmdir()
                        parent = parent.parent
            file = root / "README.md"
            file.unlink()
            file.symlink_to(root / "config.example.json")
            self.assertTrue(audit.audit(root))


if __name__ == "__main__":
    unittest.main()
