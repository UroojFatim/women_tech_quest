"""Level 2: answer the 12 questions per bill, with Python-verified arithmetic."""
import ast
import json
import operator
import re
from pathlib import Path
from typing import Any, Dict, List

from . import llm, prompts

# Safe arithmetic evaluator for the model's python_expression.
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.USub: operator.neg, ast.UAdd: operator.pos,
    ast.Pow: operator.pow, ast.Mod: operator.mod,
}


def safe_eval(expr: str) -> float | None:
    """Evaluate a pure-arithmetic expression (digits, + - * / ( ) . and round())."""
    if not expr or not isinstance(expr, str):
        return None
    try:
        node = ast.parse(expr, mode="eval").body
        return _eval_node(node)
    except Exception:
        return None


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "round":
        args = [_eval_node(a) for a in node.args]
        return round(*args)
    raise ValueError("unsupported expression")


def _fmt(num: float) -> str:
    if num == int(num):
        return str(int(num))
    return f"{round(num, 2)}"


def answer_bill(
    image_path: Path, bill_id: str, level1_json: str, questions: List[Dict[str, str]]
) -> Dict[str, str]:
    """Return {question_id: answer_text} for all questions of one bill."""
    context = _build_context(image_path, bill_id)
    q_block = "\n".join(f"{q['question_id']}: {q['question']}" for q in questions)
    prompt = prompts.LEVEL2_PROMPT.format(
        level1=level1_json,
        context=json.dumps(context, ensure_ascii=False),
        questions=q_block,
    )
    raw = llm.generate_json(prompt, image_path=image_path, cache_key=f"l2:{bill_id}")
    answers = raw.get("answers", []) if isinstance(raw, dict) else []

    by_id = {str(a.get("question_id")): a for a in answers if isinstance(a, dict)}
    result: Dict[str, str] = {}
    for q in questions:
        qid = q["question_id"]
        a = by_id.get(qid, {})
        result[qid] = _verify(a)
    return result


def _verify(a: Dict[str, Any]) -> str:
    """Replace the model's arithmetic with a Python-computed value when possible."""
    text = str(a.get("answer", "")).strip() or "The bill does not show the information needed to answer this."
    expr = a.get("python_expression")
    computed = safe_eval(expr) if expr else None
    if computed is None:
        return text
    # Accept the text if it already contains the computed value in any common form.
    stripped = re.sub(r"[,\s]", "", text)
    forms = {_fmt(computed), f"{round(computed, 2)}", f"{round(computed, 1)}", f"{int(round(computed))}"}
    if any(f in stripped for f in forms):
        return text
    # Otherwise the model's arithmetic disagrees with the verified calculation: correct it.
    return f"{text} (corrected value from the bill: {_fmt(computed)})"


def _build_context(image_path: Path, bill_id: str) -> Dict[str, Any]:
    try:
        ctx = llm.generate_json(
            prompts.CONTEXT_PACK_PROMPT, image_path=image_path, cache_key=f"ctx:{bill_id}"
        )
    except Exception:
        return {}
    # Safety net: monthly consumption units are physically non-negative. Strip any
    # minus sign the model may have bled in from an adjacent money column.
    hist = ctx.get("usage_history")
    if isinstance(hist, list):
        for e in hist:
            if isinstance(e, dict) and isinstance(e.get("units"), (int, float)):
                e["units"] = abs(e["units"])
    return ctx
