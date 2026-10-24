"""Shared single-token choice renderer for local and cloud System One paths."""

from __future__ import annotations

import string

from .vendor.tinker_decisions import PrefixedChoiceRenderer


class AlphaChoiceRenderer(PrefixedChoiceRenderer):
    """choice#<ID> where ID alphabet is A..Z, 0..9, a..z — filtered to ids
    that tokenize as exactly one token after the prefix (SPEC 1.2)."""

    IDS = list(string.ascii_uppercase + string.digits + string.ascii_lowercase)

    def __init__(self, renderer):
        super().__init__(renderer, prefix="choice#", placeholder="?")
        prefix_length = len(self.prefix_tokens)
        usable_ids = []
        for choice_id in self.IDS:
            tokens = self.tokenizer.encode(self.prefix + choice_id, add_special_tokens=False)
            if tokens[:prefix_length] == self.prefix_tokens and len(tokens) == prefix_length + 1:
                usable_ids.append(choice_id)
        if len(usable_ids) < 40:
            raise RuntimeError(f"only {len(usable_ids)} usable choice ids, need >= 40")
        self.usable_ids = usable_ids
        self.IDS = usable_ids
