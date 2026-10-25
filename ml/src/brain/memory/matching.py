"""Small token-matching helpers shared by memory rules and validation."""

from __future__ import annotations


def distance_one(left: str, right: str, min_length: int = 5) -> bool:
    if left == right:
        return True
    if min(len(left), len(right)) < min_length or \
            abs(len(left) - len(right)) > 1:
        return False
    if len(left) > len(right):
        left, right = right, left
    row = list(range(len(left) + 1))
    for index, char in enumerate(right, 1):
        next_row = [index]
        for offset, other in enumerate(left, 1):
            next_row.append(min(
                next_row[-1] + 1, row[offset] + 1,
                row[offset - 1] + (char != other)))
        row = next_row
    return row[-1] <= 1
