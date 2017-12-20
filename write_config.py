#!/usr/bin/env python3
"""
Generate a hound config.json file
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

import json
import requests

BASE = {
    'max-concurrent-indexers': 2,
    'dbpath': 'data',
    'repos': {
        'MediaWiki core': {
            'url': 'https://gerrit.wikimedia.org/r/mediawiki/core'
        }
    }
}


r = requests.get(
    'https://www.mediawiki.org/w/api.php',
    params={
        "action": "query",
        "format": "json",
        'formatversion': 2,
        "list": "extdistrepos"
    }
)
r.raise_for_status()

data = r.json()
for ext in data['query']['extdistrepos']['extensions']:
    BASE['repos']['Extension:%s' % ext] = {
        'url': 'https://gerrit.wikimedia.org/r/mediawiki/extensions/%s' % ext
    }

for skin in data['query']['extdistrepos']['skins']:
    BASE['repos']['Skin:%s' % skin] = {
        'url': 'https://gerrit.wikimedia.org/r/mediawiki/skins/%s' % skin
    }

with open('config.json', 'w') as f:
    json.dump(BASE, f, indent='\t')
