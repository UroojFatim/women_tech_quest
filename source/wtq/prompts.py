"""Prompts encoding every extraction/answer rule from the guide (§5, §6)."""

LEVEL1_JSON_TEMPLATE = """{
  "provider": "KE | LESCO | IESCO",
  "tariff": "string",
  "sanctioned_load_kw": number,
  "bill_month": "YYYY-MM",
  "reading_date": "YYYY-MM-DD",
  "issue_date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD",
  "previous_reading": number,
  "current_reading": number,
  "units_consumed": number,
  "charges": [{"type": "energy|fixed|fpa|quarterly_adjustment|surcharge|meter_rent|subsidy|other", "amount": number}],
  "total_charges": number,
  "taxes": [{"type": "gst|electricity_duty|income_tax|municipal_tax|other_tax", "amount": number}],
  "total_taxes": number,
  "current_bill": number,
  "arrears": number,
  "payable_within_due_date": number,
  "payable_after_due_date": number
}"""

EXTRACTION_PROMPT = """You are an expert at reading Pakistani electricity bills (K-Electric/KESC, LESCO, IESCO).
Bills may be tilted, partly in Urdu, photographed, and have personal details hidden by grey boxes.

Read the bill image and return ONE JSON object with exactly this structure (no extra keys, no markdown):
{template}

RULES — follow exactly:
- Extract values AS PRINTED. Do NOT recalculate, round, or correct any amount.
- Amounts are numbers in PKR. Remove "Rs."/commas: "Rs. 19,964" -> 19964.
- Credits and subsidies are NEGATIVE: "38209CR" -> -38209. A subsidy/relief line is a negative amount.
- Dates: "22nd Sep 2026" -> "2026-09-22"; "MAR 2026" -> "2026-03" (bill_month is month only).
- Use null for anything not printed, blank, covered by a grey box, or unreadable. NEVER guess. Use [] for an empty list.
- NEVER output personal identifiers: no names, address, CNIC, account/reference/consumer/meter numbers.

provider: one of KE, LESCO, IESCO. (K-Electric files use "KESC" but the provider value is "KE".){hint}
tariff: the tariff code exactly as printed, e.g. "A1-R" or "A-1a(01)".
sanctioned_load_kw: value labelled Sanc Load / S.Load / San Load, in kW.
due_date: last date to pay WITHOUT a late-payment surcharge.
previous_reading / current_reading / units_consumed: the printed meter readings and units.

CLASSIFY EVERY LINE BY THE SECTION IT IS PRINTED IN, NOT ITS NAME. A line printed in the tax / duties /
government section is a TAX (see taxes below) and must NEVER appear in charges — this includes municipal
lines like MUCT (KMC). A line in the electricity/charges breakdown is a charge.

charges: ONE entry per printed NON-ZERO line in the electricity/charges breakdown. Skip blank lines and lines printed as 0.
  Also capture charge lines shown in a SEPARATE BOX OR SECOND COLUMN of that same charges breakdown, or added
  AFTER the "Current Bill" subtotal into the grand total (some layouts, e.g. IESCO, print "Total FPA" or
  adjustments in a side column of the charges area). Do not miss these — but do not pull anything out of the tax section.
  Keep separate entries if the same type appears more than once (e.g. two energy lines).
  Types: energy (cost of units, "Variable Upto ... Units"/"Cost of Electricity"/"Energy Charges"/"Total Electricity Charges");
  fixed (fixed charges); fpa (fuel price adjustment, FPA / FCA / "Total FPA");
  quarterly_adjustment (QTA / Uniform Quarterly Adjustment); surcharge (e.g. Additional Surcharge (PHL), F.C Surcharge);
  meter_rent (meter/service rent); subsidy (government subsidy/relief, NEGATIVE); other (any other charge).
  Do NOT include late-payment surcharge / "payable after due date" amounts as charges.
total_charges: the printed charges subtotal (e.g. "Net Electricity Charges"), or null if no subtotal is printed.

taxes: ONE entry per printed line in the tax/government section. Classify by the SECTION it is printed in, not its name.
  If only a single combined tax figure is printed (e.g. one "Taxes 15.24%" line with no per-tax breakdown),
  return [] for taxes and put that amount in total_taxes.
  Types: gst (sales tax/GST, incl. GST on FPA); electricity_duty (ED); income_tax; municipal_tax (e.g. KE MUCT (KMC)); other_tax (extra/further tax, TV fee).
total_taxes: the printed tax subtotal, or null if no subtotal is printed.

current_bill: the printed amount for THIS month's bill.
arrears: previous dues carried forward; keep the printed sign; null if blank.
payable_within_due_date: amount payable by the due date.
payable_after_due_date: amount payable after the due date; if several late amounts are shown, use the HIGHEST.

Return only the JSON object."""

