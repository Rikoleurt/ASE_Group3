"""Discussions that mention a corpus glyph, an edition release or a sign (scholars' workbench,
story L): listed beside the box, the edition and the sign, so their discussions are one click
away. A discussion is linked by mentioning the target in one of its comments."""

import re
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from mysql.connector import Error as DatabaseError
from pydantic import BaseModel

from backend.app.data_controller.data_controller import DataController
from backend.app.model.analysis import ApiError

router = APIRouter(prefix="/community", tags=["community"])
TARGET = re.compile(
    r"^(glyph:[A-Za-z0-9]+(?:-[A-Za-z0-9]+){0,6}:[0-9]{1,7}|edition:[1-9][0-9]{0,19}|sign:[A-Za-z0-9]{1,12})$"
)
MAX_LINKED = 20


class LinkDataController(DataController):
    def linked(self, key: str, limit: int) -> list[dict]:
        """Discussions with a comment that mentions `key` (the token's destination), newest first."""
        pattern = "%](" + key.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + ")%"
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    "SELECT d.id, d.title, u.username AS author, MAX(c.created_at) AS mentioned_at "
                    "FROM community_comment c JOIN community_discussion d ON d.id = c.discussion_id "
                    "JOIN `user` u ON u.id = d.author_id WHERE c.body LIKE %s "
                    "GROUP BY d.id, d.title, u.username ORDER BY mentioned_at DESC LIMIT %s",
                    (pattern, limit),
                )
                return cursor.fetchall()
            finally:
                cursor.close()


def get_link_data_controller() -> LinkDataController:
    return LinkDataController()


Links = Annotated[LinkDataController, Depends(get_link_data_controller)]


class LinkedDiscussion(BaseModel):
    id: int
    title: str
    author: str
    mentioned_at: datetime  # the latest comment there that mentions it


class LinkedDiscussions(BaseModel):
    target: str
    items: list[LinkedDiscussion]


@router.get(
    "/linked",
    response_model=LinkedDiscussions,
    responses={422: {"model": ApiError}, 503: {"model": ApiError}},
)
def linked_discussions(
    target: Annotated[str, Query(max_length=100)], links: Links
) -> LinkedDiscussions:
    """The discussions that mention `target`: glyph:<tablet>:<position>, edition:<release id> or
    sign:<sign ID>, as written in mentions."""
    if not TARGET.fullmatch(target):
        raise HTTPException(422, "Give glyph:<tablet>:<position>, edition:<id> or sign:<sign>.")
    try:
        rows = links.linked(target, MAX_LINKED)
    except DatabaseError as error:
        raise HTTPException(503, "Discussions are unavailable. Please try again.") from error
    return LinkedDiscussions(
        target=target,
        items=[
            LinkedDiscussion(
                id=row["id"],
                title=row["title"],
                author=row["author"],
                mentioned_at=row["mentioned_at"].replace(tzinfo=timezone.utc),
            )
            for row in rows
        ],
    )
