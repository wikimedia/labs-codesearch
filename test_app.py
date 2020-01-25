"""
Copyright (C) 2020 Kunal Mehta <legoktm@member.fsf.org>

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
    assert 'Strict-Transport-Security' in rv.headers


def test_index_url(client):
    client.get('/')
    assert '<b>Everything</b>' == app.index_url('search', 'search')
    assert '<a href="/extensions/">Extensions</a>' == app.index_url('extensions', 'search')


def test_index(client, requests_mock):
    requests_mock.get('http://localhost:6080/', text='<body>')
    rv = client.get('/search/')
    assert '<b>Everything</b> . ' \
           '<a href="/extensions/">Extensions</a> . ' \
           '<a href="/skins/">Skins</a>\n</div>' in rv.data.decode()


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


@pytest.mark.parametrize('input,expected', ((
    ('<title>Hound</title>', '<title>MediaWiki code search</title>'),
    (app.HOUND_STARTUP, 'Hound is still starting up')
)))
def test_backend(client, requests_mock, input, expected):
    requests_mock.get('http://localhost:6080/', text=input)
    rv = client.get('/search/')
    assert expected in rv.data.decode()


def test_invalid_backend(client):
    rv = client.get('/foobarbaz/')
    assert b'invalid backend' == rv.data