# A compact re-read prompt used when the code consistency check fails.
RECHECK_PROMPT = """Re-examine ONLY these fields on the same bill and return a JSON object with just these keys.
The current reading of them looks inconsistent with the printed totals, so look very carefully and return
the values exactly as printed (or null if truly unreadable). Do not change other fields.

Fields to re-read: {fields}
Current values: {current}

Return only a JSON object with those keys."""

CONTEXT_PACK_PROMPT = """Read this electricity bill image and return a JSON object capturing extra context useful
for answering customer questions. Structure (use null / [] when not printed):
{
  "usage_history": [{"month": "YYYY-MM or as printed", "units": number}],
  "max_demand": number,
  "load_factor": number,
  "num_days_billed": number,
  "slab_breakdown": [{"range": "string as printed", "units": number, "rate": number, "amount": number}],
  "notes": "any other short facts printed on the bill that help explain charges"
}
Rules: values AS PRINTED, numbers only (strip Rs/commas), no personal identifiers, English only.
usage_history is the printed monthly consumption history table if present. For each row read ONLY the
"UNITS" column — the monthly units consumed, which are NON-NEGATIVE whole numbers. Do NOT read the amount
from the adjacent "Bill (Rs.)" or "Payment (Rs.)" columns, and never carry a minus sign from those money
columns onto the units. If a bill is net-metering, still report the printed UNITS value as shown.
Return only the JSON object."""

LEVEL2_PROMPT = """You answer a customer's questions about THEIR electricity bill, in plain English.

You are given: (a) the structured extracted bill data (Level 1 JSON), (b) an extra context pack
(including any printed usage history), and (c) the bill image itself. Use ONLY information from this bill.

Extracted bill data (Level 1 JSON):
{level1}

Context pack:
{context}

Answer rules:
- Ground every answer in this bill. Do NOT use outside tariff/rate knowledge. If the bill does not show a
  needed value, say so plainly instead of guessing.
- Answer in English, even where the bill is in Urdu.
- Write a POLISHED, FINAL answer only. Do NOT think out loud, show drafts, or write "wait" / "let me
  reconsider" / "actually". State the conclusion directly. NEVER list candidate values you then reject.
- Be specific and complete: cite the actual figures from the bill, and where it adds value give the context
  (e.g. the amount AND what it is a share of AND the percentage). Keep it to 1-4 clear sentences.
- When a question concerns the usage/consumption history, use the EXACT monthly values from the context
  pack's `usage_history`. Build your `python_expression` from those exact numbers (e.g. list every value in
  the sum: (141+138+...+151)/13) so the computation uses ground-truth figures, not an approximation.
- For counting / "how many" questions: go through EVERY item in usage_history in order, list ALL that
  qualify (do not stop early or skip any), and set `python_expression` to a sum of 1s with exactly one
  "1" per qualifying item (e.g. three qualifying months -> "1+1+1"). State a count that equals that sum.
  If none qualify, use "0".
- Get numbers right. For ANY answer that involves a number derived by arithmetic (averages, differences,
  counts, percentages, shares, estimates), you MUST provide a `python_expression` of pure arithmetic
  (only digits, + - * / ( ) . and round()) that evaluates to the KEY figure, and list `numbers_used`.
  The number you state in `answer` MUST equal the result of your `python_expression`. Round money to 2
  decimals and percentages to 1 decimal in the text.
- Label estimates clearly and explain how you calculated them.
- If a question is ambiguous, state the interpretation you used (or answer both reasonable meanings).
- Never include personal identifiers.

Here are the questions. Return a JSON object: {{"answers": [{{"question_id": "...", "answer": "...",
"python_expression": "... or null", "numbers_used": {{}} }} ]}} with one entry per question, in order.

Questions:
{questions}

Return only the JSON object."""
