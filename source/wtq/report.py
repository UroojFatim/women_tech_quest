"""Per-run report: console summary + output/_report.json."""
import json
from pathlib import Path
from typing import Any, Dict, List

from . import llm


def write_report(out_dir: Path, bills: List[Dict[str, Any]]) -> None:
    report = {
        "model_calls": llm.STATS["calls"],
        "cache_hits": llm.STATS["cache_hits"],
        "retries": llm.STATS["retries"],
        "bills": bills,
    }
    (out_dir / "_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def print_summary(bills: List[Dict[str, Any]]) -> None:
    print("\n" + "=" * 60)
    print(f"{'bill_id':<14}{'provider':<10}{'status':<10}flags")
    print("-" * 60)
    for b in bills:
        flags = ",".join(b.get("flags", [])) or "ok"
        print(f"{b['bill_id']:<14}{str(b.get('provider')):<10}{b.get('status',''):<10}{flags}")
    print("=" * 60)
    print(
        f"calls={llm.STATS['calls']} cache_hits={llm.STATS['cache_hits']} "
        f"retries={llm.STATS['retries']}\n"
    )
