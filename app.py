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

app = Flask(__name__)

BACKENDS = {
    'search': 6080,  # all
    'extensions': 6081,
    'skins': 6082,
    'things': 6083,
}


@app.route('/')
def homepage():
    return redirect(url_for('index', backend='search'))


@app.route('/<backend>/')
def index(backend):
    if backend not in BACKENDS:
        return 'invalid backend'

    def mangle(text):
        header = '<h2 style="text-align: center;">MediaWiki code search</h2>'
        return text.replace('<body>', '<body>' + header)
    return proxy(backend, mangle=mangle)


@app.route('/<backend>/<path:path>')
def proxy(backend, path='', mangle=False):
    if backend not in BACKENDS:
        return 'invalid backend'
    port = BACKENDS[backend]
    r = requests.get(
        'http://localhost:%s/%s' % (port, path),
        params=request.args
    )
    excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
    headers = [(name, value) for (name, value) in r.raw.headers.items()
               if name.lower() not in excluded_headers]
    if mangle:
        text = mangle(r.text)
    else:
        text = r.text
    return Response(
        text,
        r.status_code,
        headers
    )


if __name__ == '__main__':
    app.run(debug=True)
