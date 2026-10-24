"""Pure probability helpers for decisions with more options than one renderer pass."""

from __future__ import annotations

import math


def chunk_options(options: list[tuple[str, str]], maximum: int) -> list[list[tuple[str, str]]]:
    if maximum < 1:
        raise ValueError("maximum must be positive")
    count = len(options)
    if count <= maximum:
        return [list(options)]
    chunks_count = math.ceil(count / maximum)
    if chunks_count > maximum:
        raise ValueError("option count exceeds the two-stage renderer capacity")
    size, extra = divmod(count, chunks_count)
    chunks = []
    offset = 0
    for index in range(chunks_count):
        next_offset = offset + size + (index < extra)
        chunks.append(list(options[offset:next_offset]))
        offset = next_offset
    return chunks


def combine_chunked(
    chunks: list[list[tuple[str, str]]],
    conditional: list[dict[str, float]],
    winners: dict[str, float],
) -> dict[str, float]:
    if len(chunks) != len(conditional):
        raise ValueError("each option chunk must have one conditional distribution")
    combined: dict[str, float] = {}
    for chunk, distribution in zip(chunks, conditional, strict=True):
        if not chunk:
            raise ValueError("option chunks must not be empty")
        winner = max(chunk, key=lambda option: distribution[option[0]])[0]
        winner_mass = winners[winner]
        for label, _description in chunk:
            combined[label] = distribution[label] * winner_mass
    return combined
