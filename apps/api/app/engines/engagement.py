"""Engagement classification + response policy (spec §36-37).

Risk 0-20 AUTO_REPLY / 21-60 DRAFT / 61-100 HUMAN_REQUIRED.
High-risk categories never auto-reply. Every decision logged.
"""
from __future__ import annotations

CATEGORIES = [
    "QUESTION",
    "POSITIVE",
    "NEGATIVE",
    "COMPLAINT",
    "BUSINESS_LEAD",
    "PURCHASE_INTENT",
    "SPAM",
    "ABUSE",
    "SENSITIVE",
    "UNKNOWN",
]

# Categories that never auto-reply regardless of risk score.
NO_AUTO_REPLY = {"COMPLAINT", "ABUSE", "SENSITIVE"}

# Keyword heuristics (deterministic fallback when AI classification unavailable).
KEYWORD_RULES: dict[str, list[str]] = {
    "PURCHASE_INTENT": ["berapa harga", "berapa harganya", "how much", "how to buy", "mau beli",
                        "ingin beli", "price", "harga", "promokode", "promo code", "discount"],
    "BUSINESS_LEAD": ["kerjasama", "collab", "partnership", "b2b", "kerjasama bisnis", "investasi",
                      "sponsor", "media kit"],
    "COMPLAINT": ["refund", "scam", "penipuan", "tipu", "gagal", "rusak", "error", "tidak bisa",
                  "doesn't work", "broken", "money back"],
    "QUESTION": ["bagaimana", "gimana", "how", "what", "why", "kenapa", "kapan", "when",
                 "apa itu", "what is"],
    "NEGATIVE": ["jelek", "buruk", "bosan", "boring", "bad", "trash", "sucks", "mundur"],
    "POSITIVE": ["mantap", "keren", "bagus", "great", "awesome", "love", "thanks", "terima kasih",
                 "nice", "fire", "goat"],
    "SPAM": ["follow back", "follow4follow", "f4f", "check my", "dm me", "klik link", "click link",
             "sub4sub", "gratis", "free money", "crypto pump"],
    "ABUSE": ["bodoh", "goblok", "stupid", "idiot", "bangsat", "kontol", "fuck", "shit"],
}

BASE_RISK: dict[str, float] = {
    "QUESTION": 15,
    "POSITIVE": 5,
    "NEGATIVE": 55,
    "COMPLAINT": 75,
    "BUSINESS_LEAD": 30,
    "PURCHASE_INTENT": 20,
    "SPAM": 40,
    "ABUSE": 90,
    "SENSITIVE": 95,
    "UNKNOWN": 65,
}


def classify_by_keywords(body: str) -> str:
    text = (body or "").lower()
    if not text.strip():
        return "UNKNOWN"
    for category in ["ABUSE", "SPAM", "COMPLAINT", "PURCHASE_INTENT", "BUSINESS_LEAD",
                     "QUESTION", "NEGATIVE", "POSITIVE"]:
        for kw in KEYWORD_RULES[category]:
            if kw in text:
                return category
    return "UNKNOWN"


def risk_score(category: str, body: str = "") -> float:
    base = BASE_RISK.get(category, 65)
    text = (body or "").lower()
    # sensitive-topic escalation
    for kw in ["politik", "politik", "sara", "agama", "racism", "suicide", "bunuh diri", "terror",
               "teror", "anak", "child"]:
        if kw in text:
            return 95.0
    if category == "UNKNOWN" and "?" in text:
        return 30.0
    return float(base)


def decide_action(risk: float, category: str) -> str:
    """0-20 AUTO_REPLY / 21-60 DRAFT / 61-100 HUMAN_REQUIRED (spec §37)."""
    if category in NO_AUTO_REPLY:
        return "HUMAN_REQUIRED" if risk > 60 else "DRAFT"
    if risk <= 20:
        return "AUTO_REPLY"
    if risk <= 60:
        return "DRAFT"
    return "HUMAN_REQUIRED"


def classify_and_decide(body: str) -> dict:
    category = classify_by_keywords(body)
    risk = risk_score(category, body)
    action = decide_action(risk, category)
    return {"category": category, "risk": risk, "action": action}
