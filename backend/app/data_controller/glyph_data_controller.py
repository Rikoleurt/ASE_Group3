from datetime import datetime, timezone

from backend.app.data_controller.data_controller import DataController
from backend.app.model.glyph import Annotation, AnnotationAuthor, AnnotationTarget


class GlyphDataController(DataController):
    """Comments written once and saved against many glyph occurrences."""

    def create_annotation(self, author_id: int, sign_id: str, body: str,
                          targets: list[tuple[str, int]], author_username: str) -> Annotation:
        created_at = datetime.now(timezone.utc)
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "INSERT INTO glyph_annotation (author_id, sign_id, body, created_at) VALUES (%s, %s, %s, %s)",
                    (author_id, sign_id, body, created_at.replace(tzinfo=None)),
                )
                annotation_id = cursor.lastrowid
                cursor.executemany(
                    "INSERT INTO glyph_annotation_target (annotation_id, tablet_id, position) VALUES (%s, %s, %s)",
                    [(annotation_id, tablet, position) for tablet, position in targets],
                )
            finally:
                cursor.close()
        return Annotation(id=annotation_id, sign=sign_id, body=body, created_at=created_at,
                          author=AnnotationAuthor(id=author_id, username=author_username),
                          targets=[AnnotationTarget(tablet=t, position=p) for t, p in targets])

    def list_annotations(self, sign_id: str, limit: int, before: int | None = None) -> list[Annotation]:
        """Newest first. Reads one extra row so the caller can tell whether another page exists."""
        clause, params = "", [sign_id]
        if before is not None:
            clause = " AND a.id < %s"
            params.append(before)
        params.append(limit + 1)
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    "SELECT a.id, a.sign_id, a.body, a.created_at, a.author_id, u.username "
                    "FROM glyph_annotation a JOIN `user` u ON u.id = a.author_id "
                    "WHERE a.sign_id = %s" + clause + " ORDER BY a.id DESC LIMIT %s", tuple(params),
                )
                rows = cursor.fetchall()
                targets: dict[int, list[AnnotationTarget]] = {}
                shown = [row["id"] for row in rows[:limit]]
                if shown:
                    cursor.execute(
                        "SELECT annotation_id, tablet_id, position FROM glyph_annotation_target "
                        "WHERE annotation_id IN (" + ", ".join(["%s"] * len(shown)) + ") "
                        "ORDER BY annotation_id, tablet_id, position", tuple(shown),
                    )
                    for target in cursor.fetchall():
                        targets.setdefault(target["annotation_id"], []).append(
                            AnnotationTarget(tablet=target["tablet_id"], position=target["position"]))
            finally:
                cursor.close()
        return [
            Annotation(id=row["id"], sign=row["sign_id"], body=row["body"],
                       created_at=row["created_at"].replace(tzinfo=timezone.utc),
                       author=AnnotationAuthor(id=row["author_id"], username=row["username"]),
                       targets=targets.get(row["id"], []))
            for row in rows
        ]

    def delete_annotation(self, annotation_id: int, author_id: int) -> bool:
        """Only the author can delete; a foreign comment is indistinguishable from a missing one."""
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("DELETE FROM glyph_annotation WHERE id = %s AND author_id = %s",
                               (annotation_id, author_id))
                return cursor.rowcount > 0
            finally:
                cursor.close()
