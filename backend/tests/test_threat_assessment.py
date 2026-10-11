
from app.services.threat_assessment import assess_potential_threat


def test_vessel_detection_alone_does_not_prove_threat():
    result = assess_potential_threat({"boat": 4})

    assert result["score"] == 0
    assert result["level"] == "NO_RULE_TRIGGERED"
    assert result["human_review_required"] is True


def test_combined_indicators_raise_review_priority():
    result = assess_potential_threat(
        {"boat": 2},
        restricted_zone_entry=True,
        ais_status="mismatch",
        near_protected_asset=True,
    )

    assert result["score"] == 80
    assert result["level"] == "HIGH_PRIORITY_REVIEW"
    assert result["score_is_probability"] is False
    assert len(result["indicators"]) == 4


def test_context_without_vessel_requires_separate_review():
    result = assess_potential_threat(
        {},
        restricted_zone_entry=True,
        ais_status="missing",
    )

    assert result["level"] == "CONTEXT_REVIEW_REQUIRED"
    assert result["human_review_required"] is True
