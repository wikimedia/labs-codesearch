#!/usr/bin/env python3
"""
Proxy requests to hound
Copyright (C) 2017-2018 Kunal Mehta <legoktm@member.fsf.org>

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
    send_from_directory, render_template

import os
import re
import requests
import subprocess
import traceback

from ports import PORTS

app = Flask(__name__)

DESCRIPTIONS = {
    'search': 'Everything',
    'core': 'MediaWiki core',
    'extensions': 'Extensions',
    'skins': 'Skins',
    'things': 'Extensions & skins',
    'ooui': 'OOUI',
    'operations': 'Wikimedia Operations',
    'armchairgm': 'ArmchairGM',
    'milkshake': 'Milkshake',
    'bundled': 'MW tarball',
}

LINK_OPENSEARCH = re.compile('<link rel="search" .*?/>', flags=re.DOTALL)


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
        return '<b>%s</b>' % text
    else:
        return '<a href="%s">%s</a>' % (
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


@app.route('/_health')
def health():
    status = {}
    for backend, port in PORTS.items():
        # First try to hit the hound backend, if it's up, we're good
        try:
            requests.get('http://localhost:%s/api/v1/search' % port)
            status[backend] = 'up'
        except requests.exceptions.ConnectionError:
            # See whether the systemd unit is running
            try:
                show = subprocess.check_output(
                    ['systemctl', 'show', 'hound-%s' % backend]
                )
                info = parse_systemctl_show(show.decode())
                if info['MainPID'] == '0':
                    status[backend] = 'down'
                else:
                    # No webservice, but hound is running, so it's probably
                    # just starting up still
                    status[backend] = 'starting up'
            except subprocess.CalledProcessError:
                status[backend] = 'unknown'

    return render_template('health.html', status=status)


@app.route('/<backend>/')
def index(backend):
    if backend not in PORTS:
        return 'invalid backend'
    header = """
<div style="text-align: center;">
<h2>MediaWiki code search</h2>

{search} ·
{core} ·
{ext} ·
{skins} ·
{things}
{bundled}
{ooui}
{operations}
{milkshake}
</div>
""".format(
        search=index_url('search', backend),
        core=index_url('core', backend),
        ext=index_url('extensions', backend),
        skins=index_url('skins', backend),
        things=index_url('things', backend),
        ooui=index_url('ooui', backend),
        operations=index_url('operations', backend),
        milkshake=index_url('milkshake', backend),
        bundled=index_url('bundled', backend)
    )
    title = '<title>MediaWiki code search</title>'

    footer = """
<p style="text-align: center;">
<a href="https://www.mediawiki.org/wiki/codesearch">MediaWiki code search</a>
is powered by <a href="https://github.com/etsy/hound">hound</a>.
<br />
<a href="https://phabricator.wikimedia.org/diffusion/LCSH/">Source code</a>
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
        text = LINK_OPENSEARCH.sub(opensearch_link, text)
        return text
    return proxy(backend, mangle=mangle)


@app.route('/<backend>/open_search.xml')
def opensearch(backend):
    if backend not in PORTS:
        return 'invalid backend'
    temp = render_template('open_search.xml', backend=backend,
                           description=DESCRIPTIONS[backend])
    return Response(temp, content_type='text/xml')


@app.route('/<backend>/<path:path>')
def proxy(backend, path='', mangle=False):
    if backend not in PORTS:
        return 'invalid backend'
    port = PORTS[backend]
    try:
        r = requests.get(
            'http://localhost:%s/%s' % (port, path),
            params=request.args
        )
    except requests.exceptions.ConnectionError as e:
        resp = """
Unable to contact hound. If <https://codesearch.wmflabs.org/_health>
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
    return Response(
        text,
        r.status_code,
        headers
    )


if __name__ == '__main__':
    app.run(debug=True)
