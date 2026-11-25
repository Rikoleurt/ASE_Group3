from backend.app.data_controller.data_controller import DataController
from backend.app.mentions import PublicSymbol, public_symbols
from backend.app.model.mention import MentionPage, MentionTarget


def literal_pattern(query: str) -> str:
    return '%' + query.strip().replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'


class MentionDataController(DataController):
    def search_mentions(self, discussion_id: int, kind: str, q: str, limit: int, after: int) -> MentionPage | None:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute('SELECT analysis_id FROM community_discussion WHERE id = %s', (discussion_id,))
                discussion = cursor.fetchone()
                if discussion is None:
                    return None
                if kind == 'user':
                    return self.search_user_mentions(cursor, q, limit, after)
                return self.search_symbol_mentions(cursor, discussion['analysis_id'], q, limit, after)
            finally:
                cursor.close()

    def search_user_mentions(self, cursor, q: str, limit: int, after: int) -> MentionPage:
        cursor.execute("SELECT id, username FROM `user` WHERE id > %s AND username LIKE %s ESCAPE '!' "
                       'ORDER BY id LIMIT %s', (after, literal_pattern(q), limit + 1))
        rows = cursor.fetchall()
        return MentionPage(items=[MentionTarget(key=f"user:{row['id']}", kind='user', user_id=row['id'],
                                                label=row['username']) for row in rows[:limit]],
                           next_after=rows[limit - 1]['id'] if len(rows) > limit else None)

    def search_symbol_mentions(self, cursor, analysis_id: int, q: str, limit: int, after: int) -> MentionPage:
        # This bounded response comes from the saved detection snapshot, never
        # from the current browser state or a new model invocation.
        needle = q.strip().casefold()
        symbols = sorted(public_symbols(cursor, {analysis_id}).values(), key=lambda item: item.symbol.id)
        matches = [item.target for item in symbols if item.symbol.id > after and
                   (not needle or needle in item.target.label.casefold() or needle in str(item.symbol.id)
                    or needle in (item.symbol.sign or '').casefold())]
        return MentionPage(items=matches[:limit], next_after=matches[limit - 1].sign_id if len(matches) > limit else None)

    def get_public_symbol(self, analysis_id: int, sign_id: int) -> PublicSymbol | None:
        with self.connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                return public_symbols(cursor, {analysis_id}).get(f'symbol:{analysis_id}:{sign_id}')
            finally:
                cursor.close()
