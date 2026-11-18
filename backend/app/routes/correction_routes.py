"""Users propose corrections to the reader's signs; reviewers decide which become training labels.

A correction never changes a saved analysis or the deployed model. Reviewers are the
usernames listed in SIGN_REVIEWERS (comma-separated).
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from mysql.connector import Error as DatabaseError

from backend.app.auth import AuthenticatedWrite, CurrentUser, is_reviewer
from backend.app.data_controller.correction_data_controller import (CorrectionDataController, OwnCorrection,
                                                                    ReviewConflict, catalogue, catalogue_sign,
                                                                    sign_key)
from backend.app.model.analysis import ApiError
from backend.app.model.correction import (CatalogueSign, CorrectionCreate, CorrectionExportTablet, CorrectionReview,
                                          ReviewStatus, SignCorrection)
from backend.app.model.user import UserPublic

router = APIRouter(tags=["corrections"])
Identifier = Annotated[int, Path(gt=0, le=2**64 - 1)]


def get_correction_data_controller() -> CorrectionDataController:
    return CorrectionDataController()


CorrectionController = Annotated[CorrectionDataController, Depends(get_correction_data_controller)]


def require_reviewer(user: CurrentUser) -> UserPublic:
    if not is_reviewer(user):
        raise HTTPException(403, "Only reviewers can do this.")
    return user


def require_reviewer_write(user: AuthenticatedWrite) -> UserPublic:
    return require_reviewer(user)


Reviewer = Annotated[UserPublic, Depends(require_reviewer)]
ReviewerWrite = Annotated[UserPublic, Depends(require_reviewer_write)]


@router.get("/corrections/catalogue", response_model=list[CatalogueSign])
def sign_catalogue() -> list[CatalogueSign]:
    return catalogue()


@router.post("/analysis/{analysis_id}/corrections", response_model=SignCorrection, status_code=status.HTTP_201_CREATED,
             responses={code: {"model": ApiError} for code in (401, 403, 404, 503)})
def submit(analysis_id: Identifier, request: CorrectionCreate, user: AuthenticatedWrite,
           controller: CorrectionController) -> SignCorrection:
    proposed = None
    if request.proposed_sign is not None:
        proposed = catalogue_sign(request.proposed_sign)
        if proposed is None:
            raise HTTPException(422, "This sign is not in the sign catalogue.")
    try:
        saved = controller.detected_sign(user.id, analysis_id, request.sign_id)
        if saved is None:
            raise HTTPException(404, "Sign not found in this analysis.")
        # The generic fallback model finds objects, not Linear A signs: nothing to train the reader on.
        if not saved.trained:
            raise HTTPException(422, "Only signs read by the Linear A sign reader can be corrected.")
        if proposed is not None and sign_key(proposed) == sign_key(saved.sign.get("sign") or ""):
            raise HTTPException(422, "This is already the model's reading.")
        return controller.create(user.id, analysis_id, request, saved, proposed)
    except DatabaseError as error:
        raise HTTPException(503, "Corrections cannot be saved right now. Please try again.") from error


@router.get("/analysis/{analysis_id}/corrections", response_model=list[SignCorrection],
            responses={code: {"model": ApiError} for code in (401, 503)})
def my_corrections(analysis_id: Identifier, user: CurrentUser, controller: CorrectionController) -> list[SignCorrection]:
    try:
        return controller.list_for_analysis(user.id, analysis_id)
    except DatabaseError as error:
        raise HTTPException(503, "Corrections are unavailable.") from error


@router.get("/corrections", response_model=list[SignCorrection],
            responses={code: {"model": ApiError} for code in (401, 403, 503)})
def review_queue(_reviewer: Reviewer, controller: CorrectionController,
                 review_status: Annotated[ReviewStatus, Query(alias="status")] = "pending",
                 limit: Annotated[int, Query(ge=1, le=200)] = 50) -> list[SignCorrection]:
    try:
        return controller.list_by_status(review_status, limit)
    except DatabaseError as error:
        raise HTTPException(503, "Corrections are unavailable.") from error


@router.post("/corrections/{correction_id}/review", response_model=SignCorrection,
             responses={code: {"model": ApiError} for code in (401, 403, 404, 409, 503)})
def review(correction_id: Identifier, decision: CorrectionReview, reviewer: ReviewerWrite,
           controller: CorrectionController) -> SignCorrection:
    try:
        reviewed = controller.review(correction_id, reviewer.id, decision.decision)
    except OwnCorrection as error:
        raise HTTPException(403, "You cannot review your own correction.") from error
    except ReviewConflict as error:
        raise HTTPException(409, "This correction was already reviewed.") from error
    except DatabaseError as error:
        raise HTTPException(503, "Corrections are unavailable.") from error
    if reviewed is None:
        raise HTTPException(404, "Correction not found.")
    return reviewed


@router.get("/corrections/export", response_model=list[CorrectionExportTablet],
            responses={code: {"model": ApiError} for code in (401, 403, 503)})
def export(_reviewer: Reviewer, controller: CorrectionController) -> list[CorrectionExportTablet]:
    try:
        return controller.export_approved()
    except DatabaseError as error:
        raise HTTPException(503, "Corrections are unavailable.") from error
