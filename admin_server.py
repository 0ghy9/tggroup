#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TG Links Manager - Admin Backend Server
Serves admin.html and provides API for link management + git deploy.
Only listens on 127.0.0.1 for security.
"""

import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

PORT = 8765
ROOT = os.path.dirname(os.path.abspath(__file__))
LINKS_FILE = os.path.join(ROOT, "data", "links.json")

# Cloudflare Pages config (loaded from gitignored config file)
_CF_CONFIG_FILE = os.path.join(ROOT, "cf_config.json")
_cf_config = {}
if os.path.exists(_CF_CONFIG_FILE):
    with open(_CF_CONFIG_FILE, "r", encoding="utf-8") as f:
        _cf_config = json.load(f)
CF_API_TOKEN = _cf_config.get("api_token", "")
CF_ACCOUNT_ID = _cf_config.get("account_id", "")
CF_PROJECT_NAME = _cf_config.get("project_name", "")
WRANGLER = _cf_config.get("wrangler", "")


class AdminHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/api/links":
            try:
                with open(LINKS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._json_response(200, data)
            except FileNotFoundError:
                self._json_response(404, {"error": "links.json not found"})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/api/links":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                links = json.loads(body)

                if not isinstance(links, list):
                    self._json_response(400, {"error": "Expected a JSON array"})
                    return

                os.makedirs(os.path.dirname(LINKS_FILE), exist_ok=True)
                with open(LINKS_FILE, "w", encoding="utf-8") as f:
                    json.dump(links, f, ensure_ascii=False, indent=2)

                self._json_response(200, {"success": True, "count": len(links)})
            except json.JSONDecodeError as e:
                self._json_response(400, {"error": f"Invalid JSON: {e}"})
            except Exception as e:
                self._json_response(500, {"error": str(e)})

        elif parsed.path == "/api/deploy":
            parts = []
            errors = []
            # GitHub Pages
            try:
                parts.append(self._git_deploy())
            except Exception as e:
                errors.append(f"GitHub: {e}")
            # Cloudflare Pages
            try:
                parts.append("\n--- Cloudflare Pages ---\n" + self._cf_deploy())
            except Exception as e:
                errors.append(f"Cloudflare: {e}")
            output = "\n".join(parts)
            if errors:
                self._json_response(200, {"success": True, "output": output, "warnings": errors})
            else:
                self._json_response(200, {"success": True, "output": output})
        else:
            self.send_error(404)

    def _json_response(self, code, data):
        body = json.dumps(data, ensure_ascii=False, indent=2)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def _git_deploy(self):
        """Git add, commit, and push to origin."""
        lines = []

        def run(cmd, cwd=ROOT):
            result = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True,
                timeout=60,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}
            )
            out = result.stdout.strip() + result.stderr.strip()
            if out:
                lines.append(out)
            if result.returncode != 0:
                raise RuntimeError(f"Command failed (exit {result.returncode}): {' '.join(cmd)}\n{out}")
            return out

        lines.append(">>> git add -A")
        run(["git", "add", "-A"])

        lines.append(">>> git commit")
        run(["git", "commit", "-m", "update links via admin dashboard"])

        lines.append(">>> git push origin main")
        run(["git", "push", "origin", "main"])

        return "\n".join(lines)

    def _cf_deploy(self):
        """Deploy static files to Cloudflare Pages via wrangler."""
        deploy_dir = tempfile.mkdtemp(prefix="cf_deploy_")
        try:
            # Copy static files for deployment
            shutil.copy(os.path.join(ROOT, "index.html"), deploy_dir)
            data_dir = os.path.join(deploy_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            shutil.copy(LINKS_FILE, data_dir)

            # Build environment with wrangler in PATH and CF credentials
            env = dict(os.environ)
            # Clear proxy to avoid connectivity issues
            for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
                env.pop(k, None)
            node_dir = os.path.dirname(WRANGLER)
            env["PATH"] = node_dir + ";" + env.get("PATH", "")
            env["CLOUDFLARE_API_TOKEN"] = CF_API_TOKEN
            env["CLOUDFLARE_ACCOUNT_ID"] = CF_ACCOUNT_ID

            result = subprocess.run(
                [WRANGLER, "pages", "deploy", deploy_dir,
                 "--project-name=" + CF_PROJECT_NAME, "--branch=main"],
                capture_output=True, text=True, timeout=120, env=env
            )

            out = result.stdout.strip()
            if result.returncode != 0:
                err = result.stderr.strip()
                raise RuntimeError(f"CF deploy failed (exit {result.returncode}):\n{out}\n{err}")
            return out
        finally:
            shutil.rmtree(deploy_dir, ignore_errors=True)

    def log_message(self, format, *args):
        # Suppress default logging, keep it clean
        pass


def main():
    server = http.server.HTTPServer(("127.0.0.1", PORT), AdminHandler)
    print(f"Admin server running at http://127.0.0.1:{PORT}/admin.html")
    print(f"Press Ctrl+C to stop.")
    print(f"Root directory: {ROOT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
