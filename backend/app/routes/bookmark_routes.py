"""Bookmarked tablets (scholars' workbench, story K): a user's own list, shown first on the
Tablets page. At most MAX_BOOKMARKS per user."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from mysql.connector import Error as DatabaseError
from pydantic import BaseModel

from backend.app.auth import AuthenticatedWrite, CurrentUser
from backend.app.data_controller.data_controller import DataController
from backend.app.model.analysis import ApiError

router = APIRouter(tags=["bookmarks"])
Slug = Annotated[str, Path(pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$", max_length=64)]
ERRORS = {code: {"model": ApiError} for code in (401, 403, 409, 422, 503)}
MAX_BOOKMARKS = 200
UNAVAILABLE = "Bookmarks are unavailable. Please try again."


class BookmarkDataController(DataController):
    def bookmarks(self, user_id: int) -> list[str]:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    "SELECT tablet_slug FROM tablet_bookmark WHERE user_id = %s "
                    "ORDER BY created_at DESC, tablet_slug",
                    (user_id,),
                )
                return [row["tablet_slug"] for row in cursor.fetchall()]
            finally:
                cursor.close()

    def add(self, user_id: int, slug: str) -> None:
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "INSERT INTO tablet_bookmark (user_id, tablet_slug, created_at) VALUES (%s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE tablet_slug = tablet_slug",
                    (user_id, slug, datetime.now(timezone.utc).replace(tzinfo=None)),
                )
            finally:
                cursor.close()

    def remove(self, user_id: int, slug: str) -> None:
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "DELETE FROM tablet_bookmark WHERE user_id = %s AND tablet_slug = %s",
                    (user_id, slug),
                )
            finally:
                cursor.close()


def get_bookmark_data_controller() -> BookmarkDataController:
    return BookmarkDataController()


Bookmarks = Annotated[BookmarkDataController, Depends(get_bookmark_data_controller)]


class BookmarkList(BaseModel):
    tablets: list[str]  # slugs, the latest first


@router.get("/bookmarks", response_model=BookmarkList, responses=ERRORS)
def list_bookmarks(user: CurrentUser, bookmarks: Bookmarks) -> BookmarkList:
    try:
        return BookmarkList(tablets=bookmarks.bookmarks(user.id))
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error


@router.put("/bookmarks/{slug}", response_model=BookmarkList, responses=ERRORS)
def add_bookmark(slug: Slug, user: AuthenticatedWrite, bookmarks: Bookmarks) -> BookmarkList:
    """Bookmark a tablet (again is fine); at most 200."""
    try:
        current = bookmarks.bookmarks(user.id)
        if slug not in current and len(current) >= MAX_BOOKMARKS:
            raise HTTPException(409, f"You can bookmark at most {MAX_BOOKMARKS} tablets.")
        bookmarks.add(user.id, slug)
        return BookmarkList(tablets=bookmarks.bookmarks(user.id))
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error


@router.delete("/bookmarks/{slug}", response_model=BookmarkList, responses=ERRORS)
def remove_bookmark(slug: Slug, user: AuthenticatedWrite, bookmarks: Bookmarks) -> BookmarkList:
    try:
        bookmarks.remove(user.id, slug)
        return BookmarkList(tablets=bookmarks.bookmarks(user.id))
    except DatabaseError as error:
        raise HTTPException(503, UNAVAILABLE) from error
