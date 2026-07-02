"""Nepal phone number normalization & validation.

Pure, dependency-free helpers (easy to unit-test). Goal: take whatever a user
typed and produce an E.164 string (+977…) plus a number-type classification,
distinguishing Nepali mobile from landline.

Rules (Nepal, country code 977):
- Mobile: 10 national digits beginning 97/98 (NTC/Ncell/etc.) — sometimes 96
  for newer ranges. E.164: +977 + 10 digits.
- Landline: area code (1–3 digits, leading 0 nationally) + subscriber number;
  national significant number is typically 8–9 digits including the area code's
  leading-0-stripped form. E.164: +977 + (area code without leading 0) + number.

We accept input with +977, 977, 00977, a leading 0, spaces, dashes, parens.
"""
import re
from dataclasses import dataclass

from app.core.constants import ContactNumberType

NEPAL_CC = "977"
_MOBILE_PREFIXES = ("96", "97", "98")


@dataclass
class NormalizedNumber:
    raw: str
    e164: str | None          # +977… or None if invalid
    number_type: ContactNumberType
    is_valid: bool


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _strip_country(d: str) -> str:
    """Return the national-significant digits (drop +977/977/00977 and a single
    leading 0)."""
    if d.startswith("00977"):
        d = d[5:]
    elif d.startswith("977") and len(d) > 10:
        d = d[3:]
    # National trunk leading zero (landline dialing) — drop one.
    if d.startswith("0"):
        d = d[1:]
    return d


def normalize_nepal_number(
    raw: str, *, expected: ContactNumberType | None = None
) -> NormalizedNumber:
    """Normalize a single number. `expected` lets the caller hint mobile vs
    landline (from which field it came); we still classify from the digits."""
    if not raw or not raw.strip():
        return NormalizedNumber(raw=raw or "", e164=None,
                                number_type=ContactNumberType.UNKNOWN, is_valid=False)

    nsn = _strip_country(_digits(raw))

    # Mobile: exactly 10 digits with a known prefix.
    if len(nsn) == 10 and nsn[:2] in _MOBILE_PREFIXES:
        return NormalizedNumber(raw=raw, e164=f"+{NEPAL_CC}{nsn}",
                                number_type=ContactNumberType.MOBILE, is_valid=True)

    # Landline: 7–9 national digits (area code + subscriber), not a mobile range.
    if 7 <= len(nsn) <= 9 and nsn[:2] not in _MOBILE_PREFIXES:
        return NormalizedNumber(raw=raw, e164=f"+{NEPAL_CC}{nsn}",
                                number_type=ContactNumberType.LANDLINE, is_valid=True)

    # Couldn't confidently classify/validate.
    return NormalizedNumber(raw=raw, e164=None,
                            number_type=ContactNumberType.UNKNOWN, is_valid=False)
