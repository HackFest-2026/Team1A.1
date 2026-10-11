"""Legacy field evidence stays separate and its mock analysis is labelled (ADR-010)."""
from app.services.field_operations.evidence_service import evidence_service as legacy
from app.services.field_operations.models import Evidence
from app.repositories.evidence_repository import evidence_repository


def test_mock_analysis_declares_itself_mock():
    ev = legacy.add_evidence(Evidence(incident_id="INC-X", evidence_type="PHOTO",
                                      file_name="flood_street.jpg", file_path="/fake/storage/flood_street.jpg"))
    res = legacy.analyze_evidence(ev.evidence_id)
    assert res["evidence"]["analysis_method"] == "FILENAME_KEYWORD_MOCK"
    assert legacy.evidence[ev.evidence_id].analysis_method == "FILENAME_KEYWORD_MOCK"


def test_legacy_upload_is_not_written_to_canonical_store():
    before = evidence_repository.count()
    legacy.add_evidence(Evidence(incident_id="INC-Y", evidence_type="PHOTO",
                                 file_name="block.jpg", file_path="/fake/storage/block.jpg"))
    assert evidence_repository.count() == before
