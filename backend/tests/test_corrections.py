"""Sign corrections (#52): validation, ownership, review rights and CSRF, without a running database."""
import json
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from mysql.connector import Error as DatabaseError

from backend.app import tablet_demo
from backend.app.auth import COOKIE_NAME, csrf_token, token_hash
from backend.app.data_controller.correction_data_controller import (CorrectionDataController, OwnCorrection,
                                                                    ReviewConflict, SavedSign)
from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.main import app
from backend.app.model.correction import SignCorrection
from backend.app.model.user import UserPublic

SIGN = {"id": 3, "sign": "AB59", "label": "AB59 (ta)", "confidence": 41.5, "box": {"x": 0.1, "y": 0.2, "w": 0.05, "h": 0.06}}
READ = SavedSign(SIGN, "linear_a_signs.pt@abc", True, 1000, 800)


def saved(**changes):
    fields = dict(id=9, analysis_id=12, sign_id=3, created_at=datetime.now(timezone.utc), box=SIGN["box"],
                  original_sign="AB59", original_label="AB59 (ta)", original_confidence=41.5,
                  model_version="linear_a_signs.pt@abc", proposed_sign="AB81", uncertain=False, note=None,
                  status="pending")
    return SignCorrection(**{**fields, **changes})


def login(monkeypatch, username="owner"):
    token = "a" * 43
    monkeypatch.setattr(UserDataController, "get_session_user", lambda self, digest:
                        UserPublic(id=7, email=f"{username}@ase3.com", username=username)
                        if digest == token_hash(token) else None)
    client = TestClient(app)
    client.cookies.set(COOKIE_NAME, token)
    client.headers["X-CSRF-Token"] = csrf_token(token)
    return client


@pytest.fixture
def owner(monkeypatch):
    with login(monkeypatch) as client:
        yield client


@pytest.fixture
def reviewer(monkeypatch):
    monkeypatch.setenv("SIGN_REVIEWERS", "someone, Reviewer")
    with login(monkeypatch, "reviewer") as client:
        yield client


@pytest.fixture
def create(monkeypatch):
    return creating(monkeypatch, READ)


def creating(monkeypatch, read):
    monkeypatch.setattr(CorrectionDataController, "detected_sign",
                        lambda self, user_id, analysis_id, sign_id: read
                        if (user_id, analysis_id, sign_id) == (7, 12, 3) else None)
    create = MagicMock(side_effect=lambda user_id, analysis_id, request, read, proposed:
                       saved(proposed_sign=proposed, uncertain=request.uncertain, note=request.note))
    monkeypatch.setattr(CorrectionDataController, "create", lambda self, *args: create(*args))
    return create


def test_catalogue_lists_every_unicode_sign_with_its_glyph():
    with TestClient(app) as client:
        signs = {sign["sign"]: sign for sign in client.get("/corrections/catalogue").json()}
    assert signs["AB81"]["glyph"] == "\U00010642"
    # Spelled as in the training data, even without the classifier's own list.
    assert signs["AB01"]["glyph"] == "\U00010600" and "AB1" not in signs
    assert len(signs) >= 300


def test_submitting_needs_login_and_a_csrf_token(owner, create):
    with TestClient(app) as anonymous:
        assert anonymous.post("/analysis/12/corrections", json={"sign_id": 3, "uncertain": True}).status_code == 401
    assert owner.post("/analysis/12/corrections", json={"sign_id": 3, "uncertain": True},
                      headers={"X-CSRF-Token": csrf_token("another-session")}).status_code == 403
    create.assert_not_called()


def test_replacement_keeps_the_original_prediction_and_region(owner, create):
    response = owner.post("/analysis/12/corrections", json={"sign_id": 3, "proposed_sign": "ab081"})

    assert response.status_code == 201
    user_id, analysis_id, request, read, proposed = create.call_args.args
    assert (user_id, analysis_id, read, proposed) == (7, 12, READ, "AB81")
    body = response.json()
    assert body["status"] == "pending"
    assert (body["original_sign"], body["proposed_sign"], body["box"]) == ("AB59", "AB81", SIGN["box"])


