"""Level 1 schema definition and normalization into the exact required shape."""
from typing import Any, Dict

from . import normalize

PROVIDERS = {"KE", "LESCO", "IESCO"}
CHARGE_TYPES = {
    "energy", "fixed", "fpa", "quarterly_adjustment", "surcharge",
    "meter_rent", "subsidy", "other",
}
TAX_TYPES = {"gst", "electricity_duty", "income_tax", "municipal_tax", "other_tax"}

# Scalar fields and whether each is a date (and month-only).
NUMERIC_FIELDS = [
    "sanctioned_load_kw", "previous_reading", "current_reading", "units_consumed",
    "total_charges", "total_taxes", "current_bill", "arrears",
    "payable_within_due_date", "payable_after_due_date",
]
DATE_FIELDS = {
    "bill_month": True,       # month only -> YYYY-MM
    "reading_date": False,
    "issue_date": False,
    "due_date": False,
}

# The template, in the exact field order of the guide §5.1.
TEMPLATE_KEYS = [
    "provider", "tariff", "sanctioned_load_kw",
    "bill_month", "reading_date", "issue_date", "due_date",
    "previous_reading", "current_reading", "units_consumed",
    "charges", "total_charges",
    "taxes", "total_taxes",
    "current_bill", "arrears", "payable_within_due_date", "payable_after_due_date",
]


def normalize_level1(raw: Dict[str, Any], provider_hint: str | None = None) -> Dict[str, Any]:
    """Turn the model's raw output into the exact JSON object the task asks for."""
    raw = normalize.clean_identifiers(raw or {})
    out: Dict[str, Any] = {}

    # provider
    prov = str(raw.get("provider", "") or "").upper().strip()
    if prov not in PROVIDERS:
        prov = provider_hint if provider_hint in PROVIDERS else None
    out["provider"] = prov

    # tariff (kept as printed string)
    tariff = raw.get("tariff")
    out["tariff"] = str(tariff).strip() if tariff not in (None, "", "null") else None

    # numeric scalars
    for f in NUMERIC_FIELDS:
        out[f] = normalize.parse_amount(raw.get(f))

    # dates
    for f, month_only in DATE_FIELDS.items():
        out[f] = normalize.parse_date(raw.get(f), month_only=month_only)

    out["charges"] = _normalize_lines(raw.get("charges"), CHARGE_TYPES, "other")
    out["taxes"] = _normalize_lines(raw.get("taxes"), TAX_TYPES, "other_tax")

    # Combined-tax case: some bills (e.g. IESCO) print one single "Taxes" figure
    # instead of a per-tax breakdown. The task says to return taxes=[] and keep
    # the amount in total_taxes. If there is exactly one tax line and it does not
    # match the printed tax subtotal, treat that subtotal as the combined figure.
    tt = out.get("total_taxes")
    if len(out["taxes"]) == 1 and tt is not None and abs(out["taxes"][0]["amount"] - tt) > 1:
        out["taxes"] = []

    # Re-order to the template.
    return {k: out.get(k) for k in TEMPLATE_KEYS}


def _normalize_lines(lines: Any, valid_types: set, default_type: str) -> list:
    result = []
    if not isinstance(lines, list):
        return result
    for item in lines:
        if not isinstance(item, dict):
            continue
        amount = normalize.parse_amount(item.get("amount"))
        if amount is None or amount == 0:
            continue  # skip blank lines and lines printed as 0 (per the task rules)
        t = str(item.get("type", "") or "").lower().strip()
        if t not in valid_types:
            t = default_type
        # subsidy must be recorded as a deduction (negative)
        if t == "subsidy" and amount > 0:
            amount = -amount
        result.append({"type": t, "amount": amount})
    return result
