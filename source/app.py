"""Optional web UI for a live demo. It is NOT part of the scored pipeline.

This file only draws the screen. It calls the SAME extraction and answer code as
the command-line tool (wtq.level1 and wtq.level2), so the model, the prompts, and
the accuracy are exactly the same as the CLI. The scored path is run.py -> CSV
files, which never imports this file, so this UI cannot change any result.

Run it like this:
    cd source
    pip install -r requirements-ui.txt
    streamlit run app.py
"""
import html
import json
import tempfile
from pathlib import Path

import streamlit as st

from wtq import level1, level2

# ---------------------------------------------------------------------------
# Page setup.
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Utility Bill Decoder",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Styling (visual only — no effect on results).
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

      html, body, [class*="css"], .stMarkdown, p, div, span, label { font-family: 'Inter', sans-serif; }
      .stApp {
        background:
          radial-gradient(1100px 500px at 12% -5%, #EDE9FF 0%, rgba(237,233,255,0) 55%),
          radial-gradient(900px 500px at 100% 0%, #E6F0FF 0%, rgba(230,240,255,0) 50%),
          #F6F7FD;
      }
      .block-container { padding-top: 1.4rem; max-width: 1200px; }
      #MainMenu, footer { visibility: hidden; }

      /* ---------- Hero ---------- */
      .hero {
        position: relative; overflow: hidden;
        background: linear-gradient(120deg, #6D5EF8 0%, #8B6DF2 45%, #4F8DF9 100%);
        padding: 2.1rem 2.2rem; border-radius: 22px; margin-bottom: 1.4rem;
        box-shadow: 0 20px 45px rgba(109,94,248,.35);
      }
      .hero::after {
        content:""; position:absolute; right:-60px; top:-60px;
        width:230px; height:230px; border-radius:50%;
        background: radial-gradient(circle, rgba(255,255,255,.28), rgba(255,255,255,0) 70%);
      }
      .hero h1 { font-family:'Poppins',sans-serif; color:#fff; margin:0; font-size:2.1rem; font-weight:700; letter-spacing:.3px; }
      .hero p  { color:#EEEAFF; margin:.45rem 0 0; font-size:1.05rem; max-width:640px; }
      .pill {
        display:inline-block; padding:.3rem .85rem; border-radius:999px;
        background: rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.25);
        color:#fff; font-size:.8rem; font-weight:600; margin:.65rem .4rem 0 0;
        backdrop-filter: blur(4px);
      }

      /* ---------- Section titles ---------- */
      .section-title { font-family:'Poppins',sans-serif; font-weight:600; font-size:1.2rem; margin:.3rem 0 .8rem; color:#141A2E; }

      /* ---------- Provider badge ---------- */
      .pbadge { display:inline-block; padding:.3rem .9rem; border-radius:10px; color:#fff; font-weight:700; font-size:.9rem; letter-spacing:.4px; }

      /* ---------- Metric cards ---------- */
      .mgrid { display:grid; grid-template-columns: repeat(4, 1fr); gap:.8rem; margin:.2rem 0 1rem; }
      .mcard {
        background:#fff; border:1px solid #ECEBF6; border-radius:16px; padding:.9rem 1rem;
        box-shadow: 0 6px 18px rgba(20,26,46,.05); position:relative; overflow:hidden;
      }
      .mcard::before { content:""; position:absolute; left:0; top:0; height:100%; width:4px; background:var(--accent,#6D5EF8); }
      .micon { font-size:1.1rem; }
      .mlabel { color:#8A90A6; font-size:.72rem; font-weight:600; letter-spacing:.6px; text-transform:uppercase; margin-top:.2rem; }
      .mvalue { color:#141A2E; font-size:1.3rem; font-weight:700; font-family:'Poppins',sans-serif; line-height:1.25; }

      /* ---------- Tables ---------- */
      .wtq-table { width:100%; border-collapse:separate; border-spacing:0; font-size:.92rem; margin-top:.3rem; }
      .wtq-table th { text-align:left; color:#8A90A6; font-size:.72rem; letter-spacing:.5px; text-transform:uppercase; padding:.5rem .8rem; }
      .wtq-table td { background:#fff; padding:.6rem .8rem; border-top:1px solid #F0F0F8; }
      .wtq-table tr td:first-child { border-left:1px solid #F0F0F8; border-radius:10px 0 0 10px; }
      .wtq-table tr td:last-child { border-right:1px solid #F0F0F8; border-radius:0 10px 10px 0; text-align:right; font-weight:600; font-family:'Poppins',sans-serif; }
      .ttotal { text-align:right; color:#4A5070; font-weight:600; margin-top:.5rem; font-size:.92rem; }

      /* ---------- Answer + flag cards ---------- */
      .answer-card {
        background: linear-gradient(180deg,#F2FBF6 0%, #ECFaf2 100%);
        border:1px solid #CDEEDC; border-left:5px solid #1FA971;
        padding:1.1rem 1.3rem; border-radius:14px; font-size:1.05rem; line-height:1.6; color:#133c2a;
        box-shadow: 0 8px 22px rgba(31,169,113,.12);
      }
      .flag-card {
        background:#FFF7EA; border:1px solid #F3DBB0; border-left:5px solid #E8A33D;
        padding:.65rem 1rem; border-radius:12px; font-size:.86rem; margin-top:.7rem; color:#6b4e18;
      }

      /* ---------- Buttons ---------- */
      .stButton > button {
        border-radius:12px; font-weight:600; border:1px solid #E3E2F2; background:#fff; color:#4A4470;
        transition: all .15s ease;
      }
      .stButton > button:hover { border-color:#6D5EF8; color:#6D5EF8; transform: translateY(-1px); }
      .stButton > button[kind="primary"] {
        background: linear-gradient(120deg,#6D5EF8,#4F8DF9); color:#fff; border:none;
        box-shadow: 0 10px 22px rgba(109,94,248,.33);
      }
      .stButton > button[kind="primary"]:hover { filter:brightness(1.06); transform: translateY(-2px); color:#fff; }

      /* ---------- Uploader ---------- */
      [data-testid="stFileUploaderDropzone"] {
        background:#fff; border:2px dashed #CBC7EE; border-radius:16px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar.
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚡ Bill Decoder")
    st.markdown(
        "AI assistant that reads **K-Electric, LESCO & IESCO** electricity bills, "
        "extracts the details, and answers your questions in plain English."
    )
    st.markdown("---")
    st.markdown("**How it works**")
    st.markdown(
        "1. Upload a bill image\n"
        "2. Click **Extract bill details**\n"
        "3. Ask any question in plain English"
    )
    st.markdown("---")
    st.markdown("**Why it is accurate**")
    st.markdown(
        "- Reads the image directly with a vision model\n"
        "- Every calculation is **verified in code**\n"
        "- Says *null* instead of guessing"
    )
    st.markdown("---")
    st.caption("Model: Gemini 3.5 Flash-Lite")
    st.caption("Same engine as the command-line tool — accuracy is identical.")

# ---------------------------------------------------------------------------
# Hero header.
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero">
      <h1>⚡ Utility Bill Decoder</h1>
      <p>Turn any electricity bill into clear, structured details — and get plain-English answers in seconds.</p>
      <div>
        <span class="pill">🔌 K-Electric</span>
        <span class="pill">💡 LESCO</span>
        <span class="pill">⚙️ IESCO</span>
        <span class="pill">✅ Math verified in code</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Formatting helpers (display only).
# ---------------------------------------------------------------------------
PROVIDER_COLORS = {"KE": "#F26A21", "LESCO": "#1E9E57", "IESCO": "#1E6FB8"}
CHARGE_LABELS = {
    "energy": "Energy", "fixed": "Fixed", "fpa": "Fuel Price Adj.",
    "quarterly_adjustment": "Quarterly Adj.", "surcharge": "Surcharge",
    "meter_rent": "Meter Rent", "subsidy": "Subsidy", "other": "Other",
}
TAX_LABELS = {
    "gst": "GST / Sales Tax", "electricity_duty": "Electricity Duty",
    "income_tax": "Income Tax", "municipal_tax": "Municipal Tax", "other_tax": "Other Tax",
}


def money(value) -> str:
    if value is None:
        return "—"
    try:
        return f"Rs {value:,.2f}".replace(".00", "")
    except (TypeError, ValueError):
        return html.escape(str(value))


def shown(value) -> str:
    return "—" if value is None or value == "" else html.escape(str(value))


def metric_card(icon: str, label: str, value: str, accent: str) -> str:
    return (
        f'<div class="mcard" style="--accent:{accent}">'
        f'<div class="micon">{icon}</div>'
        f'<div class="mlabel">{label}</div>'
        f'<div class="mvalue">{value}</div></div>'
    )


def lines_table(items, label_map) -> str:
    if not items:
        return '<div class="ttotal" style="text-align:left;color:#8A90A6;">No separate lines (combined amount only).</div>'
    rows = ""
    for it in items:
        name = label_map.get(it.get("type", ""), str(it.get("type", "")))
        rows += f'<tr><td>{html.escape(name)}</td><td>{money(it.get("amount"))}</td></tr>'
    return (
        '<table class="wtq-table"><thead><tr><th>Type</th><th>Amount</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
    )


def render_level1(data: dict, flags: list) -> None:
    prov = data.get("provider")
    accent = PROVIDER_COLORS.get(prov, "#6D5EF8")
    badge = (
        f'<span class="pbadge" style="background:{accent}">{shown(prov)}</span>'
        if prov else '<span class="pbadge" style="background:#8A90A6">Unknown</span>'
    )
    st.markdown(
        f'<div class="section-title">📄 Extracted details &nbsp; {badge}</div>',
        unsafe_allow_html=True,
    )

    cards = [
        metric_card("🏢", "Provider", shown(prov), accent),
        metric_card("🏷️", "Tariff", shown(data.get("tariff")), "#6D5EF8"),
        metric_card("📅", "Bill month", shown(data.get("bill_month")), "#4F8DF9"),
        metric_card("⚡", "Units used", shown(data.get("units_consumed")), "#F2A51A"),
        metric_card("🧾", "Current bill", money(data.get("current_bill")), "#1E9E57"),
        metric_card("⏱️", "Due date", shown(data.get("due_date")), "#4F8DF9"),
        metric_card("✅", "Pay on time", money(data.get("payable_within_due_date")), "#1FA971"),
        metric_card("⚠️", "Pay if late", money(data.get("payable_after_due_date")), "#E8663D"),
    ]
    st.markdown(f'<div class="mgrid">{"".join(cards)}</div>', unsafe_allow_html=True)

    col_c, col_t = st.columns(2, gap="large")
    with col_c:
        st.markdown('<b>🔻 Charges</b>', unsafe_allow_html=True)
        st.markdown(lines_table(data.get("charges"), CHARGE_LABELS), unsafe_allow_html=True)
        st.markdown(f'<div class="ttotal">Total charges: {money(data.get("total_charges"))}</div>', unsafe_allow_html=True)
    with col_t:
        st.markdown('<b>🏛️ Taxes & duties</b>', unsafe_allow_html=True)
        st.markdown(lines_table(data.get("taxes"), TAX_LABELS), unsafe_allow_html=True)
        st.markdown(f'<div class="ttotal">Total taxes: {money(data.get("total_taxes"))}</div>', unsafe_allow_html=True)

    if flags:
        st.markdown(
            f'<div class="flag-card">⚠️ <b>Confidence note:</b> {html.escape(", ".join(flags))} '
            "— the printed totals did not line up exactly, worth a quick look.</div>",
            unsafe_allow_html=True,
        )

    with st.expander("View raw JSON / download"):
        st.json(data)
        st.download_button(
            "⬇️ Download JSON",
            data=json.dumps(data, ensure_ascii=False, indent=2),
            file_name=f"{st.session_state.get('bill_id','bill')}.json",
            mime="application/json",
        )


# ---------------------------------------------------------------------------
# Upload.
# ---------------------------------------------------------------------------
EXAMPLES = [
    ("💰 Tax share", "How much of my bill is taxes, and what percentage of the total is that?"),
    ("📊 Average use", "What is my average monthly consumption over the history shown on the bill?"),
    ("📅 Amount & due date", "What is the total amount due and by what date must I pay it?"),
    ("📈 Highest month", "Which month in my usage history had the highest consumption, and how many units?"),
]

uploaded = st.file_uploader("📤 Upload a bill image (.png / .jpg)", type=["png", "jpg", "jpeg"])

if uploaded is None:
    st.info("👆 Upload a K-Electric, LESCO or IESCO bill image to get started.")
    st.stop()

# Save the uploaded image to a temporary file, because the engine reads from a path.
tmp = Path(tempfile.gettempdir()) / uploaded.name
tmp.write_bytes(uploaded.getvalue())
# The file name (e.g. KESC_0002.png) gives the provider hint, same as the CLI.
st.session_state["bill_id"] = Path(uploaded.name).stem

left, right = st.columns([1, 1.3], gap="large")

with left:
    st.markdown('<div class="section-title">🖼️ Bill image</div>', unsafe_allow_html=True)
    st.image(uploaded, use_container_width=True)

with right:
    if st.button("🔍  Extract bill details", type="primary", use_container_width=True):
        with st.spinner("Reading the bill with the vision model…"):
            data, flags = level1.extract_bill(tmp, st.session_state["bill_id"])
        st.session_state["l1"] = data
        st.session_state["flags"] = flags

    if "l1" in st.session_state:
        render_level1(st.session_state["l1"], st.session_state.get("flags", []))
    else:
        st.info("Click **Extract bill details** to read this bill.")

# ---------------------------------------------------------------------------
# Level 2 — ask a question.
# ---------------------------------------------------------------------------
st.divider()
st.markdown('<div class="section-title">💬 Ask a question about this bill</div>', unsafe_allow_html=True)

if "question" not in st.session_state:
    st.session_state["question"] = EXAMPLES[0][1]

st.caption("Quick questions:")
chip_cols = st.columns(len(EXAMPLES))
for i, (label, q) in enumerate(EXAMPLES):
    if chip_cols[i].button(label, key=f"ex{i}", use_container_width=True):
        st.session_state["question"] = q

st.text_input("Your question", key="question")

if st.button("✨  Get answer", type="primary"):
    if "l1" not in st.session_state:
        st.warning("Please extract the bill details first (button above).")
    else:
        with st.spinner("Working out the answer (the math is verified in code)…"):
            ans = level2.answer_bill(
                tmp,
                st.session_state["bill_id"],
                json.dumps(st.session_state["l1"], ensure_ascii=False),
                [{"question_id": "Q1", "question": st.session_state["question"]}],
            )
        st.markdown(f'<div class="answer-card">{html.escape(ans["Q1"])}</div>', unsafe_allow_html=True)
