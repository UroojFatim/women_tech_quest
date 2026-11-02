"""Level 1: extract one bill -> normalized JSON, with a code consistency self-check."""
from pathlib import Path
from typing import Any, Dict, List, Tuple

from . import llm, prompts, schema

TOLERANCE = 1.0  # numbers are accepted within +/-1


def provider_hint_from_id(bill_id: str) -> str | None:
    prefix = bill_id.split("_")[0].upper()
    if prefix == "KESC":
        return "KE"
    if prefix in {"LESCO", "IESCO"}:
        return prefix
    return None


def _sum(lines: List[Dict[str, Any]]) -> float:
    return sum(x["amount"] for x in lines if isinstance(x.get("amount"), (int, float)))


def consistency_flags(data: Dict[str, Any]) -> List[str]:
    """Check whether the printed totals add up. We only report problems here and
    never change the printed values (the task says: extract as printed)."""
    flags: List[str] = []
    tc, tt = data.get("total_charges"), data.get("total_taxes")
    cb, arr = data.get("current_bill"), data.get("arrears")
    pay = data.get("payable_within_due_date")

    if tc is not None and data["charges"]:
        if abs(_sum(data["charges"]) - tc) > TOLERANCE:
            flags.append("charges_sum!=total_charges")
    if tc is not None and tt is not None and cb is not None:
        if abs((tc + tt) - cb) > TOLERANCE:
            flags.append("charges+taxes!=current_bill")
    if cb is not None and pay is not None:
        base = cb + (arr or 0)
        if abs(base - pay) > TOLERANCE:
            flags.append("current_bill+arrears!=payable_within_due_date")
    return flags


def extract_bill(image_path: Path, bill_id: str) -> Tuple[Dict[str, Any], List[str]]:
    hint = provider_hint_from_id(bill_id)
    hint_line = f"\nThe file name indicates the provider is {hint}." if hint else ""
    prompt = prompts.EXTRACTION_PROMPT.format(
        template=prompts.LEVEL1_JSON_TEMPLATE, hint=hint_line
    )
    raw = llm.generate_json(prompt, image_path=image_path, cache_key=f"l1:{bill_id}")
    data = schema.normalize_level1(raw, provider_hint=hint)

    flags = consistency_flags(data)
    if flags:
        data = _targeted_reread(image_path, bill_id, data, flags, hint)
        flags = consistency_flags(data)  # re-evaluate after the re-read

    # The re-read can correct total_taxes. Re-apply the combined-tax rule so a
    # single stale tax line is not left behind when the bill prints one combined
    # tax figure (this is the IESCO layout).
    tt = data.get("total_taxes")
    if len(data["taxes"]) == 1 and tt is not None and abs(data["taxes"][0]["amount"] - tt) > 1:
        data["taxes"] = []
    return data, flags


def _targeted_reread(image_path, bill_id, data, flags, hint) -> Dict[str, Any]:
    """Look again at only the fields that are part of the failed checks."""
    fields = ["total_charges", "total_taxes", "current_bill", "arrears",
              "payable_within_due_date", "payable_after_due_date"]
    current = {k: data.get(k) for k in fields}
    prompt = prompts.RECHECK_PROMPT.format(fields=", ".join(fields), current=current)
    try:
        raw = llm.generate_json(prompt, image_path=image_path, cache_key=f"l1recheck:{bill_id}")
    except Exception:
        return data
    for k in fields:
        if k in raw:
            from . import normalize
            val = normalize.parse_amount(raw[k])
            if val is not None:
                data[k] = val
    return data
