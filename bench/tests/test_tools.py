from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

from bench.deskmind.run_muselet import _WorkspacePageServer, make_plan
from bench.hobbylm import replay
from bench.hobbylm.upstream.hobby import calendar_tool


R4_FIXTURE = Path(__file__).with_name("hobbylm_r4_expected.tsv")


def r4_tasks():
    with R4_FIXTURE.open(encoding="utf-8") as source:
        return {
            row["kind"]: {
                "id": row["id"], "kind": row["kind"],
                "text": row["text"], "expected": row["expected"],
            }
            for row in csv.DictReader(source, delimiter="\t", fieldnames=("id", "kind", "text", "expected"))
        }


class MockGraderHelper:
    CAL = calendar_tool
    LOCAL_TZ = "Asia/Kolkata"

    @staticmethod
    def as_num(value):
        try:
            return float((value or "").replace(",", ""))
        except ValueError:
            return None

    @staticmethod
    def finder_path():
        return ""


class ReplayTests(unittest.TestCase):
    def test_plan_expands_repeats_and_keeps_port(self):
        tasks = [{"id": "C01", "kind": "calc", "text": "two plus two"}]
        rows = replay.plan("muselet", "r4", tasks, 2, 8877)
        self.assertEqual(len(rows), 2)
        self.assertEqual([row["repeat"] for row in rows], [1, 2])
        self.assertEqual({row["port"] for row in rows}, {8877})
        self.assertEqual({row["text"] for row in rows}, {"two plus two"})

    def test_report_math_reports_pass_k_false_done_and_latency(self):
        rows = [
            {"id": "C01", "kind": "calc", "pass": True, "completed": True,
             "pass_final_state": True, "false_done": False,
             "utterance_latency_s": 2.0, "first_action_latency_s": 0.4, "completion_latency_s": 1.8},
            {"id": "C01", "kind": "calc", "pass": False, "completed": False,
             "pass_final_state": False, "false_done": True,
             "utterance_latency_s": 3.0, "first_action_latency_s": 0.8, "completion_latency_s": None},
        ]
        result = replay.report_math(rows, 2)
        self.assertEqual(result["n"], 2)
        self.assertEqual(result["pass_rate"], 0.5)
        self.assertEqual(result["completed_rate"], 0.5)
        self.assertEqual(result["pass_final_state_rate"], 0.5)
        self.assertEqual(result["pass_k_by_kind"]["calc"], 0.0)
        self.assertEqual(result["completed_k_by_kind"]["calc"], 0.0)
        self.assertEqual(result["false_done"], 1)
        self.assertEqual(result["utterance_latency_s"]["p50"], 2.5)
        self.assertEqual(result["first_action_latency_s"]["p95"], 0.78)

    def test_deskmind_plan_preserves_loaded_goal_and_setup(self):
        task = SimpleNamespace(
            id="G03-safari-extract", goal="Safari goal, already loaded",
            fixture="diag_web", app="com.apple.Safari",
            reset_apps=["com.apple.Safari", "com.apple.TextEdit"],
            stage=['open -a TextEdit "$WS/inventory.csv"', 'open -a Safari "$WS/page.html"'],
        )
        row = make_plan([task], 1, 8765, Path("/runs/bench"))
        self.assertEqual(row[0]["goal"], task.goal)
        self.assertEqual(row[0]["hands"][-1], task.goal)
        self.assertEqual(row[0]["app"], task.app)
        self.assertEqual(row[0]["reset_apps"], task.reset_apps)
        self.assertEqual(row[0]["stage"], task.stage)

    def test_deskmind_workspace_page_server_serves_only_workspace_files(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            workspace = parent / "ws"
            workspace.mkdir()
            page = workspace / "page.html"
            page.write_text("fixture")
            outside = parent / "outside.html"
            outside.write_text("outside")
            (workspace / "leak.html").symlink_to(outside)
            server = _WorkspacePageServer(workspace)
            try:
                with urllib.request.urlopen(server.url(page), timeout=5) as response:
                    self.assertEqual(response.read(), b"fixture")
                for path in (workspace / "leak.html", workspace / ".hidden"):
                    with self.subTest(path=path.name):
                        with self.assertRaises(urllib.error.HTTPError):
                            urllib.request.urlopen(server.url(path), timeout=5)
            finally:
                server.close()

    def test_grades_real_r4_expected_strings_for_every_kind(self):
        tasks = r4_tasks()
        self.assertEqual(
            set(tasks), {"calc", "device", "dark", "app", "folder", "timer", "screenshot", "none", "event"}
        )
        if (replay.DEFAULT_HOME / "data/frozen/hobbymac-sealed-test-r4.tsv").is_file():
            source_tasks = {
                task["id"]: task for task in replay.load_tasks(replay.DEFAULT_HOME, "r4")
            }
            for task in tasks.values():
                self.assertEqual(task["expected"], source_tasks[task["id"]]["expected"])

        helper = MockGraderHelper()
        test_now = datetime(2025, 1, 6, 9, tzinfo=ZoneInfo(helper.LOCAL_TZ))
        for kind, record in tasks.items():
            start = {
                "bright": 0.5, "vol": (50, False), "dark": False, "front": "Finder",
                "finder_windows": 1, "running": {"Finder": True, "Notes": False},
                "screenshot_files": ["/tmp/existing.png"],
                "calendar_now": test_now.isoformat(),
                "calendar_events": [{"identifier": "existing"}],
            }
            current = dict(start)
            current["calendar_events"] = list(start["calendar_events"])
            if kind == "calc":
                current["display"] = "129"
            elif kind == "device":
                current["bright"] = 0.3
            elif kind == "dark":
                current["dark"] = True
            elif kind == "app":
                current["front"] = "Notes"
            elif kind == "folder":
                current["finder_path"] = "/Users/test/Downloads"
            elif kind == "timer":
                current["timers"] = [18]
            elif kind == "screenshot":
                current["screenshot_files"] = start["screenshot_files"] + ["/tmp/new.png"]
            elif kind == "event":
                expected = record["expected"].removeprefix("EVENT ").strip()
                plan = helper.CAL.plan_event(expected, test_now, helper.LOCAL_TZ, lookup=lambda _name: [])
                current["calendar_events"] = start["calendar_events"] + [{
                    "identifier": "new-event", "title": plan.title,
                    "start": plan.start.isoformat(), "notes": "", "attendees": [],
                }]
            elif kind == "none":
                current["screenshot_files"] = list(start["screenshot_files"])

            with self.subTest(kind=kind, outcome="pass"):
                passed, _ = replay._grade_final_state(helper, record, start, current)
                self.assertTrue(passed)

            failed = dict(current)
            if kind == "calc":
                failed["display"] = "0"
            elif kind == "device":
                failed["bright"] = 0.8
            elif kind == "dark":
                failed["dark"] = False
            elif kind == "app":
                failed["front"] = "Finder"
            elif kind == "folder":
                failed["finder_path"] = "/Users/test/Desktop"
            elif kind == "timer":
                failed["timers"] = [19]
            elif kind == "screenshot":
                failed["screenshot_files"] = start["screenshot_files"] + ["/tmp/a.png", "/tmp/b.png"]
            elif kind == "event":
                failed["calendar_events"] = start["calendar_events"] + [{
                    "identifier": "new-event", "title": "Unrelated event",
                    "start": current["calendar_events"][-1]["start"], "notes": "", "attendees": [],
                }]
            elif kind == "none":
                failed["running"] = {"Finder": True, "Notes": True}
            with self.subTest(kind=kind, outcome="fail"):
                passed, _ = replay._grade_final_state(helper, record, start, failed)
                self.assertFalse(passed)

    def test_none_fails_if_any_action_rpc_was_dispatched(self):
        record = r4_tasks()["none"]
        start = {
            "bright": 0.5, "vol": (50, False), "dark": False, "front": "Finder",
            "finder_windows": 1, "running": {"Finder": True},
            "screenshot_files": [], "calendar_events": [],
        }
        passed, _ = replay._grade_final_state(
            MockGraderHelper(), record, dict(start), dict(start),
            trace={"rpc": [{"method": "skill", "params": {"name": "open_app"}}]},
        )
        self.assertFalse(passed)


if __name__ == "__main__":
    unittest.main()
