"""CLI tests use a real local pseudo-terminal, never Docker or a network."""
import errno
import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import tempfile
import time
import unittest
import test_setup

SCRIPT = test_setup.ROOT / "scripts/setup.py"


class CliTests(unittest.TestCase):
    def test_help_does_not_read_credentials(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"--replace-config", result.stdout)

    def test_redirected_input_is_rejected_without_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run([sys.executable, str(SCRIPT), "--directory", temporary],
                                    input=b"not-a-secret\n", capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(b"not-a-secret", result.stdout + result.stderr)
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_replacement_requires_explicit_stopped_acknowledgement(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--replace-config"],
                                input=b"", capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"--acknowledge-stopped", result.stderr)

    @unittest.skipUnless(os.name == "posix", "POSIX private files required")
    def test_real_interactive_run_hides_secret_input(self):
        setup = test_setup.load_setup()
        fixture = test_setup.SetupTests()
        reader, _ = fixture.answers()
        prompts = []
        def recording_reader(key, prompt, secret):
            value = reader(key, prompt, secret)
            prompts.append((prompt.encode(), value.encode(), secret))
            return value
        setup.collect_settings(recording_reader)
        with tempfile.TemporaryDirectory() as temporary:
            master, slave = pty.openpty()
            process = subprocess.Popen([sys.executable, str(SCRIPT), "--directory", temporary],
                                       stdin=slave, stdout=slave, stderr=slave)
            os.close(slave)
            transcript = b""
            pending = b""
            index = 0
            deadline = time.monotonic() + 12
            try:
                while time.monotonic() < deadline:
                    ready, _, _ = select.select([master], [], [], 0.1)
                    if ready:
                        try:
                            chunk = os.read(master, 65536)
                        except OSError as error:
                            if error.errno == errno.EIO:
                                break
                            raise
                        if not chunk:
                            break
                        transcript += chunk
                        pending += chunk
                        if index < len(prompts) and prompts[index][0] in pending:
                            prompt, value, _ = prompts[index]
                            pending = pending.split(prompt, 1)[1]
                            os.write(master, value + b"\n")
                            index += 1
                    elif process.poll() is not None:
                        break
                process.wait(timeout=2)
                self.assertEqual(index, len(prompts), "wizard did not finish all prompts")
                self.assertEqual(process.returncode, 0)
                self.assertTrue((Path(temporary) / "app/data/config.json").exists())
                for _, value, secret in prompts:
                    if secret and value:
                        self.assertNotIn(value, transcript, "terminal leaked a secret input")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                os.close(master)


if __name__ == "__main__":
    unittest.main()
