import re
import unicodedata

from rapidfuzz import fuzz, process
from transliterate import translit


FUZZY_TERM_THRESHOLD = 85
CANONICAL_TERMS = ("ibuprofen",)
COMMON_TYPOS = {
    "ibuprophen": "ibuprofen",
}


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.replace("ё", "е").replace("№", " n ")
    text = _transliterate_to_latin(text)
    text = re.sub(r"[^a-z0-9]+", " ", text)

    tokens = [_canonicalize_token(token) for token in text.split()]
    return " ".join(tokens)


def similarity(left: object, right: object) -> float:
    return fuzz.ratio(normalize(left), normalize(right))


def _transliterate_to_latin(text: str) -> str:
    return translit(text, "ru", reversed=True)


def _canonicalize_token(token: str) -> str:
    if token in COMMON_TYPOS:
        return COMMON_TYPOS[token]

    if token.isdigit() or len(token) < 4:
        return token

    match = process.extractOne(
        token,
        CANONICAL_TERMS,
        scorer=fuzz.ratio,
        score_cutoff=FUZZY_TERM_THRESHOLD,
    )
    return match[0] if match else token
