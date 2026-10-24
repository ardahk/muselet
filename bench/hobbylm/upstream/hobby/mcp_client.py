"""Minimal stdio JSON-RPC client for mcp-server-macos-use (same wire format as the repo's scripts/test_mcp.py)."""
from __future__ import annotations

import os

import json
import queue
import re
import subprocess
import threading
from pathlib import Path

ROOT = Path(os.environ.get('HOBBY_HOME', Path(__file__).resolve().parents[1]))  # repo root
SERVER_DIR = ROOT / 'vendor' / 'mcp-server-macos-use'
SERVER_BIN = SERVER_DIR / '.build' / 'release' / 'mcp-server-macos-use'
SERVER_COMMIT = '205c8880e8c06fa96a3e3a859e6edca728eb6c47'


class MCP:
    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout
        self.proc = subprocess.Popen([str(SERVER_BIN)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.stderr: list[str] = []
        self._q: queue.Queue = queue.Queue()
        threading.Thread(target=self._drain_err, daemon=True).start()
        threading.Thread(target=self._drain_out, daemon=True).start()
        self._id = 0
        init = self.request('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
                                           'clientInfo': {'name': 'hobbylm-macos-agent', 'version': '0.1'}})
        self.server_info = init.get('result', {}).get('serverInfo')
        self._send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        self.tools = [t['name'] for t in self.request('tools/list', {})['result']['tools']]

    def _drain_err(self):
        for line in self.proc.stderr:
            self.stderr.append(line.decode('utf-8', 'replace').rstrip())

    def _drain_out(self):
        for line in self.proc.stdout:
            line = line.strip()
            if line:
                try:
                    self._q.put(json.loads(line))
                except json.JSONDecodeError:
                    pass

    def _send(self, msg: dict):
        self.proc.stdin.write((json.dumps(msg) + '\n').encode())
        self.proc.stdin.flush()

    def request(self, method: str, params: dict) -> dict:
        self._id += 1
        rid = self._id
        self._send({'jsonrpc': '2.0', 'id': rid, 'method': method, 'params': params})
        while True:
            msg = self._q.get(timeout=self.timeout)
            if msg.get('id') == rid:
                return msg

    def call(self, tool: str, args: dict) -> dict:
        """Returns {'summary': text, 'fields': {key: value}, 'is_error': bool, 'file_text': str|None}."""
        resp = self.request('tools/call', {'name': tool, 'arguments': args})
        if 'error' in resp:
            return {'summary': json.dumps(resp['error']), 'fields': {}, 'is_error': True, 'file_text': None}
        res = resp['result']
        text = '\n'.join(c.get('text', '') for c in res.get('content', []) if c.get('type') == 'text')
        fields = {}
        for line in text.splitlines():
            m = re.match(r'^([a-z_]+): (.*)$', line)
            if m and m.group(1) not in fields:
                fields[m.group(1)] = m.group(2)
        file_text = None
        if fields.get('file') and Path(fields['file']).exists():
            file_text = Path(fields['file']).read_text()
        return {'summary': text, 'fields': fields, 'is_error': bool(res.get('isError')), 'file_text': file_text}

    def close(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()
