"""Edition releases, votes and the admin override (scholars' workbench, story E).

* An edition's owner (or someone it is shared with at manage) releases it: a snapshot that never
  changes. Releasing opens the edition to everyone for viewing, since releases are for voting.
* Each logged-in account backs at most one release per tablet, and may change or withdraw it.
  Accounts younger than a day may not vote, nor those an admin has removed voting rights from;
  the votes of the latter are kept but not counted while their rights are removed.
* The accepted edition of a tablet is the admin override's release if there is one, otherwise the
  most backed release, the earlier one on a tie. An override needs a reason, which everyone sees.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from mysql.connector import Error as DatabaseError

from backend.app.auth import Admin, AdminWrite, AuthenticatedWrite, CurrentUser
from backend.app.data_controller.analysis_data_controller import describe_sign, read_signs
from backend.app.data_controller.edition_data_controller import EditionDataController
from backend.app.model.analysis import ApiError, DetectedSign
from backend.app.model.box_set import Reading
from backend.app.model.edition import (
    ClearOverride,
    EditionVotes,
    Override,
    OverrideRequest,
    Release,
    ReleaseCreate,
    ReleaseSummary,
    TabletEditions,
    VoteRequest,
    Voting,
    VotingRights,
    VotingRightsChange,
)
from backend.app.notifications import notify, quote, tablet_name
from backend.app.routes.box_set_routes import Controller, _catalogue, access, build, manual_lines
from backend.app.routes.version_routes import _optional_user
from backend.app.sharing import level_of

router = APIRouter(tags=["editions"])
Identifier = Annotated[int, Path(gt=0, le=2**64 - 1)]
Slug = Annotated[str, Path(pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$", max_length=64)]
ERRORS = {code: {"model": ApiError} for code in (401, 403, 404, 409, 422, 503)}
UNAVAILABLE = "Editions are unavailable. Please try again."


def get_edition_data_controller() -> EditionDataController:
    return EditionDataController()


Editions = Annotated[EditionDataController, Depends(get_edition_data_controller)]


def _release(row: dict, reading: bool = False) -> Release:
    release = Release(
        id=row["id"],
        edition_id=row["set_id"],
        number=row["number"],
        tablet=row["tablet_slug"],
        title=row["title"],
        notes=row["notes"],
        owner=row["owner"],
        version=row["version"],
        width=row["width"],
        height=row["height"],
        image_url=f"/tablets/{row['tablet_slug']}/image",
        created_at=row["created_at"],
        boxes=row["boxes"],
        merged_from=row.get("merged_from") or [],
        contributors=row.get("contributors") or [],
    )
    if reading:
        catalogue = _catalogue()
        signs = [
            DetectedSign(
                id=box.id,
                **describe_sign(box.sign, catalogue),
                confidence=100.0,
                detection_confidence=100.0,
                box=box.box,
                candidates=[],
            )
            for box in release.boxes
        ]
        marks = {box.id: box.marks.model_dump() for box in release.boxes}
        release.reading = Reading(
            **read_signs(signs, grouped=manual_lines(signs, marks), marks=marks)
        )
    return release


def _summary(row: dict) -> ReleaseSummary:
    return ReleaseSummary(
        id=row["id"],
        edition_id=row["set_id"],
        number=row["number"],
        title=row["title"],
        notes=row["notes"],
        owner=row["owner"],
        box_count=len(row["boxes"]),
        created_at=row["created_at"],
    )


@router.post(
    "/box-sets/{set_id}/releases",
    response_model=Release,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def release_edition(
    set_id: Identifier,
    request: ReleaseCreate,
    user: AuthenticatedWrite,
    controller: Controller,
    editions: Editions,
) -> Release:
    """Release your edition as it is now: a numbered snapshot others can vote on and cite. Needs the
    owner or manage level; only editions (merged copies) can be released."""
    record = access(controller, set_id, user, "manage")
    if record.get("kind") != "edition" or not record.get("tablet_slug"):
        raise HTTPException(
            422, "Only an edition of a tablet can be released: merge versions into one first."
        )
    copy = build(record)
    if not copy.boxes:
        raise HTTPException(422, "An edition with no boxes cannot be released.")
    snapshot = {
        "tablet": record["tablet_slug"],
        "title": copy.title,
        "notes": (request.notes or "").strip() or None,
        "version": copy.version,
        "width": copy.width,
        "height": copy.height,
        "boxes": [
            {
                "id": box.id,
                "box": box.box.model_dump(),
                "sign": box.sign,
                "source": box.source.model_dump() if box.source else None,
                "marks": box.marks.model_dump(),
            }
            for box in copy.boxes
        ],
        "merged_from": [item.model_dump() for item in copy.merged_from],
        "contributors": sorted(set(copy.contributors) | {copy.owner}),
    }
    try:
        release_id = editions.create_release(set_id, user.id, snapshot)
        return _release(editions.release(release_id))
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error


@router.get("/box-sets/{set_id}/releases", response_model=list[ReleaseSummary], responses=ERRORS)
def edition_releases(
    set_id: Identifier, user: CurrentUser, controller: Controller, editions: Editions
) -> list[ReleaseSummary]:
    """The releases of an edition you can see, newest first."""
    access(controller, set_id, user)
    try:
        return [_summary(row) for row in editions.releases_of(set_id)]
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error


@router.get("/editions/{release_id}", response_model=Release, responses=ERRORS)
def get_release(
    release_id: Identifier, request: Request, editions: Editions, controller: Controller
) -> Release:
    """A release, with its reading: the permalink to cite. Anyone may see the releases of an edition
    open to everyone; otherwise only those who can open the edition."""
    try:
        row = editions.release(release_id)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    if row is None:
        raise HTTPException(404, "Release not found.")
    if row["everyone"] == "none":
        user = _optional_user(request)
        try:
            share = controller.share_of(row["set_id"], user.id) if user else None
        except DatabaseError as error:
            raise HTTPException(503, UNAVAILABLE) from error
        if user is None or level_of(row["owner_id"], "none", user.id, share) is None:
            raise HTTPException(404, "Release not found.")
    return _release(row, reading=True)


def _voting(editions: EditionDataController, user) -> Voting:
    if user is None:
        return Voting(allowed=False, reason="Log in to vote.")
    voter = editions.voter(user.id)
    if voter is None or not voter["can_vote"]:
        rights = editions.voting_rights(user.id) or {}
        why = f": {rights['reason']}" if rights.get("reason") else "."
        return Voting(allowed=False, reason=f"Your voting rights were removed by an admin{why}")
    if not voter["old_enough"]:
        return Voting(allowed=False, reason="New accounts can vote one day after they are made.")
    return Voting(allowed=True)


def _editions(slug: str, editions: EditionDataController, user) -> TabletEditions:
    rows = editions.tablet_releases(slug)
    counts = editions.vote_counts(slug)
    override = editions.current_override(slug)
    visible = {row["id"] for row in rows}
    if override and override["release_id"] not in visible:
        override = None  # its edition was made private since
    items = [
        EditionVotes(
            **_summary(row).model_dump(),
            votes=counts.get(row["id"], (0, 0))[0],
            reviewer_votes=counts.get(row["id"], (0, 0))[1],
        )
        for row in rows
    ]
    accepted = override["release_id"] if override else None
    if accepted is None:
        backed = [item for item in items if item.votes]
        if backed:  # most votes; rows are oldest first, so max() keeps the earlier one on a tie
            accepted = max(backed, key=lambda item: item.votes).id
    for item in items:
        item.accepted = item.id == accepted
    items.sort(key=lambda item: (-item.accepted, -item.votes, item.created_at, item.id))
    return TabletEditions(
        slug=slug,
        items=items,
        accepted_release_id=accepted,
        override=Override(**override) if override else None,
        my_vote=editions.my_vote(slug, user.id) if user else None,
        voting=_voting(editions, user),
    )


def accepted_copies(editions: EditionDataController) -> list[dict]:
    """Each tablet's accepted release, shaped like the training export's copies (one clean version
    per tablet instead of every copy): for GET /admin/export/corrections?accepted_only=true."""
    out = []
    for slug in editions.released_tablets():
        accepted = _editions(slug, editions, None).accepted_release_id
        row = editions.release(accepted) if accepted else None
        if row is None:
            continue
        boxes = [
            {
                "id": box["id"],
                **box["box"],
                "sign": box["sign"],
                "origin": (box.get("source") or {}).get("kind") or "user",
                **{f"original_{name}": box["box"][name] for name in ("x", "y", "w", "h")},
                "model_sign": box["sign"],
            }
            for box in row["boxes"]
        ]
        out.append(
            {
                "id": row["id"],
                "image_stem": f"edition-{row['id']}",
                "owner_id": row["owner_id"],
                "owner_trusted": True,
                "analysis_id": None,
                "tablet_slug": slug,
                "start": "edition",
                "version": row["number"],
                "width": row["width"],
                "height": row["height"],
                "filename": None,
                "storage_key": None,
                "format": None,
                "boxes": boxes,
            }
        )
    return out


@router.get("/tablets/{slug}/editions", response_model=TabletEditions, responses=ERRORS)
def tablet_editions(slug: Slug, request: Request, editions: Editions) -> TabletEditions:
    """The released editions of a tablet open to everyone, with their votes, the accepted one, any
    admin override and its reason, and whether you may vote."""
    try:
        return _editions(slug, editions, _optional_user(request))
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error


@router.put("/tablets/{slug}/vote", response_model=TabletEditions, responses=ERRORS)
def vote(
    slug: Slug, request: VoteRequest, user: AuthenticatedWrite, editions: Editions
) -> TabletEditions:
    """Back a release of this tablet (replacing your earlier choice for it)."""
    try:
        voting = _voting(editions, user)
        if not voting.allowed:
            raise HTTPException(403, voting.reason)
        releases = {row["id"]: row for row in editions.tablet_releases(slug)}
        if request.release_id not in releases:
            raise HTTPException(404, "No such release of this tablet is open for voting.")
        editions.vote(slug, user.id, request.release_id)
        backed = releases[request.release_id]
        notify(
            [backed["owner_id"]],
            "vote",
            user.id,
            f"{user.username} backed your edition of {tablet_name(slug)} (release {backed['number']}).",
            f"/editions/{backed['id']}",
            slug,
        )
        return _editions(slug, editions, user)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error


@router.delete("/tablets/{slug}/vote", response_model=TabletEditions, responses=ERRORS)
def withdraw_vote(slug: Slug, user: AuthenticatedWrite, editions: Editions) -> TabletEditions:
    try:
        editions.unvote(slug, user.id)
        return _editions(slug, editions, user)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error


@router.put("/tablets/{slug}/edition-override", response_model=TabletEditions, responses=ERRORS)
def override(
    slug: Slug, request: OverrideRequest, admin: AdminWrite, editions: Editions
) -> TabletEditions:
    """Choose the tablet's accepted edition over the vote (admins). The reason (at least 15
    characters) is shown to everyone with the admin's name; the votes stay visible."""
    try:
        releases = {row["id"]: row for row in editions.tablet_releases(slug)}
        if request.release_id not in releases:
            raise HTTPException(404, "No such release of this tablet is open to everyone.")
        editions.set_override(slug, request.release_id, admin.id, request.comment)
        chosen = releases[request.release_id]
        notify(
            {row["owner_id"] for row in releases.values()},
            "override",
            admin.id,
            f"An admin ({admin.username}) chose {chosen['owner']}'s edition (release {chosen['number']}) as the "
            f"accepted edition of {tablet_name(slug)}: {quote(request.comment, 160)}",
            f"/tablets/{slug}",
            slug,
        )
        return _editions(slug, editions, admin)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error


