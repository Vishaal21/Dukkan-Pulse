"""Optional LLM layer: turns a recommendation's numbers into a detailed,
plain-English explanation for the shopkeeper.

Read only. The recommendation engine computes every number; the LLM only
explains them. If no LLM is configured (no API key), we return a deterministic
explanation built from the same numbers, so the feature still works offline.

Provider: Groq chat, model `openai/gpt-oss-120b`, via the OpenAI-compatible
chat-completions endpoint, called with plain httpx (no vendor SDK). This mirrors
the setup used in the ai-receposnist project.

Configuration (environment variables, or a backend/.env file - no hardcoded keys):
    GROQ_API_KEY   Groq API key (also accepts LLM_API_KEY).
    LLM_BASE_URL   default https://api.groq.com/openai/v1
    LLM_MODEL      default openai/gpt-oss-120b
"""
import json
import os
import re

import httpx

import recommendations


def _load_dotenv():
    """Load backend/.env if present, without overriding real environment vars."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()

LLM_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
LLM_MODEL = os.environ.get("LLM_MODEL", "openai/gpt-oss-120b")
# gpt-oss is a reasoning model: a small token cap gets used up by hidden
# thinking and leaves an empty reply, so no cap is set (same as ai-receposnist).
TIMEOUT_SECONDS = 60.0

_SYSTEM = (
    "Identity. You are DukaanPulse, a purchase planning assistant for a small Indian shop. "
    "Task. Explain ONE reorder recommendation to the shopkeeper in 2 to 3 short sentences of plain English. "
    "What to include, in this order: (1) what to order and how much, "
    "(2) the main reason the quantity is what it is, quoting the 'why' signals given "
    "(festival, weather, season) in plain words, and if usual_order differs from order_this_much, "
    "say the usual order and the new amount, "
    "(3) when to order and the supplier's delivery time. "
    "Use whole numbers. Bold the key action and the quantity using **...**. "
    "If stock lasts less than a day, say stock is running out now (do not name a past-sounding date). "
    "Hard rules. Only use the numbers and products given. Never invent numbers and never do arithmetic. "
    "Never mention internal codes or underscore words such as plan_ahead or order_now, "
    "use the plain timing phrase given instead. Never use an em dash. Do not write bullet lists."
)

ACTION_PHRASE = {
    "order_now": "order today",
    "order_soon": "order within the next few days",
    "plan_ahead": "plan a reorder soon",
    "no_action": "no action needed now",
}

_cache = {}


def _clean(text):
    """Normalise unicode spaces, remove em/en dashes, and tidy stray spacing."""
    text = text.replace("\u202f", " ").replace("\u00a0", " ")
    text = text.replace("\u2014", ",").replace("\u2013", ",")
    text = text.replace(" ,", ",").replace(" .", ".")
    return " ".join(text.split()).strip()


def _short_date(iso):
    if not iso:
        return None
    try:
        y, mo, d = iso.split("-")
        return f"{int(d)} {MONTHS[int(mo) - 1]}"
    except (ValueError, IndexError):
        return iso


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _facts(m):
    return {
        "product": m["name"],
        "unit": m["unit"],
        "current_stock": m["current_stock"],
        "daily_sales": m["velocity_per_day"],
        "stock_lasts_days": m["days_remaining"],
        "supplier_delivery_days": m["lead_time_days"],
        "order_by": _short_date(m["order_by_date"]),
        "expected_stockout": _short_date(m["expected_stockout_date"]),
        "usual_order": m["baseline_reorder_quantity"],
        "order_this_much": m["reorder_quantity"],
        "why": m["adjustment_reason"],
        "timing": ACTION_PHRASE.get(m["action"], ""),
    }


def _fallback(f):
    """Deterministic explanation when no LLM is configured."""
    if f["order_this_much"] <= 0:
        return f'{f["product"]} does not need an order right now.'
    lasts = f["stock_lasts_days"]
    lasts_txt = f"about {lasts} days" if lasts is not None else "a limited time"
    s = (f'Order about {f["order_this_much"]} {f["unit"]} of {f["product"]} '
         f'by {f["order_by"]}. Stock lasts {lasts_txt} and the supplier takes '
         f'{f["supplier_delivery_days"]} days.')
    if f["order_this_much"] > f["usual_order"]:
        if f["why"] and f["why"] != "Normal demand expected":
            s += (f' The usual order is {f["usual_order"]}, raised to '
                  f'{f["order_this_much"]} because {f["why"]}.')
        else:
            s += (f' The usual order is {f["usual_order"]}, which rounds up to '
                  f'{f["order_this_much"]} because your supplier packs in fixed sizes.')
    elif f["why"] and f["why"] != "Normal demand expected":
        s += f' {f["why"]}.'
    return s


def _call_llm(f):
    resp = httpx.post(
        f"{LLM_BASE_URL}/chat/completions",
        headers={"Authorization": "Bearer " + LLM_API_KEY},
        json={
            "model": LLM_MODEL,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": "Facts: " + json.dumps(f)},
            ],
        },
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return _clean(resp.json()["choices"][0]["message"]["content"])


def detailed_reason(product_id):
    """Detailed reason for one product. Raises KeyError for an unknown id."""
    metrics, _ = recommendations.product_metrics()
    m = next((x for x in metrics if x["product_id"] == product_id), None)
    if m is None:
        raise KeyError(product_id)

    if product_id in _cache:
        return _cache[product_id]

    f = _facts(m)
    if not LLM_API_KEY or f["order_this_much"] <= 0:
        # No model, or nothing to order: the short deterministic line reads best.
        out = {"reason": _fallback(f), "source": "demo"}
    else:
        try:
            out = {"reason": _call_llm(f), "source": "llm", "model": LLM_MODEL}
        except Exception:
            out = {"reason": _fallback(f), "source": "demo"}

    _cache[product_id] = out
    return out


# ---------------------------------------------------------------------------
# Chat: answer a free-text question about the store, grounded in the engine.
# ---------------------------------------------------------------------------
_CHAT_SYSTEM = (
    "Identity. You are DukaanPulse, a purchase planning assistant for a small Indian shop. "
    "How you talk. Answer in 2 to 4 short sentences of plain, simple English. Use whole numbers. "
    "Bold the key facts using **...**. If the question asks what to order, mention at most 3 products. "
    "Hard rules. Only use the numbers and product names in the store data given. "
    "Never invent products, prices, or numbers, and never do new arithmetic. "
    "If a budget_plan is present, list only its items and use its spent and remaining numbers, "
    "never add prices yourself. "
    "Never use an em dash. If the data does not cover the question, say so plainly."
)


def _budget_from(question):
    m = re.search(r"([\d,]{3,})", question or "")
    if not m:
        return None
    try:
        value = int(m.group(1).replace(",", ""))
    except ValueError:
        return None
    return value if value >= 100 else None


def _context_facts(question=""):
    ov = recommendations.overview()
    facts = {
        "as_of": ov["as_of"],
        "summary": ov["summary"],
        "top_reorders": [
            {
                "name": m["name"], "when": ACTION_PHRASE.get(m["action"], ""),
                "order": m["reorder_quantity"], "unit": m["unit"],
                "cost": m["reorder_cost"], "why": m["adjustment_reason"],
            }
            for m in ov["reorder_list"][:8]
        ],
        "slow_movers": [
            {"name": m["name"], "velocity": m["velocity_per_day"], "tied": m["tied_capital"]}
            for m in ov["slow_moving"][:6]
        ],
    }
    amount = _budget_from(question)
    if amount:
        plan = recommendations.budget_plan(amount)
        facts["budget_plan"] = {
            "budget": plan["budget"],
            "spent": plan["spent"],
            "remaining": plan["remaining"],
            "items": [{"name": i["name"], "qty": i["qty"], "cost": i["cost"]} for i in plan["items"]],
        }
    return facts


def _fallback_answer(question, facts):
    s = facts["summary"]
    return (
        f"You have {s['need_reorder']} products to reorder and {s['slow_moving']} slow sellers. "
        f"The top priority is {facts['top_reorders'][0]['name']} "
        f"(order {facts['top_reorders'][0]['order']} {facts['top_reorders'][0]['unit']}). "
        f"(Demo answer.)"
    ) if facts["top_reorders"] else "Nothing needs reordering right now. (Demo answer.)"


def _call_chat(question, facts):
    resp = httpx.post(
        f"{LLM_BASE_URL}/chat/completions",
        headers={"Authorization": "Bearer " + LLM_API_KEY},
        json={
            "model": LLM_MODEL,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": _CHAT_SYSTEM},
                {"role": "user", "content": "Store data: " + json.dumps(facts)
                                             + "\n\nQuestion: " + question},
            ],
        },
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return _clean(resp.json()["choices"][0]["message"]["content"])


def answer_question(question):
    """Answer a free-text question about the store (LLM if configured, else demo)."""
    question = (question or "").strip()
    if not question:
        return {"answer": "Please ask a question about your store.", "source": "demo"}
    facts = _context_facts(question)
    if LLM_API_KEY:
        try:
            return {"answer": _call_chat(question, facts), "source": "llm", "model": LLM_MODEL}
        except Exception:
            pass
    return {"answer": _fallback_answer(question, facts), "source": "demo"}
