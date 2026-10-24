from argparse import Namespace
import ast
from pathlib import Path
import subprocess
import sys
import types

import pytest

from bench.hobbylm import replay
from bench.hobbylm.calendar_safety import BENCH_CALENDAR


def _vendored_tree(tmp_path):
    upstream = tmp_path / "upstream"
    hobby = upstream / "hobby"
    hobby.mkdir(parents=True)
    (hobby / "hobbymac_run.py").write_text("ROOT = None\nWORK = None\nTEST_CAL = None\n")
    for tool in replay.MUSELET_HELPER_TOOLS:
        (hobby / f"{tool}.swift").write_text(f"// {tool}\n")
    return upstream, hobby


def test_vendored_helper_compiles_once_and_reuses_source_hash_cache(
    monkeypatch, tmp_path
):
    upstream, hobby = _vendored_tree(tmp_path)
    monkeypatch.setattr(replay, "VENDORED_UPSTREAM", upstream)
    monkeypatch.setattr(replay, "ROOT", tmp_path)
    monkeypatch.delenv("HOBBY_HOME", raising=False)
    monkeypatch.setitem(sys.modules, "hobbymac_run", types.ModuleType("hobbymac_run"))
    calls = []

    def fake_compile(command, **kwargs):
        calls.append((command, kwargs))
        cache = tmp_path / "runs/bench/hobbylm/tools"
        for path in cache.glob("*"):
            for tool in replay.MUSELET_HELPER_TOOLS:
                (path / tool).write_text("binary")
        return subprocess.CompletedProcess(command, 0, "", "")

    args = Namespace(hobby_home=None)
    first = replay.resolve_muselet_helper(args, compile=fake_compile)
    second = replay.resolve_muselet_helper(args, compile=fake_compile)

    assert first[0] is second[0]
    assert first[1] == hobby
    assert first[2] == args.work_dir
    assert args.hobby_helper_source == "vendored"
    assert len(calls) == 1
    assert first[0].ROOT == upstream
    assert first[0].WORK == first[2]
    assert first[0].TEST_CAL == BENCH_CALENDAR


def test_vendored_helper_reports_missing_swift_compiler(monkeypatch, tmp_path):
    upstream, _hobby = _vendored_tree(tmp_path)
    monkeypatch.setattr(replay, "VENDORED_UPSTREAM", upstream)
    monkeypatch.setattr(replay, "ROOT", tmp_path)
    monkeypatch.delenv("HOBBY_HOME", raising=False)

    def missing_compiler(*_args, **_kwargs):
        raise FileNotFoundError("swiftc")

    with pytest.raises(RuntimeError, match=r"pass --hobby-home.*xcode-select --install"):
        replay.resolve_muselet_helper(
            Namespace(hobby_home=None), compile=missing_compiler
        )


def test_invalid_explicit_home_names_missing_helper_path(tmp_path):
    home = tmp_path / "bad-home"
    with pytest.raises(RuntimeError, match="hobbymac_run.py"):
        replay.resolve_muselet_helper(Namespace(hobby_home=home))


def test_vendored_helper_has_no_module_level_mlx_or_torch_imports():
    helper = replay.VENDORED_UPSTREAM / "hobby/hobbymac_run.py"
    tree = ast.parse(helper.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = [alias.name.split(".", 1)[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(node.module or "").split(".", 1)[0]]
        else:
            continue
        assert not {"mlx", "torch"} & set(names)
