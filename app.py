#!/usr/bin/env python3
"""
Proxy requests to hound
Copyright (C) 2017 Kunal Mehta <legoktm@member.fsf.org>

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

from flask import Flask, Response, request, redirect, url_for

import requests
import traceback

app = Flask(__name__)

BACKENDS = {
    'search': 6080,  # all
    'extensions': 6081,
    'skins': 6082,
    'things': 6083,
    'core': 6084,
}


def index_url(target, text, current):
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


@app.route('/<backend>/')
def index(backend):
    if backend not in BACKENDS:
        return 'invalid backend'
    header = """
<div style="text-align: center;">
<h2>MediaWiki code search</h2>

{search} ·
{core} ·
{ext} ·
{skins} ·
{things}
</div>
""".format(
        search=index_url('search', 'Everything', backend),
        core=index_url('core', 'MediaWiki core', backend),
        ext=index_url('extensions', 'Extensions', backend),
        skins=index_url('skins', 'Skins', backend),
        things=index_url('things', 'Extensions & skins', backend)
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

    def mangle(text):
        text = text.replace('<body>', '<body>' + header)
        text = text.replace('</body>', footer + '</body>')
        text = text.replace('<title>Hound</title>', title)
        return text
    return proxy(backend, mangle=mangle)


@app.route('/<backend>/<path:path>')
def proxy(backend, path='', mangle=False):
    if backend not in BACKENDS:
        return 'invalid backend'
    port = BACKENDS[backend]
    try:
        r = requests.get(
            'http://localhost:%s/%s' % (port, path),
            params=request.args
        )
    except requests.exceptions.ConnectionError as e:
        resp = """
Unable to contact hound. Please retry in a few minutes.
If this error continues, please report it in Phabricator
with the following information:

"""
        resp += traceback.format_exc()
        return Response(resp, 503, mimetype='text/plain')
    excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
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
