from __future__ import annotations

import unittest

from bench.hobbylm.replay import plan, report_math


class ReplayTests(unittest.TestCase):
    def test_plan_expands_repeats_and_keeps_port(self):
        tasks = [{"id": "C01", "kind": "calc", "text": "two plus two"}]
        rows = plan("muselet", "r4", tasks, 2, 8877)
        self.assertEqual(len(rows), 2)
        self.assertEqual([row["repeat"] for row in rows], [1, 2])
        self.assertEqual({row["port"] for row in rows}, {8877})
        self.assertEqual({row["text"] for row in rows}, {"two plus two"})

    def test_report_math_reports_pass_k_false_done_and_latency(self):
        rows = [
            {"id": "C01", "kind": "calc", "pass": True, "false_done": False,
             "utterance_latency_s": 2.0, "first_action_latency_s": 0.4, "completion_latency_s": 1.8},
            {"id": "C01", "kind": "calc", "pass": False, "false_done": True,
             "utterance_latency_s": 3.0, "first_action_latency_s": 0.8, "completion_latency_s": None},
        ]
        result = report_math(rows, 2)
        self.assertEqual(result["n"], 2)
        self.assertEqual(result["pass_rate"], 0.5)
        self.assertEqual(result["pass_k_by_kind"]["calc"], 0.0)
        self.assertEqual(result["false_done"], 1)
        self.assertEqual(result["utterance_latency_s"]["p50"], 2.5)
        self.assertEqual(result["first_action_latency_s"]["p95"], 0.78)


if __name__ == "__main__":
    unittest.main()
