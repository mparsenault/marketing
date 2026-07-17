import approvals


def test_target_record_id_present():
    assert approvals.target_record_id({"record": "recABC"}) == "recABC"


def test_target_record_id_absent_returns_none():
    assert approvals.target_record_id({}) is None


def test_target_record_id_blank_returns_none():
    assert approvals.target_record_id({"record": "   "}) is None


def test_target_record_id_is_trimmed():
    assert approvals.target_record_id({"record": "  recX "}) == "recX"


def test_build_pending_payload():
    assert approvals.build_pending_payload() == {
        "StatutPublication": "En attente d'approbation"}


def test_build_approval_payload():
    assert approvals.build_approval_payload("a@elem.global", "2026-07-17") == {
        "StatutPublication": "Approuvé",
        "ApprouvéPar": "a@elem.global",
        "DateApprobation": "2026-07-17",
    }


def test_build_rejection_payload_sets_a_rediger():
    assert approvals.build_rejection_payload("trop court") == {
        "StatutPublication": "À rédiger",
        "RaisonRejet": "trop court",
    }