def test_uncertain_sign_is_flagged_without_a_label(owner, create):
    response = owner.post("/analysis/12/corrections", json={"sign_id": 3, "uncertain": True, "note": "worn"})

    assert response.status_code == 201
    assert (response.json()["proposed_sign"], response.json()["uncertain"], response.json()["note"]) == (None, True, "worn")


@pytest.mark.parametrize("payload", [
    {"sign_id": 3},
    {"sign_id": 3, "proposed_sign": "AB81", "uncertain": True},
    {"sign_id": 3, "proposed_sign": "NOT-A-SIGN"},
    {"sign_id": 3, "proposed_sign": "AB59"},
    {"sign_id": 0, "uncertain": True},
    {"sign_id": 3, "uncertain": True, "note": "x" * 501},
])
def test_invalid_corrections_are_rejected(owner, create, payload):
    assert owner.post("/analysis/12/corrections", json=payload).status_code == 422
    create.assert_not_called()


def test_the_models_own_reading_is_rejected_however_it_is_spelled(owner, monkeypatch):
    create = creating(monkeypatch, READ._replace(sign={**SIGN, "sign": "AB01"}))
    assert owner.post("/analysis/12/corrections", json={"sign_id": 3, "proposed_sign": "ab1"}).status_code == 422
    create.assert_not_called()


def test_signs_from_the_generic_fallback_model_cannot_be_corrected(owner, monkeypatch):
    create = creating(monkeypatch, READ._replace(trained=False, sign={**SIGN, "sign": None, "label": "person"}))
    response = owner.post("/analysis/12/corrections", json={"sign_id": 3, "proposed_sign": "AB81"})
    assert response.status_code == 422
    assert response.json()["detail"] == "Only signs read by the Linear A sign reader can be corrected."
    create.assert_not_called()


@pytest.mark.parametrize("path,sign_id", [("/analysis/13/corrections", 3), ("/analysis/12/corrections", 4)])
def test_other_users_analyses_and_unknown_signs_are_not_found(owner, create, path, sign_id):
    assert owner.post(path, json={"sign_id": sign_id, "uncertain": True}).status_code == 404
    create.assert_not_called()


def test_database_failure_is_a_clear_503(owner, monkeypatch):
    monkeypatch.setattr(CorrectionDataController, "detected_sign", MagicMock(side_effect=DatabaseError("down")))
    response = owner.post("/analysis/12/corrections", json={"sign_id": 3, "uncertain": True})
    assert response.status_code == 503
    assert response.json()["detail"] == "Corrections cannot be saved right now. Please try again."


def test_review_is_for_listed_reviewers_only(owner, monkeypatch):
    monkeypatch.setenv("SIGN_REVIEWERS", "reviewer")
    review = MagicMock()
    monkeypatch.setattr(CorrectionDataController, "review", review)
    assert owner.get("/corrections").status_code == 403
    assert owner.get("/corrections/export").status_code == 403
    assert owner.post("/corrections/9/review", json={"decision": "approved"}).status_code == 403
    review.assert_not_called()


def test_reviewer_sees_the_queue_and_approves(reviewer, monkeypatch):
    monkeypatch.setattr(CorrectionDataController, "list_by_status", lambda self, status, limit: [saved()] if status == "pending" else [])
    review = MagicMock(return_value=saved(status="approved"))
    monkeypatch.setattr(CorrectionDataController, "review", lambda self, *args: review(*args))

    assert [item["id"] for item in reviewer.get("/corrections").json()] == [9]
    assert reviewer.get("/corrections?status=approved").json() == []
    response = reviewer.post("/corrections/9/review", json={"decision": "approved"})
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    review.assert_called_once_with(9, 7, "approved")


