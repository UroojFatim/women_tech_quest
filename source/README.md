# WTQ Utility Bill Decoder

An AI assistant that reads Pakistani electricity bills (K-Electric/KESC, LESCO,
IESCO) from images and produces two outputs:

- **Level 1 — Extraction:** one JSON object per bill (provider, tariff, dates,
  meter readings, itemized charges & taxes, totals, arrears, payable amounts).
- **Level 2 — Explanation:** plain-English answers to the 12 customer questions
  per bill, with arithmetic verified in code.

## How it works

Each bill image is sent directly to a **vision LLM** (Gemini 3.5 Flash-Lite) with
a strict prompt that encodes the competition's extraction rules, and the model
returns JSON. On top of that baseline the solution adds four reliability layers:

1. **Deterministic normalization** (`wtq/normalize.py`): strips `Rs.`/commas,
   turns `38209CR` into `-38209`, coerces dates to `YYYY-MM[-DD]`, fills every
   required field with `null` when absent, and strips any leaked identifier.
2. **Consistency self-check** (`wtq/level1.py`): in *code* (not the LLM) it checks
   that printed values hang together (`sum(charges) ≈ total_charges`,
   `charges+taxes ≈ current_bill`, …). On a mismatch it does one targeted re-read
   of just those fields. It **never overwrites printed values** — the rule is
   "extract as printed" — it only recovers obvious misreads and flags low
   confidence in `output/_report.json`.
3. **Code-verified Level 2 arithmetic** (`wtq/level2.py`): the model returns each
   numeric answer as a safe arithmetic expression, which Python evaluates — so
   averages, counts and percentages are exact.
4. **Context pack**: a 12-month usage-history extraction per bill grounds
   counting/averaging questions. Raw responses are cached in `cache/` for fast,
   rate-limit-friendly re-runs.

## Requirements

- **Python 3.12** (works on 3.11+).
- Dependencies in `requirements.txt`.

## Setup

```bash
cd source
python -m venv .venv && . .venv/Scripts/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env         # then edit .env and set API_KEY
```

Get a free Gemini key at https://aistudio.google.com (Get API key). Make one test
call first so you do not lose build time on setup.

## Run

On the official test set (with the supplied CSV templates):

```bash
python run.py --bills ../test/bills \
              --level1 ../test/csv/level1.csv \
              --level2 ../test/csv/level2.csv \
              --out ../output
```

This writes `output/level1.csv` (10 rows), `output/level2.csv` (120 rows), and a
diagnostic `output/_report.json`.

Training / exploration (Level 1 only, bill ids discovered from the folder):

```bash
python run.py --bills "../train-20261010T055653Z-1-001/train/bills" --out ../output
```

## Optional web UI (demo only)

A small Streamlit app (`app.py`) lets you upload one bill, see the extracted
fields, and ask a question, all in the browser. It is **only for demos**. It calls
the exact same engine as the command line (`wtq.level1` / `wtq.level2`), so the
model, prompts, and accuracy are identical. The scored path (`run.py` → CSV files)
does not use this file, so the UI cannot change any result.

```bash
pip install -r requirements-ui.txt
streamlit run app.py
```

## View one bill in the terminal (demo helper)

```bash
python show.py --bills ../test/bills --bill KESC_0002 --open
```
Shows that bill's extracted JSON and a few answers, and opens the image.

## Tests

```bash
python tests/test_normalize.py
```

## Configuration (.env)

| Variable | Purpose | Default |
|---|---|---|
| `MODEL_PROVIDER` | model provider | `google` |
| `MODEL_NAME` | model id | `gemini-3.5-flash-lite` |
| `API_KEY` | provider API key | — (required) |
| `TEMPERATURE` | sampling temperature | `0` |
| `MAX_RETRIES` | retry budget on rate limits | `5` |
| `USE_CACHE` | cache raw responses in `cache/` | `1` |

## AI usage

- **Models / APIs:** Google Gemini `gemini-3.5-flash-lite` via the `google-genai`
  SDK, for both Level 1 extraction and Level 2 answers. No other LLM/API is called.
- **Services:** none. No invoice/receipt extraction agents, no Azure/Textract/Mindee.
- **Local OCR:** none (direct vision model).
- **AI coding assistant:** Claude Code (Anthropic) was used to help write this code.
