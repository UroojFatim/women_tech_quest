"""Clean the model's output into the exact formats the task needs.

There is no AI call in this file, so the same input always gives the same result.
The model is told to return clean values, but these helpers are a safety net so a
formatting slip never costs points: remove currency text and commas, make credits
negative, fix date formats, and make sure every required field is present.
"""
import re
from typing import Any, Optional

MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "sept": "09", "oct": "10", "nov": "11",
    "dec": "12",
}

# Personal-identifier-ish keys that must never appear in output.
_FORBIDDEN_KEYS = re.compile(
    r"(name|address|cnic|account|reference|consumer|meter.?no|ref.?no)", re.I
)


def parse_amount(value: Any) -> Optional[float]:
    """'Rs. 19,964' -> 19964 ; '38209CR' -> -38209 ; '(0.53)' -> -0.53 ; '' -> None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return _as_number(float(value))
    s = str(value).strip()
    if s == "" or s.lower() in {"null", "none", "n/a", "na", "-"}:
        return None

    negative = False
    # Credit markers.
    if re.search(r"cr\b", s, re.I) or s.startswith("(") and s.endswith(")"):
        negative = True
    s = re.sub(r"\b(cr|dr)\b", "", s, flags=re.I)
    s = s.strip("()")
    # Remove currency labels and thousands separators, keep sign/decimal.
    s = re.sub(r"(rs\.?|pkr|rupees)", "", s, flags=re.I)
    s = s.replace(",", "").replace(" ", "")
    if s.startswith("-"):
        negative = True
        s = s[1:]
    s = re.sub(r"[^0-9.]", "", s)
    if s in {"", "."}:
        return None
    try:
        num = float(s)
    except ValueError:
        return None
    if negative:
        num = -num
    return _as_number(num)


def _as_number(num: float) -> float:
    """Return int when the value is whole, to match printed integers."""
    if num == int(num):
        return int(num)
    return round(num, 2)


def parse_date(value: Any, month_only: bool = False) -> Optional[str]:
    """Convert a date to YYYY-MM-DD (or YYYY-MM when month_only is True)."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s.lower() in {"null", "none", "n/a"}:
        return None

    # Already correct.
    if month_only and re.fullmatch(r"\d{4}-\d{2}", s):
        return s
    if not month_only and re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) and month_only:
        return s[:7]
    if re.fullmatch(r"\d{4}-\d{2}", s) and not month_only:
        return None  # not enough info for a full date

    # e.g. "22nd Sep 2026", "22 Sep 2026", "Sep 2026", "MAR 2026"
    low = s.lower()
    mon = next((MONTHS[k] for k in MONTHS if re.search(rf"\b{k}", low)), None)
    year = re.search(r"\b(20\d{2})\b", s)
    day = re.search(r"\b(\d{1,2})(st|nd|rd|th)?\b", s)
    if mon and year:
        if month_only:
            return f"{year.group(1)}-{mon}"
        if day:
            return f"{year.group(1)}-{mon}-{int(day.group(1)):02d}"
    # dd/mm/yyyy or dd-mm-yyyy
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", s)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}" if month_only else f"{y}-{int(mo):02d}-{int(d):02d}"
    return None


def clean_identifiers(obj: Any) -> Any:
    """Recursively drop any key that looks like a personal identifier."""
    if isinstance(obj, dict):
        return {
            k: clean_identifiers(v)
            for k, v in obj.items()
            if not _FORBIDDEN_KEYS.search(str(k))
        }
    if isinstance(obj, list):
        return [clean_identifiers(v) for v in obj]
    return obj
