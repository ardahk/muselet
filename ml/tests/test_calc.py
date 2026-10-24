"""Deterministic exact answers (task 3): no model call when code parses."""

import pytest
from brain import calc

CASES = [
    # percentages
    ("15 percent of 80", "15% of 80 is 12"),
    ("what's 15% of 80", "15% of 80 is 12"),
    ("what is twenty percent of fifty", "20% of 50 is 10"),
    ("what's 18% tip on 64.50", "An 18% tip on $64.50 is $11.61, total $76.11"),
    ("what's an 18 percent tip on sixty four fifty",
     "An 18% tip on $64.50 is $11.61, total $76.11"),
    ("what's a 20% tip on $45", "A 20% tip on $45 is $9, total $54"),
    ("what's 20% off $50", "20% off $50 is $40"),
    ("what percent of 80 is 12", "12 is 15% of 80"),
    ("12 is what percent of 80", "12 is 15% of 80"),
    ("what is half of 80", "half of 80 is 40"),
    # arithmetic in digits and words
    ("2+2", "2 plus 2 is 4"),
    ("what is 7 x 8", "7 times 8 is 56"),
    ("What is twelve times seven?", "12 times 7 is 84"),
    ("one hundred and twenty three plus four", "123 plus 4 is 127"),
    ("sixty-four point five divided by two", "64.5 divided by 2 is 32.25"),
    ("what's 1,250 times 3", "1,250 times 3 is 3,750"),
    ("what is 2 to the power of 10", "2 to the power of 10 is 1,024"),
    ("square root of 144", "The square root of 144 is 12"),
    ("what is 10 divided by 0", "You can't divide by zero"),
    # conversions
    ("convert 5 pounds to kilograms", "5 lb is 2.27 kg"),
    ("how many grams in 3 ounces", "3 oz is 85.05 g"),
    ("what's 70 F in celsius", "70°F is 21.1°C"),
    ("100 c to f", "100°C is 212°F"),
    ("10 km in miles", "10 km is 6.21 mi"),
    ("how many ml in a cup", "1 cup is 236.59 ml"),
    ("three tablespoons to ml", "3 tbsp is 44.36 ml"),
    ("5 feet 10 inches in cm", "5 ft 10 in is 177.8 cm"),
]


@pytest.mark.parametrize("q,want", CASES)
def test_exact_answers(q, want):
    assert calc.answer(q) == want


@pytest.mark.parametrize("q", [
    "set volume to 30", "open safari", "what is the capital of France",
    "what time is it", "tell me a joke", "", "two thousand twenty six minus "
    "nineteen ninety", "remind me in 5 minutes", "who won the game"])
def test_non_math_falls_back(q):
    assert calc.answer(q) is None


@pytest.mark.parametrize("q", [c[0] for c in CASES])
def test_answers_fit_bubble(q):
    assert len(calc.answer(q).split()) <= 12


@pytest.mark.parametrize("v,src,dst,want", [
    (1, "kg", "lb", 2.2046), (1, "mi", "km", 1.6093), (1, "m", "ft", 3.2808),
    (1, "in", "cm", 2.54), (1, "oz", "g", 28.3495), (1, "cups", "ml", 236.588),
    (1, "tbsp", "ml", 14.7868), (32, "F", "C", 0.0), (-40, "C", "F", -40.0),
])
def test_convert_factors(v, src, dst, want):
    r = calc.convert(v, src, dst)
    assert r is not None and abs(r[0] - want) < 1e-3


def test_convert_incompatible_units():
    assert calc.convert(1, "kg", "km") is None


@pytest.mark.parametrize("text,want", [
    ("twenty one", "21"), ("one hundred and five", "105"),
    ("three thousand two hundred", "3200"), ("seven point five", "7.5"),
])
def test_spoken_numbers(text, want):
    assert calc.normalize(text)[0].strip() == want
