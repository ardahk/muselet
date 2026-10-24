import subprocess
from types import SimpleNamespace

from bench.hobbylm import replay


def _args(tmp_path):
    hobby = tmp_path / "upstream" / "hobby"
    hobby.mkdir(parents=True)
    (hobby / "hobbymac_run.py").write_text(
        "from pathlib import Path\n"
        "ROOT = Path('.')\nWORK = ROOT / 'data'\nTEST_CAL = 'x'\n"
        "def snapshot():\n"
        "    return {'work_is_path': isinstance(WORK, Path),\n"
        "            'tool': str(WORK / 'brightness')}\n"
        "def running(app):\n    return False\n"
    )
    return SimpleNamespace(hobby_root=tmp_path / "upstream", hobby_dir=hobby,
                           work_dir=tmp_path / "tools")


def test_state_script_sets_work_as_a_path(tmp_path):
    args = _args(tmp_path)
    out = subprocess.run(replay._hobby_state_script(args, "dark"), shell=True,
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert '"work_is_path": true' in out.stdout
    assert str(tmp_path / "tools" / "brightness") in out.stdout


def test_restore_script_sets_root_and_work_as_paths(tmp_path):
    script = replay._hobby_restore_script(_args(tmp_path), {}, {}, {})
    assert "helper.ROOT = Path(" in script and "helper.WORK = Path(" in script
    assert "from pathlib import Path" in script
