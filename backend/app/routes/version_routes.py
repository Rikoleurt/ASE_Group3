"""The versions of a corpus tablet, and comparing them (scholars' workbench, story C).

A tablet's versions are the scholars' published boxes, the model's, and every corrected copy
the user can open (theirs, and others' shared with them or with everyone; see sharing.py).
"""

import re
from itertools import combinations
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response, status
from mysql.connector import Error as DatabaseError

from backend.app import box_matching, corpus, glyph_index
from backend.app.auth import COOKIE_NAME, AuthenticatedWrite, CurrentUser, current_user
from backend.app.data_controller.analysis_data_controller import describe_sign
from backend.app.model.analysis import ApiError
from backend.app.model.user import UserPublic
from backend.app.model.versions import (
    Agreement,
    CompareCluster,
    MergeRequest,
    TabletComparison,
    TabletVersion,
    TabletVersions,
    VersionBox,
)
from backend.app.model.box_set import BoxSet
from backend.app.routes.box_set_routes import UNAVAILABLE, Controller, _catalogue, _current, access
from backend.app.sharing import level_of

router = APIRouter(tags=["tablet versions"])
Slug = Annotated[str, Path(pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$", max_length=64)]
ERRORS = {code: {"model": ApiError} for code in (401, 404, 422, 503)}
MAX_COMPARE = 6
VERSION_KEY = r"^(scholar|model|copy:[1-9][0-9]{0,19})$"


def _tablet(slug: str) -> tuple[glyph_index.GlyphIndex, str]:
    try:
        index = glyph_index.get_index()
    except glyph_index.CorpusMissing as error:
        raise HTTPException(503, str(error)) from error
    if slug not in index.slugs:
        raise HTTPException(404, "Tablet not found.")
    return index, index.slugs[slug]


def _optional_user(request: Request) -> UserPublic | None:
    try:
        return current_user(Response(), request.cookies.get(COOKIE_NAME))
    except HTTPException:
        return None


def _copy_version(row: dict, user_id: int) -> TabletVersion:
    level = level_of(row["owner_id"], row.get("everyone") or "none", user_id, row.get("share"))
    return TabletVersion(
        key=f"copy:{row['id']}",
        kind="edition" if row.get("kind") == "edition" else "copy",
        title=row.get("title"),
        owner=row["owner"],
        mine=row["owner_id"] == user_id,
        permission=level,
        box_count=row.get("box_count"),
        version=row.get("version"),
        updated_at=row.get("updated_at"),
    )


@router.get("/tablets/{slug}/versions", response_model=TabletVersions, responses=ERRORS)
def tablet_versions(slug: Slug, request: Request, controller: Controller) -> TabletVersions:
    """The versions of a tablet you can see: the scholars' boxes, the model's (with a login), and
    the corrected copies you can open, your own first. Logged out, only the first two."""
    index, tablet = _tablet(slug)
    items = [
        TabletVersion(
            key="scholar", kind="scholar", box_count=len(corpus.scholar_signs(index, slug))
        ),
        TabletVersion(key="model", kind="model", needs_login=True),
    ]
    user = _optional_user(request)
    if user is not None:
        try:
            rows = controller.versions_for_tablet(user.id, slug)
        except DatabaseError as error:
            raise HTTPException(503, UNAVAILABLE) from error
        items.extend(_copy_version(row, user.id) for row in rows)
    return TabletVersions(slug=slug, tablet=tablet, items=items)


def _boxes(signs, origin: str) -> list[dict]:
    return [
        {"id": sign.id, "box": sign.box.model_dump(), "sign": sign.sign, "origin": origin}
        for sign in signs
    ]


def _version(
    key: str, slug: str, index, user: UserPublic, controller
) -> tuple[TabletVersion, list[dict], int | None]:
    """A version's description, its boxes (each with its origin) and, for a copy, its owner's id;
    404 for a copy you cannot see or of another tablet."""
    if key == "scholar":
        boxes = _boxes(corpus.scholar_signs(index, slug), "scholar")
        return TabletVersion(key=key, kind="scholar", box_count=len(boxes)), boxes, None
    if key == "model":
        path = glyph_index.tracing_path(slug)
        if path is None:
            raise HTTPException(
                404, f"This tablet's drawing is not on this server. {corpus.DOWNLOAD_HINT}"
            )
        try:
            boxes = _boxes(corpus.model_signs(slug, path), "model")
        except (corpus.ReaderMissing, corpus.ReaderBusy) as error:
            raise HTTPException(503, str(error)) from error
        except (FileNotFoundError, RuntimeError) as error:
            raise HTTPException(503, "The sign reader is unavailable.") from error
        return TabletVersion(key=key, kind="model", box_count=len(boxes)), boxes, None
    record = access(controller, int(key.split(":")[1]), user)
    if record.get("tablet_slug") != slug:
        raise HTTPException(404, "Corrected copy not found.")
    boxes = [
        {
            "id": row["id"],
            "box": {name: row[name] for name in ("x", "y", "w", "h")},
            "sign": row["sign"],
            "origin": row["origin"],
        }
        for row in record["boxes"]
        if not row["deleted"]
    ]
    version = TabletVersion(
        key=key,
        kind="edition" if record.get("kind") == "edition" else "copy",
        title=record.get("title"),
        owner=record["owner"],
        mine=record["owner_id"] == user.id,
        permission=record["permission"],
        box_count=len(boxes),
        version=record["version"],
        updated_at=record["updated_at"],
    )
    return version, boxes, record["owner_id"]


@router.get("/tablets/{slug}/compare", response_model=TabletComparison, responses=ERRORS)
def compare_versions(
    slug: Slug,
    user: CurrentUser,
    controller: Controller,
    v: Annotated[
        list[str],
        Query(
            min_length=2, max_length=MAX_COMPARE, description="Version keys from /versions, 2 to 6"
        ),
    ],
) -> TabletComparison:
    """Two to six versions of a tablet side by side: their boxes matched by overlap into places,
    each place marked as agreeing, differing in sign, or missing from some versions, in reading
    order; and how often each pair of versions agrees. Needs a login (the model's boxes run the reader)."""
    keys = list(dict.fromkeys(v))
    if len(keys) < 2 or not all(re.fullmatch(VERSION_KEY, key) for key in keys):
        raise HTTPException(422, "Give 2 to 6 different versions: scholar, model or copy:<id>.")
    index, tablet = _tablet(slug)
    path = glyph_index.tracing_path(slug)
    if path is None:
        raise HTTPException(
            404, f"This tablet's drawing is not on this server. {corpus.DOWNLOAD_HINT}"
        )
    found = [_version(key, slug, index, user, controller) for key in keys]
    versions = {version.key: boxes for version, boxes, _owner in found}
    clusters = box_matching.cluster(versions)
    catalogue = _catalogue()

    def labelled(box: dict) -> VersionBox:
        label = describe_sign(box["sign"], catalogue)["label"] if box["sign"] else None
        return VersionBox(id=box["id"], box=box["box"], sign=box["sign"], label=label)

    width, height = corpus.image_size(path)
    return TabletComparison(
        slug=slug,
        tablet=tablet,
        width=width,
        height=height,
        image_url=f"/tablets/{slug}/image",
        versions=[version for version, _boxes, _owner in found],
        clusters=[
            CompareCluster(
                box=place.box,
                members={key: labelled(box) for key, box in place.members.items()},
                status=place.status(keys),
                moved=place.moved,
            )
            for place in clusters
        ],
        agreement=[
            Agreement(a=a, b=b, same=same, total=total)
            for a, b in combinations(keys, 2)
            for same, total in [box_matching.agreement(clusters, a, b)]
        ],
    )


@router.post(
    "/box-sets/merge",
    response_model=BoxSet,
    status_code=status.HTTP_201_CREATED,
    responses={**ERRORS, 403: {"model": ApiError}, 409: {"model": ApiError}},
)
def merge_versions(
    request: MergeRequest, user: AuthenticatedWrite, controller: Controller
) -> BoxSet:
    """Merge versions of a tablet into a new edition of your own (workbench, story D).

    The places are worked out again here, from the versions as they are now, exactly as
    GET /compare does for the same sources in the same order; `picks` chooses, place by place,
    whose box to keep (or none). A copy that changed since the merge page loaded it (its
    `version` differs) is refused with 409, as is a different number of places. Each box keeps
    where it came from and its author, who is credited on the edition.
    """
    keys = [source.key for source in request.sources]
    if len(set(keys)) != len(keys):
        raise HTTPException(422, "Give each version once.")
    index, _tablet_name = _tablet(request.tablet)
    path = glyph_index.tracing_path(request.tablet)
    if path is None:
        raise HTTPException(
            404, f"This tablet's drawing is not on this server. {corpus.DOWNLOAD_HINT}"
        )
    found = [_version(key, request.tablet, index, user, controller) for key in keys]
    for source, (version, _boxes_, _owner) in zip(request.sources, found):
        if source.version is not None and version.version != source.version:
            name = f"{version.owner}'s {version.kind}" if version.owner else source.key
            raise HTTPException(
                409, f"{name} changed since you opened the merge. Reload to see the changes."
            )
    places = box_matching.cluster({version.key: boxes for version, boxes, _owner in found})
    if len(request.picks) != len(places):
        raise HTTPException(
            409, "The versions changed since you opened the merge. Reload to see the changes."
        )
    described = {version.key: (version, owner) for version, _boxes_, owner in found}
    boxes = []
    for place, pick in zip(places, request.picks):
        if pick is None:
            continue
        if pick not in place.members:
            raise HTTPException(
                422, "Each place can only keep a box one of its versions has there."
            )
        chosen = place.members[pick]
        version, owner_id = described[pick]
        copied = pick.startswith("copy:")
        boxes.append(
            {
                "box": chosen["box"],
                "sign": chosen["sign"],
                "origin": chosen["origin"],
                "source_kind": "copy" if copied else pick,
                "source_set_id": int(pick[5:]) if copied else None,
                "source_box_id": chosen["id"],
                "source_version": version.version if copied else None,
                "source_author_id": owner_id if copied else None,
            }
        )
    if not boxes:
        raise HTTPException(422, "Keep at least one box.")
    merged_from = [
        {
            "key": version.key,
            "kind": version.kind,
            "title": version.title,
            "owner": version.owner,
            "version": version.version,
        }
        for version, _boxes_, _owner in found
    ]
    width, height = corpus.image_size(path)
    try:
        set_id = controller.create_edition(
            user.id, request.tablet, request.title, width, height, boxes, merged_from
        )
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
    return _current(controller, set_id)
