#!/usr/bin/env python3
"""Start and steer Devin Cloud sessions via the v3 API.

Reads DEVIN_API_KEY (service user token) and DEVIN_ORG_ID from the repo's .env and
passes TINKER_API_KEY, HF_TOKEN, OPENAI_API_KEY, ANTHROPIC_API_KEY as per-session
secrets. Never prints secret values; output is limited to ids, urls and status.

  python3 tools/devin_cloud.py create --title T --prompt-file F [--repo ardahk/muselet] [--acu 200]
  python3 tools/devin_cloud.py msg <session_id> (--text "..." | --file F)
  python3 tools/devin_cloud.py status <session_id>
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.devin.ai/v3/organizations"
SESSION_SECRETS = ["TINKER_API_KEY", "HF_TOKEN", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]


def load_env() -> dict:
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def call(env: dict, method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"{API}/{env['DEVIN_ORG_ID']}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {env['DEVIN_API_KEY']}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        sys.exit(f"HTTP {e.code} on {method} {path}: {detail}")


def summary(s: dict) -> dict:
    return {k: s.get(k) for k in ("session_id", "url", "status", "status_detail", "title", "acus_consumed")}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("--title", required=True)
    c.add_argument("--prompt-file", required=True)
    c.add_argument("--repo", action="append", default=[])
    c.add_argument("--acu", type=int, default=None)
    c.add_argument("--mode", default="fusion")
    c.add_argument("--no-secrets", action="store_true")
    c.add_argument("--tag", action="append", default=[])
    m = sub.add_parser("msg")
    m.add_argument("session_id")
    g = m.add_mutually_exclusive_group(required=True)
    g.add_argument("--text")
    g.add_argument("--file")
    s = sub.add_parser("status")
    s.add_argument("session_id")
    lg = sub.add_parser("log")
    lg.add_argument("session_id")
    lg.add_argument("-n", type=int, default=3)
    a = ap.parse_args()

    env = load_env()
    missing = [k for k in ("DEVIN_API_KEY", "DEVIN_ORG_ID") if not env.get(k)]
    if missing:
        sys.exit(f"missing in .env: {', '.join(missing)}")

    if a.cmd == "create":
        body = {"prompt": Path(a.prompt_file).read_text(), "title": a.title,
                "session_secrets": [{"key": k, "value": env[k], "sensitive": True}
                                    for k in SESSION_SECRETS if env.get(k)]}
        if a.repo:
            body["repos"] = a.repo
        if a.acu:
            body["max_acu_limit"] = a.acu
        if a.mode:
            body["devin_mode"] = a.mode
        if a.no_secrets:
            body.pop("session_secrets")
        if a.tag:
            body["tags"] = a.tag
        print(json.dumps(summary(call(env, "POST", "/sessions", body)), indent=2))
    elif a.cmd == "log":
        items, cursor = [], None
        while True:
            page = call(env, "GET", f"/sessions/{a.session_id}/messages"
                        + (f"?after={cursor}" if cursor else ""))
            items += page.get("items", [])
            cursor = page.get("end_cursor")
            if not page.get("has_next_page") or not cursor:
                break
        for it in items[-a.n:]:
            print(f"--- [{it.get('source')}] {it.get('created_at', '')}\n{it.get('message', '')}\n")
    elif a.cmd == "msg":
        text = a.text if a.text is not None else Path(a.file).read_text()
        call(env, "POST", f"/sessions/{a.session_id}/messages", {"message": text})
        print(json.dumps({"session_id": a.session_id, "sent": True}))
    else:
        print(json.dumps(summary(call(env, "GET", f"/sessions/{a.session_id}")), indent=2))


if __name__ == "__main__":
    main()
