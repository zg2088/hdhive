"""Resolve Compose offline with synthetic config; never build/start containers."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import test_setup

ROOT = test_setup.ROOT


class DistributionTests(unittest.TestCase):
    def test_git_ignores_all_core_and_private_delivery_files(self):
        self.assertTrue((ROOT / ".gitignore").is_file(), "installer ignore policy is missing")
        if not shutil.which("git"):
            self.skipTest("git unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copyfile(ROOT / ".gitignore", root / ".gitignore")
            subprocess.run(["git", "-c", "init.templateDir=", "init", "-q", str(root)], check=True)
            ignored = [".env", ".env.local", "app/data/config.json", "app/bot.py",
                       "web/index.html", "hdhive_license/client.py", "server/main.py", "Dockerfile",
                       "copied/config.json", "copied/hdhive_oauth_token.json", "copied/115_cookie.json",
                       "x.session", "x.session-journal", "config.json.bak", "export.zip", "cert.pem",
                       ".setup-stage-any/config.json", "owner-delivered-image.tar", "__pycache__/x.pyc"]
            result = subprocess.run(["git", "-C", str(root), "check-ignore", "--stdin"],
                                    input="\n".join(ignored) + "\n", text=True, capture_output=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(set(result.stdout.splitlines()), set(ignored))
            from test_export import load_auditor
            result = subprocess.run(["git", "-C", str(root), "check-ignore", "--stdin"],
                                    input="\n".join(load_auditor().PUBLIC_FILES) + "\n",
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")

    def test_examples_and_docs_keep_source_private(self):
        self.assertTrue((ROOT / "README.md").is_file(), "Chinese private-image guide is missing")
        example = json.loads((ROOT / "config.example.json").read_text())
        for key in ("BOT_TOKEN", "WEB_PASSWORD", "TG_API_ID", "TG_API_HASH", "TG_PHONE",
                    "HDHIVE_CLIENT_ID", "HDHIVE_CLIENT_SECRET", "HDHIVE_API_KEY"):
            self.assertEqual(example[key], "")
        self.assertEqual(example["ADMIN_ID"], 0)
        keys = {line.split("=", 1)[0] for line in (ROOT / ".env.example").read_text().splitlines()
                if line and not line.startswith("#")}
        self.assertEqual(keys, {"API_PORT", "PANEL_ORIGIN", "TZ"})
        readme = (ROOT / "README.md").read_text()
        for required in ("不公开核心代码", "本仓库仅分发安装器", "激活码", "私有镜像",
                         "docker load -i owner-delivered-image.tar", "hdhive-official:licensed",
                         "--replace-config --acknowledge-stopped", "Secure Cookie",
                         "hdhive_license.supervisor activate", "不保证官方接受 localhost"):
            self.assertIn(required, readme)
        for forbidden in ("--build", "docker build", "ghcr.io/", "/root/", "license_admin"):
            self.assertNotIn(forbidden, readme)
        tls = (ROOT / "docs/HTTPS.md").read_text()
        self.assertIn("tls internal", tls)
        self.assertIn("不把 HTTP 升级成 HTTPS", tls)

    def test_compose_uses_only_local_licensed_image_and_loopback(self):
        self.assertTrue((ROOT / "compose.yaml").is_file(), "private-image Compose is missing")
        if not shutil.which("docker"):
            self.skipTest("Docker Compose unavailable")
        version = subprocess.run(["docker", "compose", "version"], capture_output=True)
        if version.returncode:
            self.skipTest("Docker Compose unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copyfile(ROOT / "compose.yaml", root / "compose.yaml")
            reader, _ = test_setup.SetupTests().answers(API_PORT="18787")
            test_setup.load_setup().generate(root, reader)
            clean_env = {"PATH": os.environ.get("PATH", ""), "HOME": temporary}
            command = ["docker", "compose", "--project-directory", str(root),
                       "--env-file", str(root / ".env"), "-f", str(root / "compose.yaml"),
                       "--profile", "listener", "config"]
            checked = subprocess.run(command + ["-q"], env=clean_env, capture_output=True)
            self.assertEqual(checked.returncode, 0, "Compose validation failed")
            result = subprocess.run(command + ["--format", "json"], env=clean_env, capture_output=True)
            self.assertEqual(result.returncode, 0, "Compose JSON resolution failed")
            services = json.loads(result.stdout)["services"]
            self.assertEqual(set(services), {"bot", "api", "listener"})
            for name, service in services.items():
                self.assertEqual(service["image"], "hdhive-official:licensed")
                self.assertEqual(service["pull_policy"], "never")
                self.assertNotIn("build", service)
                self.assertNotIn("container_name", service)
                self.assertNotIn("env_file", service)
                self.assertNotIn("privileged", service)
                self.assertEqual(service["restart"], "no")
                self.assertTrue(service["init"])
                self.assertEqual(service["cap_drop"], ["ALL"])
                self.assertEqual(service["security_opt"], ["no-new-privileges:true"])
                self.assertEqual(service["working_dir"], "/app/app")
                self.assertEqual(service["command"],
                                 ["python", "-m", "hdhive_license.supervisor", "run", name])
                self.assertEqual(len(service["volumes"]), 1)
                volume = service["volumes"][0]
                self.assertEqual(Path(volume["source"]), root / "app/data")
                self.assertEqual(volume["target"], "/app/app/data")
                self.assertFalse(volume.get("bind", {}).get("create_host_path", False))
                self.assertNotIn("docker.sock", str(service))
                self.assertNotIn("/app/web", str(service))
            self.assertEqual(services["listener"]["profiles"], ["listener"])
            self.assertNotIn("ports", services["bot"])
            self.assertNotIn("ports", services["listener"])
            port = services["api"]["ports"][0]
            self.assertEqual(port["host_ip"], "127.0.0.1")
            self.assertEqual(str(port["published"]), "18787")
            self.assertEqual(port["target"], 8787)
            for secret in (b"offline-secret", b"offline-test-only-password", b"123456:"):
                self.assertNotIn(secret, result.stdout)
            # Exercise the exact umask/exec entrypoint resolved by Compose.
            entrypoint = services["api"]["entrypoint"]
            destination = root / "private-runtime.json"
            opaque = 'literal $HOME $(not-executed); " single-quote\''
            code = "import pathlib,sys; pathlib.Path(sys.argv[1]).write_text(sys.argv[2])"
            process = subprocess.run([sys.executable, *entrypoint[1:], sys.executable, "-c",
                                      code, str(destination), opaque], capture_output=True)
            self.assertEqual(process.returncode, 0)
            self.assertEqual(destination.read_text(), opaque)
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
