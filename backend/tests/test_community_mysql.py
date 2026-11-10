"""Exercise the public forum with separate owners, visitors, and real SQL storage."""
import os
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.app.data_controller.analysis_data_controller import AnalysisDataController
from backend.app.data_controller.community_data_controller import CommunityDataController
from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.main import app
from backend.tests.test_history import png, result

pytestmark = [pytest.mark.mysql, pytest.mark.skipif(os.getenv('RUN_MYSQL_TESTS') != '1', reason='Set RUN_MYSQL_TESTS=1')]


def test_public_discussion_keeps_private_analyses_and_comments_private(monkeypatch):
    monkeypatch.setattr(AnalysisDataController, 'analyze', lambda *a, **kw: result())
    name = uuid4().hex
    controller = UserDataController()
    users = []
    try:
        with TestClient(app, base_url='https://testserver', headers={'X-Requested-With': 'ASE'}) as owner, \
             TestClient(app, base_url='https://testserver', headers={'X-Requested-With': 'ASE'}) as other, \
             TestClient(app) as visitor:
            for index, client in enumerate((owner, other)):
                payload = {'email': f'{name}-{index}@ase3.com', 'username': f'forum-{name}-{index}', 'password': 'secret'}
                registered = client.post('/users/register', json=payload)
                assert registered.status_code == 201
                users.append(registered.json()['id'])
                login = client.post('/users/login', json=payload)
                assert login.status_code == 200
                client.headers['X-CSRF-Token'] = login.json()['csrf_token']
            upload = owner.post('/analysis', files={'file': ('tablet.png', png(), 'image/png')})
            assert upload.status_code == 200
            analysis_id = upload.json()['analysis_id']
            image_url = f'/analysis/{analysis_id}/image'
            assert owner.get(image_url).content == png()
            assert other.get(image_url).status_code == 404
            assert visitor.get(image_url).status_code == 401
            private_url = f'/users/me/analyses/{analysis_id}'
            assert owner.get(private_url).json()['image_url'] == f'/api{image_url}'
            assert owner.post(f'{private_url}/comments', json={'body': 'PRIVATE_NOTE'}).status_code == 201
            payload = {'analysis_id': analysis_id, 'title': 'Interpretation of the tablet'}
            assert other.post('/community/discussions', json=payload).status_code == 404
            # Two simultaneous shares return the same discussion, only one is created.
            with ThreadPoolExecutor(max_workers=2) as pool:
                shares = list(pool.map(lambda _: CommunityDataController().create_discussion(users[0], analysis_id, payload['title']), range(2)))
            assert sorted(created for _, created in shares) == [False, True]
            discussion_id = shares[0][0].id
            assert shares[1][0].id == discussion_id
            duplicate = owner.post('/community/discussions', json=payload)
            assert duplicate.status_code == 200 and duplicate.json()['id'] == discussion_id
            path = f'/community/discussions/{discussion_id}'
            listing = visitor.get('/community/discussions?limit=1').json()
            assert listing['items'][0]['id'] == discussion_id
            detail = visitor.get(path).json()
            assert detail['result']['symbol_interpretation'] == 'ku'
            assert 'crop' not in detail['result']['signs'][0]
            assert 'PRIVATE_NOTE' not in str(detail)
            assert visitor.get(path + '/image').content == png()
            assert visitor.get(path + '/comments').json() == []
            assert other.get(private_url).status_code == 404
            assert other.get(private_url + '/comments').status_code == 404
            assert owner.get(private_url).json()['discussion_id'] == discussion_id
            assert visitor.post(path + '/comments', json={'body': 'anonymous'}).status_code == 401
            assert other.post(path + '/comments', json={'body': 'bad csrf'}, headers={'X-CSRF-Token': 'wrong'}).status_code == 403
            for client, text in ((other, 'First public comment'), (owner, 'Second public comment')):
                response = client.post(path + '/comments', json={'body': text, 'author_id': 999})
                assert response.status_code == 201
            comments = visitor.get(path + '/comments').json()
            assert [c['body'] for c in comments] == ['First public comment', 'Second public comment']
            assert [c['author_id'] for c in comments] == [users[1], users[0]]
            assert all(c['author_username'].startswith('forum-') and c['created_at'].endswith('Z') for c in comments)
            assert visitor.get('/community/discussions/18446744073709551615').status_code == 404
            assert other.post('/community/discussions/18446744073709551615/comments', json={'body': 'missing'}).status_code == 404
            # A legacy analysis is not shareable, and a second discussion has a separate thread.
            legacy = AnalysisDataController().save_analysis(users[0], 'old.png', 'PNG', len(png()), result())
            assert owner.post('/community/discussions', json={'analysis_id': legacy.id, 'title': 'Old'}).status_code == 409
            second = owner.post('/analysis', files={'file': ('second.png', png(), 'image/png')}).json()
            shared = owner.post('/community/discussions', json={'analysis_id': second['analysis_id'], 'title': 'Second'})
            assert shared.status_code == 201
            second_id = shared.json()['id']
            assert visitor.get(f'/community/discussions/{second_id}/comments').json() == []
            page = visitor.get('/community/discussions?limit=1').json()
            assert page['next_before'] == second_id
            following = visitor.get(f'/community/discussions?limit=1&before={second_id}').json()
            assert following['items'][0]['id'] == discussion_id
            # Applying the migration repeatedly preserves discussions and private notes.
            sql = (Path(__file__).resolve().parents[1] / 'app/database/migration-60/061-community.sql').read_text()
            for _ in range(2):
                with controller.connection() as connection:
                    cursor = connection.cursor()
                    for statement in sql.split(';'):
                        if statement.strip() and not statement.strip().startswith('-- analysis_comment remains'):
                            cursor.execute(statement)
                    cursor.close()
            assert len(visitor.get(path + '/comments').json()) == 2
            assert owner.get(private_url + '/comments').json()[0]['body'] == 'PRIVATE_NOTE'
    finally:
        with controller.connection() as connection:
            cursor = connection.cursor()
            for identifier in users:
                cursor.execute('DELETE FROM `user` WHERE id = %s', (identifier,))
            cursor.close()
