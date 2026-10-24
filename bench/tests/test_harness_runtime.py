import asyncio
import json
import subprocess
from pathlib import Path

from bench.harness import runtime


class FakeProxy:
    def __init__(self, released=True):
        self.url = "ws://localhost:1"
        self.released = released
        self.calls = []
        self.capture = type("Capture", (), {
            "utterance_monotonic": None,
            "first_action_monotonic": None,
            "terminal_monotonic": None,
        })()

    async def release_slot(self, timeout):
        self.calls.append(("release", timeout))
        return self.released

    async def wait_connected(self):
        self.calls.append(("connected",))

    async def wait_disconnected(self):
        self.calls.append(("disconnected",))

    async def wait_for_utterance(self):
        self.calls.append(("utterance",))


class FakeProcess:
    def __init__(self, command, **_kwargs):
        self.command = command
        self.returncode = None

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = 0

    def kill(self):
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode


def test_start_scripts_releases_slot_before_spawning(monkeypatch, tmp_path):
    proxy = FakeProxy()
    order = []
    proxy.calls = order

    def popen(*args, **kwargs):
        order.append(("spawn",))
        return FakeProcess(*args, **kwargs)

    monkeypatch.setattr(runtime.subprocess, "Popen", popen)
    runtime.serve_timeout_supported.cache_clear()
    monkeypatch.setattr(
        runtime.subprocess, "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )
    instance = runtime.HandsRuntime(proxy, "hands", tmp_path, "case")
    asyncio.run(instance.start_scripts())
    assert order[0] == ("release", 5.0)
    assert order[1] == ("spawn",)
    asyncio.run(instance.stop())
    runtime.CLIENT_PROCESSES.clear()


def test_between_case_recovery_kills_strays_before_retrying_release():
    class StrayProcess:
        returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 0

        def kill(self):
            self.returncode = -9

        def wait(self, timeout=None):
            return self.returncode

    class Proxy:
        def __init__(self):
            self.releases = 0

        async def release_slot(self, _timeout):
            self.releases += 1
            return self.releases == 2

    process = StrayProcess()
    proxy = Proxy()
    runtime.CLIENT_PROCESSES.add(process)
    assert asyncio.run(runtime.release_slot_for_case(proxy))
    assert process.poll() == 0
    assert process not in runtime.CLIENT_PROCESSES
    assert proxy.releases == 2


def test_utterance_timeout_flag_depends_on_help_and_ceil_timeout(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(
        runtime.subprocess, "Popen",
        lambda command, **kwargs: commands.append(command) or FakeProcess(command, **kwargs),
    )
    monkeypatch.setattr(
        runtime.subprocess, "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, "serve options: --timeout seconds", ""
        ),
    )
    runtime.serve_timeout_supported.cache_clear()
    instance = runtime.HandsRuntime(FakeProxy(), "hands-timeout", tmp_path, "supported")
    asyncio.run(instance.start_utterance("hello", timeout_s=30.1))
    assert commands[-1][-2:] == ["--timeout", "46"]
    asyncio.run(instance.stop())
    runtime.CLIENT_PROCESSES.clear()

    commands.clear()
    monkeypatch.setattr(
        runtime.subprocess, "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "serve", ""),
    )
    runtime.serve_timeout_supported.cache_clear()
    instance = runtime.HandsRuntime(FakeProxy(), "hands-no-timeout", tmp_path, "unsupported")
    asyncio.run(instance.start_utterance("hello", timeout_s=30))
    assert "--timeout" not in commands[-1]
    asyncio.run(instance.stop())
    runtime.CLIENT_PROCESSES.clear()


def test_serve_summary_parses_last_line_and_exit_code(tmp_path):
    log = tmp_path / "hands.log"
    log.write_text(
        '{"t":"serve_summary","exit":1,"reason":"old"}\n'
        '{"t":"serve_summary","exit":2,"reason":"timeout"}\n'
    )
    assert runtime._serve_summary(log, 2) == {
        "t": "serve_summary", "exit": 2, "reason": "timeout", "exit_code": 2,
    }
