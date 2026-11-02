"""Pretty single-bill viewer — ideal for the demo video.

Shows one bill's Level 1 extraction (formatted JSON) and a few Level 2 answers,
and can open the bill image in your default viewer.

Usage:
    python show.py --bills ../test/bills --bill KESC_0008 --open
    python show.py --bills ../test/bills --bill KESC_0008 --questions "How much is tax?" "What is my due date?"
"""
import argparse
import json
import os
from pathlib import Path

from wtq import level1, level2

DEFAULT_QUESTIONS = [
    "How much of my bill is taxes, and what percentage of the total is that?",
    "What is my average monthly consumption over the history shown on the bill?",
    "What is the total amount due and by what date must I pay it?",
]

LINE = "=" * 64


def find_image(bills_dir: Path, bill_id: str) -> Path | None:
    for ext in (".png", ".jpg", ".jpeg"):
        p = bills_dir / f"{bill_id}{ext}"
        if p.exists():
            return p
    return None


def main():
    ap = argparse.ArgumentParser(description="Show one bill's extraction and answers")
    ap.add_argument("--bills", required=True, type=Path)
    ap.add_argument("--bill", required=True, help="bill id, e.g. KESC_0008")
    ap.add_argument("--questions", nargs="*", help="override the demo questions")
    ap.add_argument("--open", action="store_true", help="open the bill image in the default viewer")
    ap.add_argument("--no-answers", action="store_true", help="Level 1 only")
    args = ap.parse_args()

    img = find_image(args.bills, args.bill)
    if img is None:
        raise SystemExit(f"Image not found for {args.bill} in {args.bills}")

    print(LINE)
    print(f"  BILL: {args.bill}")
    print(f"  IMAGE: {img.resolve()}")
    print(LINE)
    if args.open:
        try:
            os.startfile(str(img.resolve()))  # Windows: open in default image viewer
        except Exception:
            pass

    print("\n--- LEVEL 1: EXTRACTED FIELDS ---\n")
    data, flags = level1.extract_bill(img, args.bill)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    if flags:
        print(f"\n  [confidence flags: {', '.join(flags)}]")

    if args.no_answers:
        return

    questions = args.questions or DEFAULT_QUESTIONS
    qlist = [{"question_id": f"Q{i}", "question": q} for i, q in enumerate(questions, 1)]
    print("\n--- LEVEL 2: ANSWERS ---\n")
    answers = level2.answer_bill(img, args.bill, json.dumps(data, ensure_ascii=False), qlist)
    for q in qlist:
        print(f"Q: {q['question']}")
        print(f"A: {answers[q['question_id']]}\n")
    print(LINE)


if __name__ == "__main__":
    main()
