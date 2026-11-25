"""Stable, typed references in comment text; no HTML or user-supplied URLs."""
import json
import re
from dataclasses import dataclass

from backend.app.model.analysis import DetectedSign
from backend.app.model.mention import MentionTarget, ResolvedMention

MENTION_PATTERN = re.compile(
    r'@\[((?:\\[\\\]]|[^\]\\\r\n]){1,255})\]\((user:[0-9]{1,20}|symbol:[0-9]{1,20}:[0-9]{1,20})\)'
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
    resolved = []
    for refs in parsed:
        mentions = []
        for ref in refs:
            target = targets.get(ref.key) or MentionTarget(
                key=ref.key, kind=ref.kind, label=ref.label, available=False,
                user_id=ref.user_id, analysis_id=ref.analysis_id, sign_id=ref.sign_id,
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
        raise InvalidMention('A mentioned user or public symbol is no longer available. Remove or replace the mention.')
    return mentions
