"""Stable, typed references in comment text; no HTML or user-supplied URLs."""
import json
import re
from dataclasses import dataclass

from backend.app.model.analysis import DetectedSign
from backend.app.model.mention import MentionTarget, ResolvedMention

MENTION_PATTERN = re.compile(
    r'@\[((?:\\[\\\]]|[^\]\\\r\n]){1,255})\]\((user:[0-9]{1,20}|symbol:[0-9]{1,20}:[0-9]{1,20}|sign:[A-Za-z0-9]{1,12}|glyph:[A-Za-z0-9]+(?:-[A-Za-z0-9]+){0,6}:[0-9]{1,7}|edition:[0-9]{1,20})\)'
)
MAX_MENTIONS = 20


class InvalidMention(ValueError):
    pass


@dataclass
class MentionReference:
    token: str
    key: str
    label: str
    kind: str
    user_id: int | None = None
    analysis_id: int | None = None
    sign_id: int | None = None
    sign_code: str | None = None  # a catalogue sign, e.g. "AB81"
    glyph_tablet: str | None = None  # a corpus glyph: its tablet's slug and position (workbench, story L)
    glyph_position: int | None = None
    release_id: int | None = None  # a released edition (workbench, story L)


@dataclass
class PublicSymbol:
    target: MentionTarget
    symbol: DetectedSign
    storage_key: str | None


def find_symbol(result: dict, sign_id: int) -> DetectedSign | None:
    for sign in result['signs']:
        if sign['id'] == sign_id:
            return DetectedSign(**{**sign, 'crop': None})
    return None


def symbol_name(symbol: DetectedSign) -> str:
    if not symbol.sign:
        return f'symbol-{symbol.id}'
    return symbol.reading or symbol.label or symbol.sign


def parse_mentions(body: str, *, strict: bool = False) -> list[MentionReference]:
    references = []
    for match in MENTION_PATTERN.finditer(body):
        label = re.sub(r'\\([\\\]])', r'\1', match[1])
        parts = match[2].split(':')
        if parts[0] == 'sign':
            references.append(MentionReference(token=match[0], key=match[2], label=label, kind='sign',
                                               sign_code=parts[1]))
            continue
        if parts[0] == 'glyph':
            if len(parts[1]) <= 64:
                references.append(MentionReference(token=match[0], key=match[2], label=label, kind='glyph',
                                                   glyph_tablet=parts[1], glyph_position=int(parts[2])))
            elif strict:
                raise InvalidMention('A mention has an invalid identifier.')
            continue
        if parts[0] == 'edition':
            if 0 < int(parts[1]) <= 2**64 - 1:
                references.append(MentionReference(token=match[0], key=match[2], label=label, kind='edition',
                                                   release_id=int(parts[1])))
            elif strict:
                raise InvalidMention('A mention has an invalid identifier.')
            continue
        identifier = int(parts[1])
        sign_id = int(parts[2]) if parts[0] == 'symbol' else None
        if not 0 < identifier <= 2**64 - 1 or (sign_id is not None and sign_id > 2**63 - 1):
            if strict:
                raise InvalidMention('A mention has an invalid identifier.')
            continue
        key = f'user:{identifier}' if sign_id is None else f'symbol:{identifier}:{sign_id}'
        references.append(MentionReference(
            token=match[0], key=key, label=label, kind=parts[0],
            user_id=identifier if sign_id is None else None,
            analysis_id=identifier if sign_id is not None else None, sign_id=sign_id,
        ))
    return references


def public_symbols(cursor, analysis_ids: set[int]) -> dict[str, PublicSymbol]:
    """Only published occurrences, unless the whole analysis is public."""
    symbols = {}
    identifiers = sorted(analysis_ids)
    for start in range(0, len(identifiers), 200):
        batch = identifiers[start:start + 200]
        placeholders = ', '.join(['%s'] * len(batch))
        cursor.execute(
            'SELECT a.id, a.filename, a.result_json, i.storage_key FROM analysis a '
            'LEFT JOIN analysis_image i ON i.analysis_id = a.id '
            f'WHERE a.id IN ({placeholders}) AND EXISTS '
            '(SELECT 1 FROM community_discussion d WHERE d.analysis_id = a.id)', tuple(batch))
        analyses = cursor.fetchall()
        cursor.execute('SELECT id, analysis_id, sign_id FROM community_discussion '
                       f'WHERE analysis_id IN ({placeholders})', tuple(batch))
        threads = {}
        for row in cursor.fetchall():
            threads.setdefault(row['analysis_id'], {})[row['sign_id']] = row['id']
        for analysis in analyses:
            shared = threads.get(analysis['id'], {})
            for raw in json.loads(analysis['result_json'])['signs']:
                if None not in shared and raw['id'] not in shared:
                    continue
                symbol = DetectedSign(**{**raw, 'crop': None})
                key = f"symbol:{analysis['id']}:{symbol.id}"
                target = MentionTarget(
                    key=key, kind='symbol', label=symbol_name(symbol), analysis_id=analysis['id'],
                    sign_id=symbol.id, tablet_filename=analysis['filename'],
                    image_url=f"/api/community/symbols/{analysis['id']}/{symbol.id}/image",
                    discussion_id=shared.get(symbol.id),
                )
                symbols[key] = PublicSymbol(target, symbol, analysis['storage_key'])
    return symbols


