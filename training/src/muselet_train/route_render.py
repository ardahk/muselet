"""Route + ARGS rendering (SPEC 1.2). Must stay byte-identical with the Mac runtime."""

from __future__ import annotations

import string
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

from tinker_cookbook import model_info, renderers
from tinker_cookbook.exceptions import ConfigurationError
from tinker_cookbook.recipes.decisions import (
    ChoiceRendering,
    Decision,
    DecisionRenderer,
    DecisionRendering,
)
from tinker_cookbook.renderers import Message, Renderer
from tinker_cookbook.tokenizer_utils import get_tokenizer

from muselet_train.catalog import Option, arg_signature, options

STUDENT_MODEL = "Qwen/Qwen3.5-4B"
PREFIX = "choice#"
PLACEHOLDER = "?"
ID_CANDIDATES = string.ascii_uppercase + string.digits + string.ascii_lowercase
MIN_IDS = 40

ROUTE_SYSTEM = """You are the intent router of an on-device macOS voice assistant. Read the context and the user's spoken request, then pick exactly one choice. Reply with the id of your choice, written as `choice#?`, and nothing else.

Choices:
{choices}"""

ROUTE_USER = """Context: app={app} | focused={focused} | selection={selection} | online={online} | last_action={last_action}
Request: "{utterance}\""""

ARGS_SYSTEM = "You extract arguments for a macOS assistant skill from the user's spoken request. Reply with one line of key=value pairs using the skill's argument names. Quote values that contain spaces. Copy spoken dates, times and durations exactly as said; do not convert them. Convert spoken numbers to digits. If a required argument is missing, reply missing=<argument name>."

ARGS_USER = """Skill: {name}({signature})
Context: app={app} | last_action={last_action}
Request: "{utterance}\""""


@dataclass(frozen=True)
class RouteContext:
    app: str
    focused: str = "none"
    selection: bool = False
    online: bool = True
    last_action: str | None = None

    def line(self) -> str:
        return ROUTE_USER.split("\n")[0].format(
            app=self.app,
            focused=self.focused,
            selection="yes" if self.selection else "no",
            online="yes" if self.online else "no",
            last_action=self.last_action or "none",
        )


def usable_ids(tokenizer) -> list[str]:
    """Ordered id alphabet: chars c where encode(PREFIX + c) == encode(PREFIX) + [one token]."""
    prefix = tokenizer.encode(PREFIX, add_special_tokens=False)

    def single(c: str) -> bool:
        t = tokenizer.encode(PREFIX + c, add_special_tokens=False)
        return t[: len(prefix)] == prefix and len(t) == len(prefix) + 1

    if not single(PLACEHOLDER):
        raise ConfigurationError(f"placeholder {PLACEHOLDER!r} is not one token after {PREFIX!r}")
    ids = [c for c in ID_CANDIDATES if single(c)]
    if len(ids) < MIN_IDS:
        raise ConfigurationError(f"only {len(ids)} usable choice ids (< {MIN_IDS}): {ids}")
    return ids


class AlphabetChoiceRenderer:
    """Like PrefixedChoiceRenderer but with the extended id alphabet (A-Z, 0-9, a-z filtered)."""

    def __init__(self, renderer: Renderer):
        self.tokenizer = renderer.tokenizer
        self.ids = usable_ids(self.tokenizer)
        self.prefix_tokens = self.tokenizer.encode(PREFIX, add_special_tokens=False)
        self.answer_tokens = self.tokenizer.encode(PREFIX + PLACEHOLDER, add_special_tokens=False)
        n = len(self.prefix_tokens)
        self.id_tokens = {
            c: self.tokenizer.encode(PREFIX + c, add_special_tokens=False)[n] for c in self.ids
        }
        if len(set(self.id_tokens.values()) | {self.answer_tokens[-1]}) != len(self.ids) + 1:
            raise ConfigurationError("choice id tokens are not distinct")

    def id_for(self, index: int) -> str:
        return self.ids[index]

    def render_choices(self, labels: Sequence[str]) -> ChoiceRendering:
        if len(labels) > len(self.ids):
            raise ConfigurationError(f"at most {len(self.ids)} choices, got {len(labels)}")
        return ChoiceRendering(
            answer_tokens=list(self.answer_tokens),
            answer_position=len(self.prefix_tokens),
            label_tokens={lab: self.id_tokens[c] for lab, c in zip(labels, self.ids)},
        )


class RouteDecisionRenderer(DecisionRenderer):
    """Options in the system message (static, cacheable); context + request in the user message.

    ``Decision.text`` is the full user message; ``Decision.choices`` are (name, description).
    """

    def __init__(self, renderer: Renderer):
        super().__init__(renderer, AlphabetChoiceRenderer(renderer))

    def system_text(self, choices: Sequence[tuple[str, str]]) -> str:
        cr: AlphabetChoiceRenderer = self.choice_renderer  # type: ignore[assignment]
        lines = [
            f'{PREFIX}{cr.id_for(i)} = "{name}": {desc}' for i, (name, desc) in enumerate(choices)
        ]
        return ROUTE_SYSTEM.format(choices="\n".join(lines))

    def _build_messages(
        self, decision: Decision, choice_rendering: ChoiceRendering
    ) -> list[Message]:
        return [
            Message(role="system", content=self.system_text(decision.choices)),
            Message(role="user", content=decision.text),
        ]


def route_user_text(ctx: RouteContext, utterance: str) -> str:
    return ROUTE_USER.format(
        app=ctx.app,
        focused=ctx.focused,
        selection="yes" if ctx.selection else "no",
        online="yes" if ctx.online else "no",
        last_action=ctx.last_action or "none",
        utterance=utterance,
    )


def route_choices(opts: Sequence[Option] | None = None) -> list[tuple[str, str]]:
    return [(o.name, o.description) for o in (opts if opts is not None else options())]


def route_decision(ctx: RouteContext, utterance: str) -> Decision:
    return Decision(route_user_text(ctx, utterance), route_choices())


def args_messages(
    opt: Option, ctx: RouteContext, utterance: str, target: str | None = None
) -> list[Message]:
    msgs = [
        Message(role="system", content=ARGS_SYSTEM),
        Message(
            role="user",
            content=ARGS_USER.format(
                name=opt.name,
                signature=arg_signature(opt),
                app=ctx.app,
                last_action=ctx.last_action or "none",
                utterance=utterance,
            ),
        ),
    ]
    if target is not None:
        msgs.append(Message(role="assistant", content=target))
    return msgs


_SENTINEL = "SENTINELMARKER9Z"


def args_runtime_prompt(rend: Renderer, opt: Option, ctx: RouteContext, utterance: str) -> list[int]:
    """ARGS prompt ids exactly as brain.decision.DecisionEngine.args builds them: the empty think block is prefilled."""
    toks = rend.build_supervised_example(args_messages(opt, ctx, utterance, _SENTINEL))[0].to_ints()
    s = rend.tokenizer.encode(_SENTINEL, add_special_tokens=False)
    return toks[:next(i for i in range(len(toks)) if toks[i:i + len(s)] == s)]


@lru_cache(maxsize=4)
def base_renderer(model: str = STUDENT_MODEL) -> Renderer:
    return renderers.get_renderer(model_info.get_recommended_renderer_name(model), get_tokenizer(model))


@lru_cache(maxsize=4)
def route_renderer(model: str = STUDENT_MODEL) -> RouteDecisionRenderer:
    return RouteDecisionRenderer(base_renderer(model))


def render_route(ctx: RouteContext, utterance: str, model: str = STUDENT_MODEL) -> DecisionRendering:
    return route_renderer(model).render(route_decision(ctx, utterance))
