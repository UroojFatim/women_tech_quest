"""WTQ Utility Bill Decoder — CLI entry point.

Usage (test day, with the supplied templates):
    python run.py --bills ../test/bills --level1 ../test/csv/level1.csv \
        --level2 ../test/csv/level2.csv --out ../output

Training / exploration (Level 1 only, derive bill ids from the folder):
    python run.py --bills ../train.../train/bills --out ../output
"""
import argparse
import csv
import json
import sys
from pathlib import Path

from wtq import level1, level2, report

IMAGE_EXTS = (".png", ".jpg", ".jpeg")


def find_image(bills_dir: Path, bill_id: str) -> Path | None:
    for ext in IMAGE_EXTS:
        p = bills_dir / f"{bill_id}{ext}"
        if p.exists():
            return p
    # fall back: match by file stem, any supported extension
    for p in bills_dir.iterdir():
        if p.stem == bill_id and p.suffix.lower() in IMAGE_EXTS:
            return p
    return None


def read_level1_ids(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return [row["bill_id"] for row in csv.DictReader(f)]


def read_level2_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def discover_ids(bills_dir: Path) -> list[str]:
    ids = sorted({p.stem for p in bills_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS})
    return ids


def run_level1(bills_dir, ids, out_dir, status):
    rows = []
    for bill_id in ids:
        img = find_image(bills_dir, bill_id)
        entry = {"bill_id": bill_id, "status": "ok", "flags": [], "provider": None}
        if img is None:
            print(f"  [L1] {bill_id}: image not found", file=sys.stderr)
            data = {}
            entry["status"] = "no_image"
        else:
            try:
                data, flags = level1.extract_bill(img, bill_id)
                entry["flags"] = flags
                entry["provider"] = data.get("provider")
                if flags:
                    print(f"  [L1] {bill_id}: {data.get('provider')} (flags: {flags})")
                else:
                    print(f"  [L1] {bill_id}: {data.get('provider')} ok")
            except Exception as e:  # noqa: BLE001
                print(f"  [L1] {bill_id}: ERROR {e}", file=sys.stderr)
                data = {}
                entry["status"] = "error"
        rows.append((bill_id, json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
        status[bill_id] = entry

    out = out_dir / "level1.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["bill_id", "json"])
        w.writerows(rows)
    print(f"Wrote {out} ({len(rows)} rows)")
    return {bid: js for bid, js in rows}


def run_level2(bills_dir, level2_path, l1_by_id, out_dir, status):
    rows = read_level2_rows(level2_path)
    # group questions by bill_id preserving order
    by_bill: dict[str, list[dict]] = {}
    for r in rows:
        by_bill.setdefault(r["bill_id"], []).append(r)

    answers: dict[tuple, str] = {}
    for bill_id, qrows in by_bill.items():
        img = find_image(bills_dir, bill_id)
        questions = [{"question_id": q["question_id"], "question": q["question"]} for q in qrows]
        if img is None:
            for q in questions:
                answers[(bill_id, q["question_id"])] = "The bill image was not available."
            continue
        try:
            ans = level2.answer_bill(img, bill_id, l1_by_id.get(bill_id, "{}"), questions)
            for qid, text in ans.items():
                answers[(bill_id, qid)] = text
            print(f"  [L2] {bill_id}: {len(ans)} answers")
        except Exception as e:  # noqa: BLE001
            print(f"  [L2] {bill_id}: ERROR {e}", file=sys.stderr)
            for q in questions:
                answers[(bill_id, q["question_id"])] = (
                    "The bill does not show the information needed to answer this."
                )

    out = out_dir / "level2.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["bill_id", "question_id", "question", "answer"])
        for r in rows:
            key = (r["bill_id"], r["question_id"])
            w.writerow([r["bill_id"], r["question_id"], r["question"],
                        answers.get(key, "").strip() or "No answer could be determined from the bill."])
    print(f"Wrote {out} ({len(rows)} rows)")


def main():
    ap = argparse.ArgumentParser(description="WTQ Utility Bill Decoder")
    ap.add_argument("--bills", required=True, type=Path, help="folder of bill images")
    ap.add_argument("--level1", type=Path, help="level1.csv template (optional)")
    ap.add_argument("--level2", type=Path, help="level2.csv template (optional)")
    ap.add_argument("--out", type=Path, default=Path("../output"), help="output folder")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    ids = read_level1_ids(args.level1) if args.level1 else discover_ids(args.bills)
    print(f"Processing {len(ids)} bills from {args.bills}")

    status: dict[str, dict] = {}
    print("\n== Level 1: extraction ==")
    l1_by_id = run_level1(args.bills, ids, args.out, status)

    if args.level2:
        print("\n== Level 2: questions ==")
        run_level2(args.bills, args.level2, l1_by_id, args.out, status)
    else:
        print("\n(no --level2 template given; skipping Level 2)")

    bills = [status[b] for b in ids if b in status]
    report.write_report(args.out, bills)
    report.print_summary(bills)


if __name__ == "__main__":
    main()