@router.post(
    "/tablets/{slug}/edition-override/clear", response_model=TabletEditions, responses=ERRORS
)
def clear_override(
    slug: Slug, request: ClearOverride, admin: AdminWrite, editions: Editions
) -> TabletEditions:
    """Return the choice to the vote (admins), with a reason kept on record."""
    try:
        if not editions.clear_override(slug, admin.id, request.comment):
            raise HTTPException(404, "This tablet has no override.")
        notify(
            {row["owner_id"] for row in editions.tablet_releases(slug)},
            "override",
            admin.id,
            f"An admin ({admin.username}) returned the accepted edition of {tablet_name(slug)} to the vote: "
            f"{quote(request.comment, 160)}",
            f"/tablets/{slug}",
            slug,
        )
        return _editions(slug, editions, admin)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error


@router.get("/admin/users/{user_id}/voting", response_model=VotingRights, responses=ERRORS)
def voting_rights(user_id: Identifier, admin: Admin, editions: Editions) -> VotingRights:
    try:
        rights = editions.voting_rights(user_id)
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    if rights is None:
        raise HTTPException(404, "User not found.")
    return VotingRights(**rights)


@router.put("/admin/users/{user_id}/voting", response_model=VotingRights, responses=ERRORS)
def set_voting_rights(
    user_id: Identifier, request: VotingRightsChange, admin: AdminWrite, editions: Editions
) -> VotingRights:
    """Remove or restore an account's voting rights (admins), with a reason of at least 15
    characters that the account is shown. Its votes are kept but not counted while removed.
    Admins cannot change their own."""
    if user_id == admin.id:
        raise HTTPException(422, "You cannot change your own voting rights.")
    try:
        if not editions.set_voting_rights(user_id, admin.id, request.can_vote, request.reason):
            raise HTTPException(404, "User not found.")
        notify(
            [user_id],
            "voting_rights",
            admin.id,
            f"An admin ({admin.username}) {'restored' if request.can_vote else 'removed'} your voting rights "
            f"on editions: {quote(request.reason, 160)}",
            None,
        )
        return VotingRights(**editions.voting_rights(user_id))
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
