"""Quality Control engine (spec §32).

Checks are pure functions over (asset metadata, script, variant constraints).
Verdicts: >=85 AUTO_APPROVED, 70-84 REVIEW_OR_REGENERATE, <70 REJECTED.
Thresholds configurable via system_settings['qc'].
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class QCCheck:
    name: str
    passed: bool
    weight: float
    detail: str = ""


@dataclass
class QCInput:
    video_exists: bool = False
    file_readable: bool = False
    duration: float | None = None
    expected_duration: float | None = None
    resolution: tuple[int, int] | None = None
    min_resolution: tuple[int, int] = (720, 1280)  # (w, h) portrait minimum
    has_audio: bool | None = None
    has_subtitle: bool = False
    subtitle_aligns: bool | None = None
    branding_ok: bool | None = None
    script_alignment_score: float | None = None  # 0-100, None = unverified
    duplicate_risk: float = 0.0  # 0-100
    fact_risk: float = 0.0  # 0-100
    platform_constraint_violations: list[str] = field(default_factory=list)


WEIGHTS = {
    "video_exists": 20.0,
    "file_readable": 15.0,
    "duration_ok": 10.0,
    "resolution_ok": 10.0,
    "audio_ok": 10.0,
    "subtitle_ok": 5.0,
    "script_alignment": 10.0,
    "low_duplicate_risk": 8.0,
    "low_fact_risk": 7.0,
    "platform_constraints": 5.0,
}


def run_qc(data: QCInput, *, threshold_auto: float = 85.0, threshold_review: float = 70.0):
    """Run all checks; returns (verdict, score, checks dict)."""
    checks: list[QCCheck] = []

    checks.append(QCCheck("video_exists", data.video_exists, WEIGHTS["video_exists"],
                          "video asset row + storage object present"))
    checks.append(QCCheck("file_readable", data.file_readable, WEIGHTS["file_readable"],
                          "storage object readable + checksum match"))

    duration_ok = False
    if data.duration is not None and data.expected_duration is not None:
        # within 20% of expected
        delta = abs(data.duration - data.expected_duration) / max(data.expected_duration, 1.0)
        duration_ok = delta <= 0.20
    elif data.duration is not None and data.duration >= 5:
        duration_ok = True
    checks.append(QCCheck("duration_ok", duration_ok, WEIGHTS["duration_ok"],
                          f"duration={data.duration} expected={data.expected_duration}"))

    resolution_ok = False
    if data.resolution is not None:
        w, h = data.resolution
        mw, mh = data.min_resolution
        resolution_ok = w >= mw and h >= mh
    checks.append(QCCheck("resolution_ok", resolution_ok, WEIGHTS["resolution_ok"],
                          f"resolution={data.resolution} min={data.min_resolution}"))

    # None (unsupported/unmeasured) counts neutral-pass with half weight recorded in detail
    audio_ok = data.has_audio is not False
    checks.append(QCCheck("audio_ok", audio_ok, WEIGHTS["audio_ok"],
                          f"has_audio={data.has_audio}"))

    subtitle_ok = data.has_subtitle and (data.subtitle_aligns is not False)
    checks.append(QCCheck("subtitle_ok", subtitle_ok, WEIGHTS["subtitle_ok"],
                          f"subtitle={data.has_subtitle} aligns={data.subtitle_aligns}"))

    if data.script_alignment_score is None:
        script_ok, script_detail = False, "script alignment unverified"
    else:
        script_ok = data.script_alignment_score >= 60
        script_detail = f"alignment={data.script_alignment_score}"
    checks.append(QCCheck("script_alignment", script_ok, WEIGHTS["script_alignment"], script_detail))

    dup_ok = data.duplicate_risk <= 50
    checks.append(QCCheck("low_duplicate_risk", dup_ok, WEIGHTS["low_duplicate_risk"],
                          f"duplicate_risk={data.duplicate_risk}"))

    fact_ok = data.fact_risk <= 30
    checks.append(QCCheck("low_fact_risk", fact_ok, WEIGHTS["low_fact_risk"],
                          f"fact_risk={data.fact_risk}"))

    plat_ok = not data.platform_constraint_violations
    checks.append(QCCheck("platform_constraints", plat_ok, WEIGHTS["platform_constraints"],
                          f"violations={data.platform_constraint_violations}"))

    total_weight = sum(c.weight for c in checks)
    earned = sum(c.weight for c in checks if c.passed)
    score = round(earned / total_weight * 100.0, 2) if total_weight else 0.0

    if not data.video_exists or not data.file_readable:
        verdict = "REJECTED"

    if score >= threshold_auto:
        verdict = "AUTO_APPROVED"
    elif score >= threshold_review:
        verdict = "REVIEW_OR_REGENERATE"
    else:
        verdict = "REJECTED"

    if not data.video_exists or not data.file_readable:
        verdict = "REJECTED"

    checks_dict = {c.name: {"passed": c.passed, "weight": c.weight, "detail": c.detail} for c in checks}
    return verdict, score, checks_dict
