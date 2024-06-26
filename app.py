#!/usr/bin/env python3
"""
Proxy requests to hound
Copyright (C) 2017-2020 Kunal Mehta <legoktm@debian.org>

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

from flask import Flask, Response, request, redirect, url_for, \
    send_from_directory, jsonify

from collections import OrderedDict
import json
import os
import re
import requests
import subprocess
import traceback

app = Flask(__name__)
if os.path.exists('/etc/codesearch_ports.json'):
    with open('/etc/codesearch_ports.json') as f:
        app.config['PORTS'] = json.load(f)

HIDDEN = ['armchairgm', 'shouthow', 'devtools']
HOUND_STARTUP = 'Hound is not ready.\n'


@app.after_request
def after_request(resp):
    # https://flask.palletsprojects.com/en/1.1.x/api/#flask.Flask.after_request
    resp.headers['access-control-allow-origin'] = '*'
    return resp


@app.route('/')
def homepage():
    return redirect(url_for('index', backend='search'))


def parse_systemctl_show(output):
    """
    turn the output of `systemctl show` into
    a dictionary
    """
    data = {}
    for line in output.splitlines():
        sp = line.split('=', 1)
        data[sp[0]] = sp[1]

    return data


def _health() -> OrderedDict:
    status = OrderedDict()
    for backend, port in sorted(app.config['PORTS'].items()):
        # First try to hit the hound backend, if it's up, we're good
        try:
            r = requests.get(f'http://localhost:{port}/api/v1/search')
            if r.text == HOUND_STARTUP:
                status[backend] = 'starting up'
            else:
                status[backend] = 'up'
        except requests.exceptions.ConnectionError:
            # See whether the systemd unit is running
            try:
                show = subprocess.check_output(
                    ['systemctl', 'show', f'hound-{backend}']
                )
                info = parse_systemctl_show(show.decode())
                if info['MainPID'] == '0':
                    status[backend] = 'down'
                else:
                    # No webservice, so hound hasn't started yet so it's waiting
                    status[backend] = 'pre-start'
            except subprocess.CalledProcessError:
                status[backend] = 'unknown'

    return status


@app.route('/_health')
def health():
    return redirect('https://codesearch.wmcloud.org/_health/')


@app.route('/_health.json')
def health_json():
    return jsonify(_health())


@app.route('/_metrics')
def metrics():
    text = """
# HELP codesearch_backend Whether Hound backend is up or not
# TYPE codesearch_backend gauge
"""
    for backend, status in _health().items():
        text += 'codesearch_backend{backend="%s"} %s\n' % (backend, int(status == "up"))
    return Response(text, mimetype="text/plain")


@app.route('/<backend>/')
def index(backend):
    if backend not in app.config['PORTS']:
        return 'invalid backend'
    sep = '</li><li class="index">'
    urls = sep.join('<a href="{}">{}</a>'.format(url_for('index', backend=target), target)
                    for target in app.config['PORTS']
                    if target not in HIDDEN)

    title = f'<title>Hound: {backend} - MediaWiki Codesearch</title>'

    # max-width matches hound's css for #root
    header = f"""
<div style="text-align: center; max-width: 960px; margin: 0 auto;">
<h2>Hound: /{backend}</h2>
<ul><li class="index">{urls}</li></ul>
</div>
"""

    style = """
<style>
.index {
    display: inline;
}
.index a {
    white-space: nowrap;
}
.index:after {
    content:" • ";
}
.index:last-child:after {
    content: none;
}
</style>
"""

    footer = """
<p style="text-align: center;">
<a href="https://gerrit.wikimedia.org/g/labs/codesearch">Source code</a> &bull;
<a href="https://phabricator.wikimedia.org/tag/vps-project-codesearch/">Issue tracker</a>
<br />
<a href="https://www.mediawiki.org/wiki/Codesearch">MediaWiki Codesearch</a>
is powered by <a href="https://github.com/hound-search/hound">Hound</a>.
License: GPL-3.0-or-later.
</p>
"""

    def mangle(text):
        text = text.replace('<title>Hound</title>', title)
        text = re.sub(r'<link rel="search".*?/>', '', text, flags=re.DOTALL)
        text = text.replace('</head>', style + '</head>')
        text = text.replace('<body>', '<body>' + header)
        text = text.replace('</body>', footer + '</body>')
        return text
    return proxy(backend, mangle=mangle)


@app.route('/<backend>/config.json')
def config_json(backend):
    if backend not in app.config['PORTS']:
        return 'invalid backend'
    resp = send_from_directory(
        f'/srv/hound/hound-{backend}',
        'config.json'
    )
    return resp


@app.route('/<backend>/<path:path>')
def proxy(backend, path='', mangle=False):
    if backend not in app.config['PORTS']:
        return 'invalid backend'
    port = app.config['PORTS'][backend]
    try:
        r = requests.get(
            f'http://localhost:{port}/{path}',
            params=request.args
        )
        if r.text == HOUND_STARTUP:
            return Response("""
Hound is still starting up, please wait a few minutes for the initial indexing
to complete. See <https://codesearch.wmcloud.org/_health> for more
information.
""", 503, mimetype='text/plain')
    except requests.exceptions.ConnectionError:
        resp = """
Unable to contact hound. If <https://codesearch.wmcloud.org/_health>
says "starting up", please wait a few minutes for the initial indexing
to complete.

If this error continues, please report it in Phabricator
with the following information:

"""
        resp += traceback.format_exc()
        return Response(resp, 503, mimetype='text/plain')
    excluded_headers = [
        'content-encoding', 'content-length', 'transfer-encoding', 'connection'
    ]
    headers = [(name, value) for (name, value) in r.raw.headers.items()
               if name.lower() not in excluded_headers]
    if mangle:
        text = mangle(r.text)
    else:
        text = r.content
    resp = Response(
        text,
        r.status_code,
        headers
    )
    if path == 'api/v1/repos':
        # Allow this endpoint to be cached
        resp.add_etag()
    return resp.make_conditional(request)


if __name__ == '__main__':
    app.run(debug=True)
