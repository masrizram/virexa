"""Engagement classification + response policy tests (spec §36-37)."""
from app.engines.engagement import classify_and_decide, decide_action, risk_score


def test_question_low_risk_auto():
    r = classify_and_decide("Bagaimana cara pakai fitur ini?")
    assert r["category"] == "QUESTION"
    assert r["risk"] <= 20
    assert r["action"] == "AUTO_REPLY"


def test_complaint_never_auto_reply():
    r = classify_and_decide("Produk rusak, saya minta refund sekarang!")
    assert r["category"] == "COMPLAINT"
    assert r["action"] in ("DRAFT", "HUMAN_REQUIRED")
    assert r["action"] != "AUTO_REPLY"


def test_purchase_intent_detected():
    r = classify_and_decide("Berapa harga paketnya? mau beli")
    assert r["category"] == "PURCHASE_INTENT"


def test_abuse_escalates():
    r = classify_and_decide("lu bodoh banget")
    assert r["category"] == "ABUSE"
    assert r["action"] == "HUMAN_REQUIRED"


def test_sensitive_topic_human_required():
    r = classify_and_decide("bagaimana pandangan kamu soal politik dan agama?")
    assert r["risk"] >= 90
    assert r["action"] == "HUMAN_REQUIRED"


def test_unknown_question_mark_moderate():
    r = classify_and_decide("xyz abc ?")
    assert r["risk"] == 30.0
    assert r["action"] == "DRAFT"


def test_spam_flagged():
    r = classify_and_decide("FOLLOW BACK saya ya, klik link bio gratis!")
    assert r["category"] in ("SPAM",)
    assert r["action"] != "AUTO_REPLY" if r["risk"] > 20 else True


def test_boundary_20_21_60_61():
    assert decide_action(20, "QUESTION") == "AUTO_REPLY"
    assert decide_action(21, "QUESTION") == "DRAFT"
    assert decide_action(60, "QUESTION") == "DRAFT"
    assert decide_action(61, "QUESTION") == "HUMAN_REQUIRED"