def test_review_needs_csrf_and_cannot_change_a_decision(reviewer, monkeypatch):
    monkeypatch.setattr(CorrectionDataController, "review", MagicMock(side_effect=ReviewConflict()))
    assert reviewer.post("/corrections/9/review", json={"decision": "approved"},
                         headers={"X-CSRF-Token": ""}).status_code == 403
    assert reviewer.post("/corrections/9/review", json={"decision": "rejected"}).status_code == 409
    monkeypatch.setattr(CorrectionDataController, "review", MagicMock(side_effect=OwnCorrection()))
    assert reviewer.post("/corrections/9/review", json={"decision": "approved"}).json() == {
        "detail": "You cannot review your own correction."}
    monkeypatch.setattr(CorrectionDataController, "review", lambda self, *args: None)
    assert reviewer.post("/corrections/9/review", json={"decision": "rejected"}).status_code == 404
    assert reviewer.post("/corrections/9/review", json={"decision": "maybe"}).status_code == 422


class FakeCursor:
    def __init__(self, row, rowcount=1):
        self.row, self.rowcount, self.queries = row, rowcount, []

    def execute(self, query, params):
        self.queries.append(query)
        self.params = params

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.row

    def close(self):
        pass


def fake_connection(monkeypatch, row, rowcount=1):
    cursor = FakeCursor(row, rowcount)

    @contextmanager
    def connection(self):
        yield MagicMock(cursor=lambda **_: cursor)

    monkeypatch.setattr(CorrectionDataController, "connection", connection)
    return cursor


def test_detected_sign_reads_the_saved_snapshot_of_the_users_own_analysis(monkeypatch):
    snapshot = {"model_version": "v2", "trained": True, "width": 1000, "height": 800, "signs": [{**SIGN, "id": 2}, SIGN]}
    cursor = fake_connection(monkeypatch, (json.dumps(snapshot),))

    assert CorrectionDataController().detected_sign(7, 12, 3) == SavedSign(SIGN, "v2", True, 1000, 800)
    assert cursor.params == (7, 12)
    assert CorrectionDataController().detected_sign(7, 12, 99) is None


def test_history_saved_before_model_versions_is_marked_unknown(monkeypatch):
    fake_connection(monkeypatch, (json.dumps({"trained": True, "width": 10, "height": 10, "signs": [SIGN]}),))
    assert CorrectionDataController().detected_sign(7, 12, 3).model_version == "unknown"


ROW = dict(id=9, analysis_id=12, sign_id=3, created_at=datetime(2026, 11, 18), box_x=0.1, box_y=0.2, box_w=0.05,
           box_h=0.06, original_sign="AB59", original_label="AB59 (ta)", original_confidence=41.5,
           model_version="v2", proposed_sign="AB81", uncertain=0, note=None, status="pending", author_id=7)


@pytest.mark.parametrize("author,expected", [(7, OwnCorrection), (8, ReviewConflict)])
def test_a_review_that_changes_nothing_says_why(monkeypatch, author, expected):
    cursor = fake_connection(monkeypatch, {**ROW, "author_id": author}, rowcount=0)
    with pytest.raises(expected):
        CorrectionDataController().review(9, 7, "approved")
    assert "author_id <> %s" in cursor.queries[0]


def test_export_gives_pixel_boxes_like_the_training_annotations(monkeypatch):
    rows = [{**ROW, "filename": "tablet.png", "image_width": 1000, "image_height": 800},
            {**ROW, "id": 10, "filename": "tablet.png", "image_width": 1000, "image_height": 800, "proposed_sign": "AB02"}]
    fake_connection(monkeypatch, rows)
    [tablet] = CorrectionDataController().export_approved()
    assert (tablet.analysis_id, tablet.filename, tablet.width, tablet.height) == (12, "tablet.png", 1000, 800)
    assert [(sign.sign, sign.xyxy, sign.source) for sign in tablet.signs] == [
        ("AB81", [100, 160, 150, 208], "correction"), ("AB02", [100, 160, 150, 208], "correction")]


def test_model_version_names_each_weight_file_and_its_hash():
    assert re.fullmatch(r"[\w.-]+\.pt@[0-9a-f]{12}(\+[\w.-]+\.pt@[0-9a-f]{12})?", tablet_demo.model_version())
