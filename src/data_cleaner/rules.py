"""Single-value cleaning rules. Pure functions: a string in, a string (and maybe a problem) out.

Every rule returns the value unchanged when it cannot do better, plus a short problem
description, so nothing is ever guessed silently.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

# --- text ---------------------------------------------------------------------------------

_SPACES = re.compile(r"\s+")
EMPTY_TOKENS = {
    "na", "n/a", "n.a.", "null", "none", "nan", "nil", "-", "--", "—", "?", "#n/a",
    "undefined", "sin dato", "sin datos", "no aplica", "no tiene", "ninguno",
}  # fmt: skip


def squeeze(value: str) -> str:
    """Trim, turn non-breaking spaces into spaces, collapse runs of whitespace."""
    return _SPACES.sub(" ", value.replace(" ", " ")).strip()


def is_empty_token(value: str) -> bool:
    return value.strip().casefold() in EMPTY_TOKENS


def plain(value: str) -> str:
    """Comparison key: no accents, no case, single spaces."""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return _SPACES.sub(" ", value.casefold()).strip()


_PARTICLES = {"de", "del", "la", "las", "los", "y", "e", "da", "das", "do", "dos", "van",
              "von", "der", "den", "di", "le", "du"}  # fmt: skip


def _cap(word: str) -> str:
    parts = re.split(r"([-'’])", word)
    return "".join(p[:1].upper() + p[1:] if p not in "-'’" else p for p in parts)


def title_name(value: str) -> str:
    """'MARIA DE LOS ANGELES' -> 'Maria de los Angeles'. Mixed case is assumed intentional."""
    if not (value.isupper() or value.islower()):
        return value
    words = value.lower().split(" ")
    return " ".join(w if i and w in _PARTICLES else _cap(w) for i, w in enumerate(words))


# --- email --------------------------------------------------------------------------------

EMAIL = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$")
DOMAIN_TYPOS = {
    "gmial.com": "gmail.com", "gmal.com": "gmail.com", "gamil.com": "gmail.com",
    "gmail.con": "gmail.com", "gmail.co": "gmail.com", "gmail.cm": "gmail.com",
    "hotmial.com": "hotmail.com", "hotmai.com": "hotmail.com", "hotmail.con": "hotmail.com",
    "hotmal.com": "hotmail.com", "yaho.com": "yahoo.com", "yahoo.con": "yahoo.com",
    "outlok.com": "outlook.com", "outlook.con": "outlook.com", "iclod.com": "icloud.com",
}  # fmt: skip


def normalize_email(value: str, fix_typos: bool = True) -> tuple[str, list[str], str | None]:
    """Returns (value, rules applied, problem)."""
    rules = []
    s = value.strip()
    s2 = s.lower().removeprefix("mailto:").replace(" ", "").rstrip(".,;")
    if s2 != s:
        rules.append("email_format")
    if "@" in s2:
        local, domain = s2.rsplit("@", 1)
        if fix_typos and domain in DOMAIN_TYPOS:
            s2 = f"{local}@{DOMAIN_TYPOS[domain]}"
            rules.append("email_domain_typo")
    return s2, rules, None if EMAIL.match(s2) else "not a valid email address"


# --- phone --------------------------------------------------------------------------------

# Calling code and national number length (without trunk prefix).
COUNTRIES = {
    "CO": ("57", 10), "MX": ("52", 10), "US": ("1", 10), "ES": ("34", 9), "AR": ("54", 10),
    "CL": ("56", 9), "PE": ("51", 9), "EC": ("593", 9), "GB": ("44", 10), "DE": ("49", 11),
}  # fmt: skip
_EXTENSION = re.compile(r"\s*(?:ext\.?|extension|extensi[oó]n|x)\s*\d+\s*$", re.IGNORECASE)


def normalize_phone(value: str, country: str) -> tuple[str, str | None]:
    """Return the number in E.164 (+573001234567) or the original value and a problem."""
    s = _EXTENSION.sub("", value.strip())
    digits = re.sub(r"\D", "", s)
    international = s.startswith("+")
    if s.startswith("00"):
        digits, international = digits[2:], True
    code, length = COUNTRIES[country]

    if international:
        if 8 <= len(digits) <= 15:
            return "+" + digits, None
        return value, "phone number has an invalid length"
    if len(digits) == length:
        return f"+{code}{digits}", None
    if digits.startswith(code) and len(digits) == len(code) + length:
        return "+" + digits, None
    if digits.startswith("0") and len(digits) == length + 1:  # national trunk prefix
        return f"+{code}{digits[1:]}", None
    return value, f"does not look like a {country} phone number"


# --- dates --------------------------------------------------------------------------------

MONTHS = {
    "jan": 1, "january": 1, "ene": 1, "enero": 1, "feb": 2, "february": 2, "febrero": 2,
    "mar": 3, "march": 3, "marzo": 3, "apr": 4, "april": 4, "abr": 4, "abril": 4,
    "may": 5, "mayo": 5, "jun": 6, "june": 6, "junio": 6, "jul": 7, "july": 7, "julio": 7,
    "aug": 8, "august": 8, "ago": 8, "agosto": 8, "sep": 9, "sept": 9, "set": 9,
    "september": 9, "septiembre": 9, "setiembre": 9, "oct": 10, "october": 10,
    "octubre": 10, "nov": 11, "november": 11, "noviembre": 11, "dec": 12, "december": 12,
    "dic": 12, "diciembre": 12,
}  # fmt: skip

_ISO = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ T].*)?$")
_NUMERIC = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4}|\d{2})(?:[ T].*)?$")
_DAY_MONTH = re.compile(
    r"^(\d{1,2})(?:st|nd|rd|th)?[\s/.-]+(?:de\s+)?([^\W\d_]+)\.?[\s/.,-]+(?:de\s+)?(\d{4}|\d{2})$"
)
_MONTH_DAY = re.compile(r"^([^\W\d_]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})$")
_SERIAL = re.compile(r"^\d{5}(?:\.\d+)?$")


def _year(y: str) -> int:
    n = int(y)
    if len(y) == 2:
        return 2000 + n if n < 69 else 1900 + n
    return n


def _make(y: int, m: int, d: int) -> str | None:
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def numeric_date_parts(value: str) -> tuple[int, int] | None:
    """For dd/mm vs mm/dd detection: the two leading numbers of a numeric date."""
    m = _NUMERIC.match(value.strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


def parse_date(value: str, order: str = "DMY") -> str | None:
    """Return YYYY-MM-DD or None. `order` decides 03/04/2026: DMY = 3 April, MDY = March 4."""
    s = value.strip().lower()
    if m := _ISO.match(s):
        return _make(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if m := _NUMERIC.match(s):
        a, b, y = int(m.group(1)), int(m.group(2)), _year(m.group(3))
        return _make(y, b, a) if order == "DMY" else _make(y, a, b)
    if (m := _DAY_MONTH.match(s)) and m.group(2) in MONTHS:
        return _make(_year(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
    if (m := _MONTH_DAY.match(s)) and m.group(1) in MONTHS:
        return _make(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2)))
    if _SERIAL.match(s) and 20000 < float(s) < 80000:  # Excel serial date
        return (date(1899, 12, 30) + timedelta(days=int(float(s)))).isoformat()
    return None


# --- numbers ------------------------------------------------------------------------------

_CURRENCY = re.compile(r"(?i)us\$|r\$|\b(?:cop|usd|eur|mxn|ars|clp|pen|gbp|brl)\b|[€$£\s]")
_PLAIN_NUMBER = re.compile(r"^-?\d+(?:\.\d+)?$")
COMMA_DECIMAL = re.compile(r"^-?\d{1,3}(?:\.\d{3})+(?:,\d+)?$|^-?\d+,\d{1,2}$")
DOT_DECIMAL = re.compile(r"^-?\d{1,3}(?:,\d{3})+(?:\.\d+)?$|^-?\d+\.\d{1,2}$")


def strip_currency(value: str) -> str:
    s = _CURRENCY.sub("", value.strip())
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    if s.endswith("-") and s[:-1].replace(".", "").replace(",", "").isdigit():
        s = "-" + s[:-1]
    return s


def parse_number(value: str, decimal: str = ".") -> str | None:
    """'$ 1.234.567,50' with decimal=',' -> '1234567.5'. Returns None when it isn't a number."""
    s = strip_currency(value)
    if not s or "%" in s:
        return None
    s = s.replace(".", "").replace(",", ".") if decimal == "," else s.replace(",", "")
    if not _PLAIN_NUMBER.match(s):
        return None
    negative = s.startswith("-")
    whole, _, frac = s.lstrip("-").partition(".")
    whole, frac = whole.lstrip("0") or "0", frac.rstrip("0")
    out = whole + (f".{frac}" if frac else "")
    return "-" + out if negative and out != "0" else out
