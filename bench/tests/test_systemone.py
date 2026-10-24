from __future__ import annotations

import json
import math
import os
import sys
import threading
import types
import unittest
import urllib.error
import urllib.request
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "bench" / "systemone" / "examples"
sys.path.insert(0, str(ROOT))

from bench.systemone.fake import FakeDecider
from bench.systemone.schema import ProtocolError, build_answer, from_answer, parse_request
from bench.systemone.server import make_server

_chunking_spec = spec_from_file_location(
    "_decision_chunking", ROOT / "ml" / "src" / "brain" / "decision_chunking.py"
)
_chunking = module_from_spec(_chunking_spec)
_chunking_spec.loader.exec_module(_chunking)


def _schema_errors(value, schema, root):
    if schema is True:
        return []
    if schema is False:
        return ["value rejected"]
    if "$ref" in schema:
        target = root
        for part in schema["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        return _schema_errors(value, target, root)

    errors = []
    expected = schema.get("type")
    allowed = expected if isinstance(expected, list) else [expected]
    if expected is not None:
        valid = False
        for kind in allowed:
            valid |= {
                "null": value is None,
                "object": isinstance(value, dict),
                "array": isinstance(value, list),
                "string": isinstance(value, str),
                "boolean": isinstance(value, bool),
                "integer": isinstance(value, int) and not isinstance(value, bool),
                "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            }[kind]
        if not valid:
            return [f"expected {expected!r}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"expected constant {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"expected one of {schema['enum']!r}")
    if "oneOf" in schema:
        matches = sum(not _schema_errors(value, branch, root) for branch in schema["oneOf"])
        if matches != 1:
            errors.append(f"oneOf matched {matches} branches")
    for conditional in schema.get("allOf", []):
        if "if" in conditional:
            if not _schema_errors(value, conditional["if"], root):
                errors.extend(_schema_errors(value, conditional.get("then", {}), root))
        else:
            errors.extend(_schema_errors(value, conditional, root))
    if isinstance(value, dict):
        for required in schema.get("required", []):
            if required not in value:
                errors.append(f"missing {required}")
        properties = schema.get("properties", {})
        for key, child in properties.items():
            if key in value:
                errors.extend(_schema_errors(value[key], child, root))
        additional = schema.get("additionalProperties", True)
        if additional is False:
            errors.extend(f"unexpected property {key}" for key in value if key not in properties)
        elif isinstance(additional, dict):
            for key in value.keys() - properties.keys():
                errors.extend(_schema_errors(value[key], additional, root))
        if len(value) < schema.get("minProperties", 0):
            errors.append("too few properties")
        if len(value) > schema.get("maxProperties", math.inf):
            errors.append("too many properties")
        if "propertyNames" in schema:
            for key in value:
                errors.extend(_schema_errors(key, schema["propertyNames"], root))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", math.inf):
            errors.append("array length out of bounds")
        if isinstance(schema.get("items"), dict):
            for item in value:
                errors.extend(_schema_errors(item, schema["items"], root))
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append("string too short")
        if "pattern" in schema and not __import__("re").search(schema["pattern"], value):
            errors.append("pattern mismatch")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < schema.get("minimum", -math.inf) or value > schema.get("maximum", math.inf):
            errors.append("number out of bounds")
    return errors


def _jev_typesafe_parse(task, answer):
    """Vendored parser from jevbench/adapters/typesafe.py at 609a664."""
    qtype = task.question["type"]
    if answer.get("type") != qtype:
        raise ValueError("native answer type mismatch")
    if qtype == "noul":
        if isinstance(answer["noul"], bool) or not isinstance(answer["noul"], (int, float)):
            raise ValueError("noul must be numeric")
        probability = float(answer["noul"])
        if not 0.0 <= probability <= 1.0:
            raise ValueError("noul out of range")
        return {"yes": probability, "no": 1.0 - probability}
    if qtype == "choice":
        if answer.get("choice") not in task.labels:
            raise ValueError("Invalid native choice")
        probabilities = answer.get("probabilities")
        if not isinstance(probabilities, dict):
            raise ValueError("choice answer missing probabilities")
        return probabilities
    if qtype == "score":
        probabilities = answer.get("probabilities")
        if not isinstance(probabilities, dict):
            raise ValueError("score answer missing probabilities")
        return probabilities
    raise ValueError("unknown question type")


class SystemOneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request_schema = json.loads((EXAMPLES / "request.schema.json").read_text())
        cls.response_schema = json.loads((EXAMPLES / "response.schema.json").read_text())
        cls.examples = sorted(
            path for folder in ("deskmind", "jevbench", "typed_decisions")
            for path in (EXAMPLES / folder).glob("*.json")
        )

    def test_saved_requests_round_trip_and_schema(self):
        self.assertEqual(len(self.examples), 9)
        for path in self.examples:
            with self.subTest(path=path.name):
                payload = json.loads(path.read_text())
                self.assertEqual(_schema_errors(payload, self.request_schema, self.request_schema), [])
                parsed = parse_request(payload)
                self.assertEqual(list(parsed.questions), list(payload["questions"]))
                for qid, question in parsed.questions.items():
                    self.assertEqual(question.options, list(question.options))
                    self.assertGreaterEqual(len(question.options), 1, qid)

    def test_parser_rejects_bad_criteria_and_identity(self):
        valid = {"state": "s", "questions": {"q": {
            "type": "choice", "instructions": "choose",
            "criteria": [{"key": "first", "description": "one"}, {"key": "second", "description": "two"}],
        }}}
        parsed = parse_request(valid)
        self.assertEqual(parsed.questions["q"].options, ["first", "second"])
        self.assertEqual(parsed.questions["q"].descriptions["second"], "two")
        with self.assertRaisesRegex(ProtocolError, "duplicate"):
            parse_request({"state": "s", "questions": {"q": {
                "type": "choice", "instructions": "x",
                "criteria": [{"key": "a", "description": ""}, {"key": "a", "description": ""}],
            }}})
        with self.assertRaises(ProtocolError):
            parse_request({"state": "s", "step": True, "questions": {}})
        with self.assertRaises(ProtocolError):
            parse_request({"state": "s", "questions": {"q": {
                "type": "score", "instructions": "x", "criteria": ["only one"],
            }}})
        with self.assertRaises(ProtocolError):
            parse_request({"state": "s", "state_digest": "sha256:bad", "questions": {}})

    def test_choice_limit_remains_255(self):
        choices = {f"option-{index}": "" for index in range(255)}
        request = parse_request({"state": "s", "questions": {"q": {
            "type": "choice", "instructions": "choose", "criteria": choices,
        }}})
        self.assertEqual(len(request.questions["q"].options), 255)
        choices["option-255"] = ""
        with self.assertRaisesRegex(ProtocolError, "1..255"):
            parse_request({"state": "s", "questions": {"q": {
                "type": "choice", "instructions": "choose", "criteria": choices,
            }}})

    def test_chunk_options_balances_and_preserves_order(self):
        chunk_options = _chunking.chunk_options
        for count, expected_sizes in ((59, [30, 29]), (240, [48, 48, 48, 48, 48])):
            options = [(f"option-{index}", f"description-{index}") for index in range(count)]
            chunks = chunk_options(options, 58)
            self.assertEqual([len(chunk) for chunk in chunks], expected_sizes)
            self.assertEqual([option for chunk in chunks for option in chunk], options)
            self.assertTrue(all(0 < len(chunk) <= 58 for chunk in chunks))
        options = [("a", "A"), ("b", "B"), ("c", "C")]
        self.assertEqual(chunk_options(options, 58), [options])

    def test_combine_chunked_normalizes_and_preserves_option_order(self):
        chunks = [[("a", "A"), ("b", "B")], [("c", "C"), ("d", "D")]]
        conditional = [
            {"a": 0.7, "b": 0.3},
            {"c": 0.2, "d": 0.8},
        ]
        combined = _chunking.combine_chunked(chunks, conditional, {"a": 0.4, "d": 0.6})
        self.assertEqual(list(combined), ["a", "b", "c", "d"])
        for option, probability in {"a": 0.28, "b": 0.12, "c": 0.12, "d": 0.48}.items():
            self.assertAlmostEqual(combined[option], probability)
        self.assertAlmostEqual(sum(combined.values()), 1.0)

    def test_answer_normalization_and_confidence(self):
        request = parse_request({"state": "s", "questions": {
            "choice": {"type": "choice", "instructions": "pick", "criteria": {"a": "A", "b": "B"}},
            "score": {"type": "score", "instructions": "rate", "criteria": ["low", "mid", "high"]},
            "noul": {"type": "noul", "instructions": "safe?"},
        }})
        choice = request.questions["choice"]
        answer = build_answer(choice, {"a": -1.0, "b": 3.0, "extra": 10.0})
        self.assertEqual(answer["choice"], "b")
        self.assertEqual(answer["probabilities"], {"a": 0.0, "b": 1.0})
        self.assertEqual(answer["confidence"], 1.0)
        score = build_answer(request.questions["score"], {"0": 0.25, "1": 0.5, "2": 0.25})
        self.assertEqual(score["score"], 1.0)
        self.assertEqual(score["legend"], {"0": "low", "1": "mid", "2": "high"})
        noul = build_answer(request.questions["noul"], {"false": 0.4, "true": 0.6})
        self.assertEqual(noul["probabilities"], {"false": 0.4, "true": 0.6})
        self.assertEqual(from_answer(request.questions["noul"], noul), {"false": 0.4, "true": 0.6})

    def test_confidence_temperature_can_differ_from_probability_temperature(self):
        request = parse_request({"state": "s", "questions": {
            "choice": {"type": "choice", "instructions": "pick", "criteria": {"a": "A", "b": "B"}},
        }})
        answer = build_answer(
            request.questions["choice"], {"a": 0.9, "b": 0.1},
            confidence_distribution={"a": 0.5, "b": 0.5},
        )
        self.assertEqual(answer["probabilities"], {"a": 0.9, "b": 0.1})
        self.assertEqual(answer["confidence"], 0.0)

    def test_fake_server_accepts_all_examples_and_schema_validates_responses(self):
        server = make_server("127.0.0.1", 0, FakeDecider(), "muselet")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            models = json.loads(urllib.request.urlopen(base + "/v1/models", timeout=2).read())
            self.assertEqual(models["data"][0]["id"], "muselet")
            for path in self.examples:
                payload = json.loads(path.read_text())
                req = urllib.request.Request(
                    base + "/v1/systemone",
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.subTest(path=path):
                    body = json.loads(urllib.request.urlopen(req, timeout=5).read())
                    self.assertEqual(_schema_errors(body, self.response_schema, self.response_schema), [])
                    self.assertIsNone(body["usage"]["input_tokens"])
                    self.assertEqual(set(body["answers"]), set(payload["questions"]))
                    for qid, raw_question in payload["questions"].items():
                        question = parse_request({
                            "state": payload["state"], "questions": {qid: raw_question}
                        }).questions[qid]
                        answer = body["answers"][qid]
                        probs = from_answer(question, answer)
                        self.assertEqual(list(probs), question.options)
                        self.assertAlmostEqual(sum(probs.values()), 1.0)
                        if question.type == "choice":
                            self.assertIn(answer["choice"], question.options)
                        self.assertGreaterEqual(answer["confidence"], 0.0) if "confidence" in answer else None
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_error_shape_and_routes(self):
        server = make_server("127.0.0.1", 0, FakeDecider(), "muselet")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            bad = urllib.request.Request(
                base + "/v1/systemone", data=b"{", headers={"Content-Type": "application/json"}, method="POST"
            )
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(bad, timeout=2)
            self.assertEqual(caught.exception.code, 400)
            self.assertEqual(json.loads(caught.exception.read())["error"]["code"], "invalid_json")
            with self.assertRaises(urllib.error.HTTPError) as missing:
                urllib.request.urlopen(base + "/not-a-route", timeout=2)
            self.assertEqual(missing.exception.code, 404)
            self.assertEqual(json.loads(missing.exception.read())["error"]["code"], "not_found")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_jevbench_and_typed_decisions_parsers_accept_answers(self):
        from bench.typed_decisions import score_one

        class Task:
            labels = ["allowed", "blocked"]
            question = {"type": "choice"}

        task = Task()
        answer = {"type": "choice", "choice": "allowed", "probabilities": {"allowed": 0.7, "blocked": 0.3}}
        self.assertEqual(_jev_typesafe_parse(task, answer), answer["probabilities"])
        gold = {"type": "choice", "probabilities": {"allowed": 1.0, "blocked": 0.0}}
        self.assertEqual(score_one(answer, gold)[0], True)
        noul = {"type": "noul", "noul": 0.8, "probabilities": {"false": 0.2, "true": 0.8}}
        self.assertEqual(
            score_one(noul, {"type": "noul", "probabilities": {"false": 0.0, "true": 1.0}})[0],
            True,
        )

    def test_tokenizer_only_renderer_when_upstream_dependencies_exist(self):
        decision_src = os.environ.get("MUSELET_DECISION_SRC")
        if decision_src:
            sys.path.insert(0, decision_src)
        sys.path.insert(0, str(ROOT / "ml" / "src"))
        stubbed_mlx = False
        try:
            import brain
            if decision_src:
                brain.__path__.insert(0, str(Path(decision_src) / "brain"))
            try:
                import mlx.core
                import mlx_lm
            except ImportError:
                mlx = types.ModuleType("mlx")
                core = types.ModuleType("mlx.core")
                mlx.core = core
                mlx.__path__ = []
                sys.modules.setdefault("mlx", mlx)
                sys.modules.setdefault("mlx.core", core)
                sys.modules.setdefault("mlx_lm", types.ModuleType("mlx_lm"))
                stubbed_mlx = True
            try:
                import dateparser
            except ImportError:
                dateparser = types.ModuleType("dateparser")
                dateparser.parse = lambda *_args, **_kwargs: None
                sys.modules["dateparser"] = dateparser
            from brain.generic_decide import Decision, GenericRenderer, _decision
            from bench.systemone.server import state_text
            from huggingface_hub import snapshot_download
            if stubbed_mlx:
                sys.modules.pop("mlx", None)
                sys.modules.pop("mlx.core", None)
                sys.modules.pop("mlx_lm", None)
        except ImportError as exc:
            if decision_src:
                raise
            self.skipTest(f"set MUSELET_DECISION_SRC to run the WIP tokenizer renderer: {exc}")

        tokenizer_path = os.environ.get("MUSELET_DECISION_TOKENIZER")
        if not tokenizer_path:
            tokenizer_path = snapshot_download(
                "mlx-community/Qwen3.5-4B-4bit",
                allow_patterns=[
                    "config.json", "tokenizer.json", "tokenizer_config.json",
                    "special_tokens_map.json", "added_tokens.json", "vocab.json",
                    "merges.txt", "*.model", "chat_template.jinja",
                ],
            )
        renderer = GenericRenderer(tokenizer_path)
        self.assertEqual(renderer.maximum, 58)
        static = renderer.static_tokens
        checked_types = set()
        chunked_questions = 0

        for path in self.examples:
            payload = json.loads(path.read_text())
            parsed = parse_request(payload)
            questions = {
                qid: {
                    "type": question.type,
                    "instructions": question.instructions,
                    "criteria": question.criteria,
                    "options": question.options,
                    "descriptions": question.descriptions,
                }
                for qid, question in parsed.questions.items()
            }
            plans, decisions = renderer.prepare(state_text(parsed.state), questions)
            renderings = renderer.render_decisions(decisions)
            self.assertGreaterEqual(renderer.common_prefix(list(renderings.values())), len(static))
            for key, decision in decisions.items():
                rendered = renderings[key]
                self.assertEqual(rendered.tokens[:len(static)], static)
                self.assertEqual(rendered.choice_pos, len(rendered.tokens) - 1)
                self.assertEqual(
                    rendered.tokens[rendered.choice_pos],
                    renderer.choice_renderer.answer_tokens[
                        len(renderer.choice_renderer.prefix_tokens)
                    ],
                )
                self.assertEqual(list(rendered.label_tokens), decision.labels)
                self.assertEqual(len(rendered.label_tokens), len(decision.choices))
                qtype = questions[key[0]]["type"]
                if qtype == "noul":
                    self.assertEqual(len(rendered.label_tokens), 2)
                elif qtype == "score":
                    self.assertEqual(len(rendered.label_tokens), len(questions[key[0]]["options"]))
                prefix = renderer.choice_renderer.prefix_tokens
                for index, (label, _description) in enumerate(decision.choices):
                    choice_id = renderer.choice_renderer.usable_ids[index]
                    label_tokens = renderer.tokenizer.encode(
                        renderer.choice_renderer.prefix + choice_id,
                        add_special_tokens=False,
                    )
                    self.assertEqual(label_tokens[:len(prefix)], prefix)
                    self.assertEqual(len(label_tokens), len(prefix) + 1)
                    self.assertEqual(rendered.label_tokens[label], label_tokens[-1])
                checked_types.add(qtype)

            for qid, plan in plans.items():
                if len(plan["chunks"]) <= 1:
                    continue
                chunked_questions += 1
                winners = [chunk[0] for chunk in plan["chunks"]]
                stage_two = renderer.render(
                    Decision(text=plan["decision"].text, choices=winners)
                )
                self.assertEqual(stage_two.tokens[:len(static)], static)
                self.assertEqual(stage_two.choice_pos, len(stage_two.tokens) - 1)
                self.assertEqual(len(stage_two.label_tokens), len(winners))
                self.assertEqual(list(stage_two.label_tokens), [label for label, _ in winners])
                for index, (label, _description) in enumerate(winners):
                    label_tokens = renderer.tokenizer.encode(
                        renderer.choice_renderer.prefix
                        + renderer.choice_renderer.usable_ids[index],
                        add_special_tokens=False,
                    )
                    self.assertEqual(label_tokens[:len(renderer.choice_renderer.prefix_tokens)],
                                     renderer.choice_renderer.prefix_tokens)
                    self.assertEqual(
                        len(label_tokens),
                        len(renderer.choice_renderer.prefix_tokens) + 1,
                    )
                    self.assertEqual(stage_two.label_tokens[label], label_tokens[-1])

        self.assertIn("noul", checked_types)
        self.assertIn("score", checked_types)
        self.assertGreater(chunked_questions, 0)


if __name__ == "__main__":
    unittest.main()
