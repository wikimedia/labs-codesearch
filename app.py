#!/usr/bin/env python3
"""
Proxy requests to hound
Copyright (C) 2017-2020 Kunal Mehta <legoktm@member.fsf.org>

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
    send_from_directory, render_template, jsonify

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

# This order is the order they will display in the UI
DESCRIPTIONS = {
    'search': 'Everything',
    'core': 'MediaWiki core',
    'extensions': 'Extensions',
    'skins': 'Skins',
    'things': 'Extensions & skins',
    'bundled': 'MW tarball',
    'deployed': 'Wikimedia deployed',
    'libraries': 'PHP libraries',
    'operations': 'Wikimedia Operations',
    'ooui': 'OOUI',
    'milkshake': 'Milkshake',
    'pywikibot': 'Pywikibot',
    'services': 'Wikimedia Services',
    'analytics': 'Analytics',
    # Not visible
    'armchairgm': 'ArmchairGM',
}

LINK_OPENSEARCH = re.compile('<link rel="search" .*?/>', flags=re.DOTALL)
HOUND_STARTUP = 'Hound is not ready.\n'


@app.before_request
def redirect_to_https():
    if request.headers.get('X-Forwarded-Proto') == 'http':
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, 302)


@app.after_request
def set_hsts(response):
    if not app.debug:
        response.headers['Strict-Transport-Security'] = 'max-age=86400'

    return response


@app.route('/favicon.ico')
def favicon():
    # http://flask.pocoo.org/docs/0.12/patterns/favicon/
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon')


def index_url(target, current):
    text = DESCRIPTIONS[target]
    if target == current:
        return f'<b>{text}</b>'
    else:
        return '<a href="{}">{}</a>'.format(
            url_for('index', backend=target),
            text
        )


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
    return render_template('health.html', status=_health())


@app.route('/_health.json')
def health_json():
    return jsonify(_health())


@app.route('/<backend>/')
def index(backend):
    if backend not in app.config['PORTS']:
        return 'invalid backend'
    sep = '</li><li class="index">'
    urls = sep.join(index_url(target, backend)
                    for target in DESCRIPTIONS
                    if target != 'armchairgm' and target in app.config['PORTS'])
    # max-width matches hound's css for #root
    header = f"""
<div style="text-align: center; max-width: 960px; margin: 0 auto;">
<h2>MediaWiki code search</h2>

<ul><li class="index">{urls}</li></ul>
</div>
"""
    title = '<title>MediaWiki code search</title>'

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
<a href="https://www.mediawiki.org/wiki/codesearch">MediaWiki code search</a>
is powered by <a href="https://github.com/hound-search/hound">hound</a>.
<br />
<a href="https://gerrit.wikimedia.org/g/labs/codesearch">Source code</a>
is available under the terms of the GPL v3 or any later version.
</p>
"""

    opensearch_link = """
<link rel="search" href="%s"
      type="application/opensearchdescription+xml"
      title="MediaWiki code search" />
""" % url_for('opensearch', backend=backend)

    def mangle(text):
        text = text.replace('<body>', '<body>' + header)
        text = text.replace('</body>', footer + '</body>')
        text = text.replace('<title>Hound</title>', title)
        text = text.replace('</head>', style + '</head>')
        text = LINK_OPENSEARCH.sub(opensearch_link, text)
        return text
    return proxy(backend, mangle=mangle)


@app.route('/<backend>/open_search.xml')
def opensearch(backend):
    if backend not in app.config['PORTS']:
        return 'invalid backend'
    temp = render_template('open_search.xml', backend=backend,
                           description=DESCRIPTIONS[backend])
    return Response(temp, content_type='text/xml')


@app.route('/<backend>/config.json')
def config_json(backend):
    if backend not in app.config['PORTS']:
        return 'invalid backend'
    resp = send_from_directory(
        f'/srv/hound/hound-{backend}',
        'config.json'
    )
    resp.headers['access-control-allow-origin'] = '*'
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
