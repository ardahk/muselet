"""Threaded HTTP server implementing the System One compatibility surface."""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol

from .schema import ProtocolError, build_answer, parse_request


class Decider(Protocol):
    def decide(self, state: str, question: dict) -> dict[str, float]: ...


def server_questions(request) -> dict[str, dict]:
    return {
        qid: {
            "type": question.type,
            "instructions": question.instructions,
            "criteria": question.criteria,
            "options": question.options,
            "descriptions": question.descriptions,
        }
        for qid, question in request.questions.items()
    }


def state_text(state: Any) -> str:
    return state if isinstance(state, str) else json.dumps(state, ensure_ascii=False, sort_keys=False)


def decide_many(decider: Decider, state: str, questions: dict[str, dict]) -> dict[str, dict[str, float]]:
    method = getattr(decider, "decide_many", None)
    if callable(method):
        return method(state, questions)
    return {qid: decider.decide(state, question) for qid, question in questions.items()}


def _error(code: str, message: str, *, field: str | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message, "retryable": code == "internal_error"}
    if field is not None:
        error["field"] = field
    return {"error": error}


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, decider: Decider, model_name: str):
        super().__init__(address, handler)
        self.decider = decider
        self.model_name = model_name
        self.backend_lock = threading.Lock()


class _Handler(BaseHTTPRequestHandler):
    server: _Server

    def log_message(self, format: str, *args: Any) -> None:
        logging.info("systemone_http " + format, *args)

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _not_found(self) -> None:
        self._send_json(404, _error("not_found", "Not found"))

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/v1/models":
            self._not_found()
            return
        self._send_json(200, {
            "data": [{
                "id": self.server.model_name,
                "object": "model",
                "criteria_forms": ["object", "list"],
            }],
        })

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/systemone":
            self._not_found()
            return
        started = time.perf_counter()
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                self._send_json(400, _error("invalid_json", f"Invalid JSON: {exc}"))
                return
            try:
                request = parse_request(payload)
            except ProtocolError as exc:
                self._send_json(400, _error(exc.code, str(exc), field=exc.field))
                return

            parsed_questions = server_questions(request)
            state = state_text(request.state)
            with self.server.backend_lock:
                distributions = decide_many(self.server.decider, state, parsed_questions)
                input_tokens = getattr(self.server.decider, "last_input_tokens", None)
            if set(distributions) != set(parsed_questions):
                raise ValueError("backend returned a different set of question IDs")
            answers = {
                qid: build_answer(request.questions[qid], distributions[qid])
                for qid in parsed_questions
            }
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            body: dict[str, Any] = {
                "id": "systemone-" + uuid.uuid4().hex,
                "model": self.server.model_name,
                "answers": answers,
                "usage": {"input_tokens": input_tokens, "output_tokens": 0},
                "latency_ms": elapsed_ms,
            }
            body.update({key: request.identity[key] for key in ("request_id", "session_id", "step") if key in request.identity})
            self._send_json(200, body)
        except ProtocolError as exc:
            self._send_json(400, _error(exc.code, str(exc), field=exc.field))
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
            if getattr(exc, "code", None) == "invalid_request":
                self._send_json(
                    400,
                    _error("invalid_request", str(exc), field=getattr(exc, "field", None)),
                )
                return
            logging.exception("systemone request failed")
            self._send_json(500, _error("internal_error", "Internal server error"))
        finally:
            logging.info("systemone_request latency_ms=%.2f", (time.perf_counter() - started) * 1000.0)


def make_server(host: str, port: int, decider: Decider, model_name: str = "muselet") -> ThreadingHTTPServer:
    return _Server((host, port), _Handler, decider, model_name)


def serve(host: str, port: int, decider: Decider, model_name: str = "muselet") -> None:
    server = make_server(host, port, decider, model_name)
    logging.info("System One shim listening on http://%s:%s", host, server.server_port)
    try:
        server.serve_forever()
    finally:
        server.server_close()
