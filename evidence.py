"""The word-for-word check used everywhere: a quote counts only if it is really in the source text.

Spaces/line breaks and curly vs straight quote marks are ignored; everything else must match exactly.
"""
import re

_MARKS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                        " ": " ", "–": "-", "—": "-"})


def norm(text):
    return re.sub(r"\s+", " ", (text or "").translate(_MARKS)).strip()


def quote_in(quote, text):
    """True only if the (normalised) quote appears in the (normalised) text."""
    q = norm(quote)
    return len(q) >= 3 and q in norm(text)


def words(quote):
    return len(norm(quote).split())