def catalogue_signs(wanted: dict[str, str]) -> dict[str, MentionTarget]:
    """Mentions of catalogue signs (key -> sign as written), with the catalogue's name and the
    sign's preview picture. A sign not in the catalogue is left out (shown as unavailable)."""
    if not wanted:
        return {}
    from backend.app.data_controller.correction_data_controller import catalogue, sign_key
    signs = {sign_key(sign.sign): sign for sign in catalogue()}
    found = {}
    for key, code in wanted.items():
        sign = signs.get(sign_key(code))
        if sign is not None:
            found[key] = MentionTarget(key=key, kind='sign', label=sign.name, sign_code=sign.sign,
                                       image_url=f'/api{sign.preview_url}' if sign.preview_url else None)
    return found


def corpus_glyphs(wanted: dict) -> dict[str, MentionTarget]:
    """Mentions of corpus glyphs (a tablet and the scholars' position): available when the corpus
    has that occurrence; shown with the tablet's thumbnail, the glyph outlined."""
    if not wanted:
        return {}
    from backend.app import glyph_index
    try:
        index = glyph_index.get_index()
    except glyph_index.CorpusMissing:
        return {}
    found = {}
    for key, ref in wanted.items():
        occurrence = index.lookup(ref.glyph_tablet, ref.glyph_position)
        if occurrence is not None:
            name = occurrence.reading or occurrence.sign
            found[key] = MentionTarget(
                key=key, kind='glyph', label=f'{occurrence.tablet} · {name}', glyph_tablet=ref.glyph_tablet,
                glyph_position=ref.glyph_position,
                image_url=f'/api/tablets/{ref.glyph_tablet}/thumbnail.png?position={ref.glyph_position}')
    return found


def released_editions(wanted: dict) -> dict[str, MentionTarget]:
    """Mentions of edition releases: available while the edition is open to everyone."""
    if not wanted:
        return {}
    from mysql.connector import Error as DatabaseError

    from backend.app.data_controller.edition_data_controller import EditionDataController
    controller = EditionDataController()
    found = {}
    for key, ref in wanted.items():
        try:
            row = controller.release(ref.release_id)
        except DatabaseError:
            row = None
        if row is not None and row['everyone'] != 'none':
            title = row['title'] or f"{row['owner']}'s edition of {row['tablet_slug'].replace('-', ' ')}"
            found[key] = MentionTarget(key=key, kind='edition', label=f"{title}, release {row['number']}",
                                       release_id=row['id'], glyph_tablet=row['tablet_slug'])
    return found


def resolve_mentions(cursor, bodies: list[str]) -> list[list[ResolvedMention]]:
    parsed = [parse_mentions(body) for body in bodies]
    user_ids = sorted({ref.user_id for refs in parsed for ref in refs if ref.kind == 'user'})
    targets = {}
    for start in range(0, len(user_ids), 200):
        batch = user_ids[start:start + 200]
        placeholders = ', '.join(['%s'] * len(batch))
        cursor.execute(f'SELECT id, username FROM `user` WHERE id IN ({placeholders})', tuple(batch))
        for row in cursor.fetchall():
            key = f"user:{row['id']}"
            targets[key] = MentionTarget(key=key, kind='user', label=row['username'], user_id=row['id'])
    analyses = {ref.analysis_id for refs in parsed for ref in refs if ref.kind == 'symbol'}
    targets.update({key: item.target for key, item in public_symbols(cursor, analyses).items()})
    targets.update(catalogue_signs({ref.key: ref.sign_code for refs in parsed for ref in refs if ref.kind == 'sign'}))
    targets.update(corpus_glyphs({ref.key: ref for refs in parsed for ref in refs if ref.kind == 'glyph'}))
    targets.update(released_editions({ref.key: ref for refs in parsed for ref in refs if ref.kind == 'edition'}))
    resolved = []
    for refs in parsed:
        mentions = []
        for ref in refs:
            target = targets.get(ref.key) or MentionTarget(
                key=ref.key, kind=ref.kind, label=ref.label, available=False,
                user_id=ref.user_id, analysis_id=ref.analysis_id, sign_id=ref.sign_id, sign_code=ref.sign_code,
                glyph_tablet=ref.glyph_tablet, glyph_position=ref.glyph_position, release_id=ref.release_id,
            )
            mentions.append(ResolvedMention(**target.model_dump(), token=ref.token))
        resolved.append(mentions)
    return resolved


def validate_mentions(cursor, body: str) -> list[ResolvedMention]:
    references = parse_mentions(body, strict=True)
    if len(references) > MAX_MENTIONS:
        raise InvalidMention(f'A comment can contain at most {MAX_MENTIONS} mentions.')
    mentions = resolve_mentions(cursor, [body])[0]
    if any(not mention.available for mention in mentions):
        raise InvalidMention('A mentioned user, symbol, sign, glyph or edition is not available. Remove or replace the mention.')
    return mentions
