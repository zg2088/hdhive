"""Offline tests. All credential-shaped values are deliberately synthetic."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_setup():
    path = ROOT / "scripts/setup.py"
    if not path.exists():
        raise AssertionError("interactive setup has not been implemented")
    spec = importlib.util.spec_from_file_location("public_setup", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.setup = load_setup()

    def answers(self, **updates):
        values = {
            "ADMIN_ID": "123456", "BOT_TOKEN": "123456:" + "X" * 35,
            "TG_API_ID": "", "TG_API_HASH": "", "TG_PHONE": "",
            "WEB_USERNAME": "", "WEB_PASSWORD": "offline-test-only-password",
            "WEB_PASSWORD_CONFIRM": "offline-test-only-password",
            "HDHIVE_CLIENT_ID": "offline-client", "HDHIVE_CLIENT_SECRET": "offline-secret",
            "HDHIVE_API_KEY": "", "PANEL_ORIGIN": "", "API_PORT": "",
        }
        values.update(updates)
        calls = []
        def reader(key, prompt, secret):
            calls.append((key, secret))
            return values[key]
        return reader, calls

    def test_collects_typed_defaults_without_revealing_secrets(self):
        reader, calls = self.answers()
        config, deployment = self.setup.collect_settings(reader)
        self.assertEqual(config["ADMIN_ID"], 123456)
        self.assertEqual(config["TG_API_ID"], "")
        self.assertEqual(config["TG_PHONE"], "")
        self.assertEqual(config["WEB_USERNAME"], "admin")
        self.assertEqual(config["HDHIVE_REDIRECT_URI"], "https://localhost:8443/callback")
        self.assertEqual(deployment["API_PORT"], "8787")
        self.assertEqual(deployment["PANEL_ORIGIN"], "https://localhost:8443")
        self.assertTrue(config["UNLOCK_SAFE_MODE"])
        self.assertTrue(config["PREMIUM_FREE_NEED_APPROVAL"])
        self.assertFalse(config["AUTO_CHECKIN"])
        self.assertEqual(config["forward_rules"], [])
        self.assertEqual(config["HDHIVE_API_KEY"], "")
        for key in ("ADMIN_ID", "BOT_TOKEN", "TG_API_ID", "TG_API_HASH", "TG_PHONE",
                    "WEB_PASSWORD", "WEB_PASSWORD_CONFIRM", "HDHIVE_CLIENT_ID",
                    "HDHIVE_CLIENT_SECRET", "HDHIVE_API_KEY"):
            self.assertIn((key, True), calls)
        self.assertNotIn("BOT_TOKEN", deployment)
        self.assertNotIn("WEB_PASSWORD", deployment)

    def test_rejects_invalid_values_without_echoing_them(self):
        cases = [
            {"ADMIN_ID": "1.5"}, {"ADMIN_ID": "-1"}, {"ADMIN_ID": "0"},
            {"BOT_TOKEN": "not-a-token"}, {"BOT_TOKEN": "123456:" + "X" * 34},
            {"TG_API_ID": "1", "TG_API_HASH": ""},
            {"TG_API_ID": "0", "TG_API_HASH": "a" * 32},
            {"TG_API_ID": "7", "TG_API_HASH": "g" * 32},
            {"TG_API_ID": "", "TG_API_HASH": "a" * 32},
            {"TG_PHONE": "not-a-phone"}, {"WEB_PASSWORD": "short"},
            {"WEB_PASSWORD_CONFIRM": "mismatch"}, {"WEB_USERNAME": "bad\nname"},
            {"HDHIVE_CLIENT_ID": ""}, {"HDHIVE_CLIENT_SECRET": ""},
            {"HDHIVE_CLIENT_SECRET": " secret-not-trimmed "},
            {"HDHIVE_API_KEY": "new\nline"},
            {"PANEL_ORIGIN": "http://localhost:8443"},
            {"PANEL_ORIGIN": "https://example.org/callback"},
            {"PANEL_ORIGIN": "https://user:pass@example.org"},
            {"PANEL_ORIGIN": "https://example.org?query=1"},
            {"PANEL_ORIGIN": "https://example.org#fragment"},
            {"PANEL_ORIGIN": "https://example.org:99999"},
            {"PANEL_ORIGIN": "https://example.org:0"},
            {"PANEL_ORIGIN": "https://bad\\host"},
            {"PANEL_ORIGIN": "https://example.org\nmalicious"},
            {"API_PORT": "0"}, {"API_PORT": "65536"}, {"API_PORT": "8787;id"},
        ]
        for updates in cases:
            with self.subTest(field=next(iter(updates))):
                reader, _ = self.answers(**updates)
                with self.assertRaises(ValueError) as caught:
                    self.setup.collect_settings(reader)
                for value in updates.values():
                    if len(value) >= 10:
                        self.assertNotIn(value, str(caught.exception))

    def test_preserves_opaque_secrets_and_accepts_optional_telegram(self):
        secret = "opaque $HOME ${SHELL} $(not-executed) # \" ' unicode密钥"
        reader, _ = self.answers(TG_API_ID="7", TG_API_HASH="A" * 32,
                                 TG_PHONE="+15555550123", HDHIVE_CLIENT_SECRET=secret,
                                 PANEL_ORIGIN="https://panel.example.org", API_PORT="18787")
        config, deployment = self.setup.collect_settings(reader)
        self.assertEqual(config["HDHIVE_CLIENT_SECRET"], secret)
        self.assertEqual(config["TG_API_ID"], "7")
        self.assertEqual(config["TG_API_HASH"], "A" * 32)
        self.assertEqual(config["HDHIVE_REDIRECT_URI"], "https://panel.example.org/callback")
        self.assertEqual(deployment["API_PORT"], "18787")

    def test_generates_private_files_and_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "install"
            reader, _ = self.answers()
            self.setup.generate(target, reader)
            for path in (target, target / "app", target / "app/data"):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
            for path in (target / ".env", target / "app/data/config.json"):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            cfg = json.loads((target / "app/data/config.json").read_text())
            self.assertEqual(cfg["ADMIN_ID"], 123456)
            env = (target / ".env").read_text()
            self.assertIn("API_PORT=8787\n", env)
            self.assertNotIn(cfg["WEB_PASSWORD"], env)
            self.assertNotIn(cfg["BOT_TOKEN"], env)
            self.assertFalse((target / ".setup.lock").exists())
            self.assertFalse(list(target.glob(".setup-stage-*")))

    def test_existing_env_is_not_read_or_overwritten_and_no_prompts(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            env = target / ".env"
            env.write_text("do-not-read-or-modify")
            def forbidden_reader(*args):
                self.fail("must refuse before asking for secrets")
            with self.assertRaises(FileExistsError):
                self.setup.generate(target, forbidden_reader)
            self.assertEqual(env.read_text(), "do-not-read-or-modify")
            self.assertFalse((target / "app/data/config.json").exists())

    def test_existing_data_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            data = target / "app/data"
            data.mkdir(parents=True)
            sentinel = data / "existing.session"
            sentinel.write_text("offline-existing-sentinel")
            reader, _ = self.answers()
            with self.assertRaises(FileExistsError):
                self.setup.generate(target, reader)
            self.assertEqual(sentinel.read_text(), "offline-existing-sentinel")
            self.assertFalse((target / ".env").exists())

    def test_explicit_replacement_preserves_unrelated_runtime_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            reader, _ = self.answers()
            self.setup.generate(target, reader)
            sentinel = target / "app/data/existing.session"
            sentinel.write_text("offline-existing-sentinel")
            reader, _ = self.answers(ADMIN_ID="123457")
            self.setup.generate(target, reader, replace=True)
            cfg = json.loads((target / "app/data/config.json").read_text())
            self.assertEqual(cfg["ADMIN_ID"], 123457)
            self.assertEqual(sentinel.read_text(), "offline-existing-sentinel")
            self.assertFalse(list(target.rglob("*.bak")))

    def test_symlinks_are_rejected_even_with_replacement(self):
        for relative in ("app", "app/data", "app/data/config.json", ".env"):
            with self.subTest(target=relative), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                install = base / "install"
                outside = base / "outside"
                outside.mkdir()
                link = install / relative
                link.parent.mkdir(parents=True)
                link.symlink_to(outside, target_is_directory=True)
                reader, _ = self.answers()
                with self.assertRaises(OSError):
                    self.setup.generate(install, reader, replace=True)
                self.assertEqual(list(outside.iterdir()), [])

    def test_invalid_input_does_not_create_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            reader, _ = self.answers(PANEL_ORIGIN="http://unsafe.example.org")
            with self.assertRaises(ValueError):
                self.setup.generate(target, reader)
            self.assertFalse((target / ".env").exists())
            self.assertFalse((target / "app/data/config.json").exists())
            self.assertFalse((target / ".setup.lock").exists())

    def test_cancelled_input_removes_lock_without_secret_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            def cancel(*args):
                raise KeyboardInterrupt
            with self.assertRaises(KeyboardInterrupt):
                self.setup.generate(target, cancel)
            self.assertFalse((target / ".setup.lock").exists())
            self.assertFalse((target / ".env").exists())
            self.assertFalse((target / "app").exists())

    def test_existing_lock_refuses_second_wizard(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            lock = target / ".setup.lock"
            lock.write_text("offline-lock-sentinel")
            reader, calls = self.answers()
            with self.assertRaises(FileExistsError):
                self.setup.generate(target, reader)
            self.assertEqual(calls, [])
            self.assertEqual(lock.read_text(), "offline-lock-sentinel")

    def test_late_target_creation_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            base_reader, _ = self.answers()
            def reader(key, prompt, secret):
                if key == "API_PORT":
                    (target / ".env").write_text("offline-race-sentinel")
                return base_reader(key, prompt, secret)
            with self.assertRaises(FileExistsError):
                self.setup.generate(target, reader)
            self.assertEqual((target / ".env").read_text(), "offline-race-sentinel")
            self.assertFalse((target / "app/data/config.json").exists())
            self.assertFalse((target / ".setup.lock").exists())

    def test_permissive_umask_cannot_open_generated_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "install"
            reader, _ = self.answers()
            old = os.umask(0)
            try:
                self.setup.generate(target, reader)
            finally:
                os.umask(old)
            self.assertEqual(stat.S_IMODE((target / ".env").stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE((target / "app/data/config.json").stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE((target / "app/data").stat().st_mode), 0o700)


if __name__ == "__main__":
    unittest.main()
