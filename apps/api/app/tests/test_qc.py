"""QC engine tests (spec §32)."""
from app.engines.qc import QCInput, run_qc


def test_all_pass_auto_approved():
    data = QCInput(
        video_exists=True, file_readable=True, duration=58.0, expected_duration=60.0,
        resolution=(1080, 1920), has_audio=True, has_subtitle=True, subtitle_aligns=True,
        script_alignment_score=95, duplicate_risk=0, fact_risk=0,
    )
    verdict, score, checks = run_qc(data)
    assert verdict == "AUTO_APPROVED"
    assert score == 100.0
    assert all(c["passed"] for c in checks.values())


def test_missing_video_rejected():
    data = QCInput(video_exists=False, file_readable=False)
    verdict, score, _ = run_qc(data)
    assert verdict == "REJECTED"
    assert score < 70


def test_review_band():
    # 75% of weight passes -> REVIEW_OR_REGENERATE
    data = QCInput(
        video_exists=True, file_readable=True, duration=55, expected_duration=60,
        resolution=(720, 1280), has_audio=False, has_subtitle=False,
        script_alignment_score=None, duplicate_risk=0, fact_risk=0,
    )
    verdict, score, _ = run_qc(data)
    assert score == 75.0
    assert verdict == "REVIEW_OR_REGENERATE"


def test_high_duplicate_risk_fails_check():
    data = QCInput(video_exists=True, file_readable=True, duplicate_risk=80)
    verdict, score, checks = run_qc(data)
    assert checks["low_duplicate_risk"]["passed"] is False
    assert verdict in ("REVIEW_OR_REGENERATE", "REJECTED")


def test_duration_tolerance():
    base = dict(video_exists=True, file_readable=True, duration=60.0, expected_duration=60.0)
    _, score_ok, _ = run_qc(QCInput(**base))
    far = QCInput(**{**base, "duration": 20.0})
    _, score_far, checks = run_qc(far)
    assert checks["duration_ok"]["passed"] is False
    assert score_far < score_ok
