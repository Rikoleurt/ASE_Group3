"""SQL for edition releases, votes, the admin override and voting rights (workbench, story E).
The rules (who may vote, which edition is accepted) are in backend/app/routes/edition_routes.py."""

import json
from datetime import UTC, datetime

from backend.app.data_controller.data_controller import DataController

RELEASE_COLUMNS = (
    "r.id, r.set_id, r.number, r.tablet_slug, r.title, r.notes, r.version, r.width, r.height, r.boxes, "
    "r.merged_from, r.contributors, r.created_at, u.username AS owner, s.everyone, s.owner_id"
)
RELEASE_FROM = (
    "FROM edition_release r JOIN box_set s ON s.id = r.set_id JOIN `user` u ON u.id = s.owner_id"
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _decoded(row: dict) -> dict:
    for name in ("boxes", "merged_from", "contributors"):
        if isinstance(row.get(name), (str, bytes)):
            row[name] = json.loads(row[name])
    return row


class EditionDataController(DataController):
    # Releases.

    def create_release(self, set_id: int, created_by: int, snapshot: dict) -> int:
        """Release the edition as it is now (number = the next one), and open it to everyone
        for viewing if it was private, since a release is for others to vote on."""
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute("SELECT everyone FROM box_set WHERE id = %s FOR UPDATE", (set_id,))
                cursor.fetchone()
                cursor.execute(
                    "SELECT COALESCE(MAX(number), 0) + 1 AS next FROM edition_release WHERE set_id = %s",
                    (set_id,),
                )
                number = cursor.fetchone()["next"]
                cursor.execute(
                    "INSERT INTO edition_release (set_id, number, tablet_slug, title, notes, version, width, height, "
                    "boxes, merged_from, contributors, created_by, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        set_id,
                        number,
                        snapshot["tablet"],
                        snapshot["title"],
                        snapshot["notes"],
                        snapshot["version"],
                        snapshot["width"],
                        snapshot["height"],
                        json.dumps(snapshot["boxes"]),
                        json.dumps(snapshot["merged_from"]),
                        json.dumps(snapshot["contributors"]),
                        created_by,
                        _now(),
                    ),
                )
                release_id = cursor.lastrowid
                cursor.execute(
                    "UPDATE box_set SET everyone = 'view' WHERE id = %s AND everyone = 'none'",
                    (set_id,),
                )
            finally:
                cursor.close()
        return release_id

    def release(self, release_id: int) -> dict | None:
        rows = self._rows(f"SELECT {RELEASE_COLUMNS} {RELEASE_FROM} WHERE r.id = %s", (release_id,))
        return _decoded(rows[0]) if rows else None

    def releases_of(self, set_id: int) -> list[dict]:
        return [
            _decoded(row)
            for row in self._rows(
                f"SELECT {RELEASE_COLUMNS} {RELEASE_FROM} WHERE r.set_id = %s ORDER BY r.number DESC",
                (set_id,),
            )
        ]

    def tablet_releases(self, slug: str) -> list[dict]:
        """Releases of the tablet's editions that are open to everyone, oldest first."""
        return [
            _decoded(row)
            for row in self._rows(
                f"SELECT {RELEASE_COLUMNS} {RELEASE_FROM} WHERE r.tablet_slug = %s AND s.everyone <> 'none' "
                "ORDER BY r.created_at, r.id",
                (slug,),
            )
        ]

    def released_tablets(self) -> list[str]:
        """Tablets with a release of an edition open to everyone."""
        return [
            row["tablet_slug"]
            for row in self._rows(
                "SELECT DISTINCT r.tablet_slug FROM edition_release r JOIN box_set s ON s.id = r.set_id "
                "WHERE s.everyone <> 'none' ORDER BY r.tablet_slug",
                (),
            )
        ]

    # Votes. Only accounts that may vote are counted; their votes are kept while they may not.

    def vote_counts(self, slug: str) -> dict[int, tuple[int, int]]:
        """release id -> (votes, of which by reviewers)."""
        rows = self._rows(
            "SELECT v.release_id, COUNT(*) AS votes, COALESCE(SUM(u.is_reviewer), 0) AS reviewers "
            "FROM edition_vote v JOIN `user` u ON u.id = v.user_id "
            "WHERE v.tablet_slug = %s AND u.can_vote GROUP BY v.release_id",
            (slug,),
        )
        return {row["release_id"]: (int(row["votes"]), int(row["reviewers"])) for row in rows}

    def my_vote(self, slug: str, user_id: int) -> int | None:
        rows = self._rows(
            "SELECT release_id FROM edition_vote WHERE tablet_slug = %s AND user_id = %s",
            (slug, user_id),
        )
        return rows[0]["release_id"] if rows else None

    def voter(self, user_id: int) -> dict | None:
        """{can_vote, old_enough}: whether the account may vote and has existed for a day."""
        rows = self._rows(
            "SELECT can_vote, (created_at IS NULL OR created_at <= NOW(6) - INTERVAL 1 DAY) AS old_enough "
            "FROM `user` WHERE id = %s",
            (user_id,),
        )
        return (
            {"can_vote": bool(rows[0]["can_vote"]), "old_enough": bool(rows[0]["old_enough"])}
            if rows
            else None
        )

    def vote(self, slug: str, user_id: int, release_id: int) -> None:
        self._rows(
            "INSERT INTO edition_vote (tablet_slug, user_id, release_id, created_at) VALUES (%s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE release_id = VALUES(release_id), created_at = VALUES(created_at)",
            (slug, user_id, release_id, _now()),
            fetch=False,
        )

    def unvote(self, slug: str, user_id: int) -> None:
        self._rows(
            "DELETE FROM edition_vote WHERE tablet_slug = %s AND user_id = %s",
            (slug, user_id),
            fetch=False,
        )

    # The admin override.

    def current_override(self, slug: str) -> dict | None:
        rows = self._rows(
            "SELECT o.release_id, u.username AS admin, o.comment, o.created_at FROM edition_override o "
            "LEFT JOIN `user` u ON u.id = o.admin_id WHERE o.tablet_slug = %s AND o.cleared_at IS NULL "
            "ORDER BY o.created_at DESC, o.id DESC LIMIT 1",
            (slug,),
        )
        return rows[0] if rows else None

    def set_override(self, slug: str, release_id: int, admin_id: int, comment: str) -> None:
        """Replace the tablet's override (the old one is kept, cleared, for the record)."""
        stamp = _now()
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "UPDATE edition_override SET cleared_at = %s, cleared_by = %s, clear_comment = %s "
                    "WHERE tablet_slug = %s AND cleared_at IS NULL",
                    (stamp, admin_id, "Replaced: " + comment, slug),
                )
                cursor.execute(
                    "INSERT INTO edition_override (tablet_slug, release_id, admin_id, comment, created_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (slug, release_id, admin_id, comment, stamp),
                )
            finally:
                cursor.close()

    def clear_override(self, slug: str, admin_id: int, comment: str) -> bool:
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "UPDATE edition_override SET cleared_at = %s, cleared_by = %s, clear_comment = %s "
                    "WHERE tablet_slug = %s AND cleared_at IS NULL",
                    (_now(), admin_id, comment, slug),
                )
                return cursor.rowcount > 0
            finally:
                cursor.close()

    # Voting rights.

    def voting_rights(self, user_id: int) -> dict | None:
        rows = self._rows(
            "SELECT u.can_vote, c.reason, a.username AS changed_by, c.created_at AS changed_at FROM `user` u "
            "LEFT JOIN vote_right_change c ON c.id = (SELECT MAX(id) FROM vote_right_change WHERE user_id = u.id) "
            "LEFT JOIN `user` a ON a.id = c.admin_id WHERE u.id = %s",
            (user_id,),
        )
        return {**rows[0], "can_vote": bool(rows[0]["can_vote"])} if rows else None

    def set_voting_rights(self, user_id: int, admin_id: int, can_vote: bool, reason: str) -> bool:
        """Grant or remove; False when there is no such user. The change and its reason are kept."""
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("UPDATE `user` SET can_vote = %s WHERE id = %s", (can_vote, user_id))
                cursor.execute("SELECT id FROM `user` WHERE id = %s", (user_id,))
                if cursor.fetchone() is None:
                    return False
                cursor.execute(
                    "INSERT INTO vote_right_change (user_id, admin_id, granted, reason, created_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (user_id, admin_id, can_vote, reason, _now()),
                )
            finally:
                cursor.close()
        return True

    def _rows(self, query: str, params: tuple, fetch: bool = True) -> list[dict]:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(query, params)
                return cursor.fetchall() if fetch else []
            finally:
                cursor.close()
