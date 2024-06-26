"""
Copyright (C) 2020 Kunal Mehta <legoktm@debian.org>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import json
import pytest

import app


@pytest.fixture
def client():
    app.app.config['TESTING'] = True
    app.app.config['PORTS'] = {
        'search': 6080,
        'extensions': 6081,
        'skins': 6082,
    }
    with app.app.test_client() as client:
        yield client


def test_homepage(client):
    # Redirect to /search/
    rv = client.get('/')
    assert rv.headers['Location'] == 'http://localhost/search/'


def test_index(client, requests_mock):
    requests_mock.get('http://localhost:6080/', text='<body>')
    rv = client.get('/search/')
    assert '<ul><li class="index"><a href="/search/">search</a></li>' \
           '<li class="index"><a href="/extensions/">extensions</a></li>' \
           '<li class="index"><a href="/skins/">skins</a></li></ul>\n</div>' in rv.data.decode()


def test_api_v1_repos(client, requests_mock):
    # Verify this endpoint has an etag
    requests_mock.get('http://localhost:6080/api/v1/repos', text='{}')
    rv = client.get('/search/api/v1/repos')
    etag = rv.headers['etag']
    assert rv.status_code == 200
    rv2 = client.get('/search/api/v1/repos', headers={'if-none-match': etag})
    assert rv2.status_code == 304
    rv3 = client.get('/search/api/v1/repos', headers={'if-none-match': 'blahblahblah'})
    assert rv3.status_code == 200


def test_api_v1_search(client, requests_mock):
    # no etag for this endpoint
    requests_mock.get('http://localhost:6080/api/v1/search', text='{}')
    rv = client.get('/search/api/v1/search')
    assert 'etag' not in rv.headers


def test_parse_systemctl_show():
    # Abbreviated version of output
    input = """
Type=simple
Restart=on-failure
MainPID=16251
""".lstrip()
    parsed = app.parse_systemctl_show(input)
    assert parsed['MainPID'] == '16251'


def test_health_json(mocker, client):
    health = {'search': 'starting up', 'extensions': 'up', 'skins': 'down'}
    mock = mocker.patch('app._health')
    mock.return_value = health
    rv = client.get('/_health.json')
    assert json.loads(rv.data.decode()) == health


def test_metrics(mocker, client):
    health = {'search': 'starting up', 'extensions': 'up', 'skins': 'down'}
    mock = mocker.patch('app._health')
    mock.return_value = health
    rv = client.get('/_metrics')
    assert rv.data.decode() == """
# HELP codesearch_backend Whether Hound backend is up or not
# TYPE codesearch_backend gauge
codesearch_backend{backend="search"} 0
codesearch_backend{backend="extensions"} 1
codesearch_backend{backend="skins"} 0
"""


@pytest.mark.parametrize('input,expected', ((
    ('<title>Hound</title>', '<title>Hound: search - MediaWiki Codesearch</title>'),
    (app.HOUND_STARTUP, 'Hound is still starting up')
)))
def test_backend(client, requests_mock, input, expected):
    requests_mock.get('http://localhost:6080/', text=input)
    rv = client.get('/search/')
    assert expected in rv.data.decode()


def test_invalid_backend(client):
    rv = client.get('/foobarbaz/')
    assert b'invalid backend' == rv.data
