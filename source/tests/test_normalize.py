"""Unit tests for the number/date cleaning helpers. No API key needed."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wtq import normalize  # noqa: E402
from wtq.level2 import safe_eval  # noqa: E402


def test_parse_amount_basic():
    assert normalize.parse_amount("Rs. 19,964") == 19964
    assert normalize.parse_amount("19964") == 19964
    assert normalize.parse_amount(900) == 900
    assert normalize.parse_amount("663.51") == 663.51


def test_parse_amount_credit():
    assert normalize.parse_amount("38209CR") == -38209
    assert normalize.parse_amount("0.53 CR") == -0.53
    assert normalize.parse_amount("(0.53)") == -0.53


def test_parse_amount_empty():
    assert normalize.parse_amount("") is None
    assert normalize.parse_amount(None) is None
    assert normalize.parse_amount("N/A") is None


def test_parse_date():
    assert normalize.parse_date("22nd Sep 2026") == "2026-09-22"
    assert normalize.parse_date("2026-04-21") == "2026-04-21"
    assert normalize.parse_date("MAR 2026", month_only=True) == "2026-03"
    assert normalize.parse_date("2026-04", month_only=True) == "2026-04"
    assert normalize.parse_date("", ) is None


def test_clean_identifiers():
    obj = {"provider": "KE", "account_number": "123", "meter_no": "x", "tariff": "A1-R"}
    cleaned = normalize.clean_identifiers(obj)
    assert "account_number" not in cleaned
    assert "meter_no" not in cleaned
    assert cleaned["provider"] == "KE"


def test_safe_eval():
    assert safe_eval("569.62 / 3430.24 * 100") == 569.62 / 3430.24 * 100
    assert safe_eval("round(2+3*4, 2)") == 14
    assert safe_eval("__import__('os')") is None  # rejects anything non-arithmetic


if __name__ == "__main__":
    import traceback
    passed = failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                passed += 1
                print(f"PASS {name}")
            except Exception:
                failed += 1
                print(f"FAIL {name}")
                traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
