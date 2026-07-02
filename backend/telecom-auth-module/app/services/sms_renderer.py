"""SMS rendering engine.

Templates use {{placeholder}} tokens. The engine:
  - extracts the distinct variables referenced in a body,
  - renders a body against a set of values (unknown tokens are left intact so a
    missing value is visible rather than silently dropped),
  - validates that the values needed to render a body are present, returning the
    missing ones (missing-variable detection).

Extensibility: the supported variable catalog is declared in SUPPORTED_VARIABLES
and the per-recipient value builder lives in build_recipient_values(). Adding a
new variable (e.g. {{order_id}}) means adding it to the catalog and supplying it
in the value builder — the regex/extraction/validation machinery is generic and
needs no change.
"""
from __future__ import annotations

import re
from typing import Iterable, Mapping

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")

# Catalog of first-class variables the platform knows how to fill. This is the
# single extension point for new placeholders.
SUPPORTED_VARIABLES: tuple[str, ...] = ("name", "phone", "company")


def extract_variables(body: str) -> list[str]:
    """Distinct variable names referenced in the body, in first-seen order."""
    return list(dict.fromkeys(_PLACEHOLDER_RE.findall(body or "")))


def render_template(body: str, values: Mapping[str, str | None]) -> str:
    """Replace {{var}} with values[var]; leave unknown/missing tokens intact."""
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = values.get(key)
        return str(value) if value is not None else match.group(0)

    return _PLACEHOLDER_RE.sub(replace, body or "")


def unsupported_variables(body: str) -> list[str]:
    """Variables referenced by the body that the platform cannot fill.

    Useful when validating a template/campaign up front: a body that references
    {{discount}} is fine syntactically but cannot be rendered unless 'discount'
    is in SUPPORTED_VARIABLES (or supplied explicitly)."""
    return [v for v in extract_variables(body) if v not in SUPPORTED_VARIABLES]


def missing_variables(body: str, values: Mapping[str, str | None]) -> list[str]:
    """Variables referenced by the body that have no (non-None) value supplied.

    These are the tokens that would render as their literal {{token}} form."""
    missing: list[str] = []
    for var in extract_variables(body):
        if values.get(var) is None:
            missing.append(var)
    return missing


def build_recipient_values(
    *, name: str | None, phone: str | None, company: str | None,
    extra: Mapping[str, str | None] | None = None,
) -> dict[str, str | None]:
    """Assemble the value map for one recipient. Extend here when adding a new
    supported variable."""
    values: dict[str, str | None] = {
        "name": name,
        "phone": phone,
        "company": company,
    }
    if extra:
        values.update(extra)
    return values


def sample_values() -> dict[str, str]:
    """Sample values for the template preview screen."""
    return {"name": "Aarav Sharma", "phone": "+9779812345678", "company": "Acme Pvt. Ltd."}
