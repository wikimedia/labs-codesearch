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

import functools
import json
import os
import requests

# One hour
POLL = 60 * 60 * 1000
DATA = '/srv/hound'


@functools.lru_cache()
def get_extdist_repos():
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

    return r.json()


def repo_info(gerrit_name):
    return {
        'url': 'https://gerrit.wikimedia.org/r/' + gerrit_name,
        'url-pattern': {
            'base-url': 'https://phabricator.wikimedia.org/' +
                        'r/p/%s;browse/master/{path}' % gerrit_name
        },
        'ms-between-poll': POLL,
    }


def make_conf(directory, core=True, exts=True, skins=True):
    conf = {
        'max-concurrent-indexers': 2,
        'dbpath': 'data',
        'repos': {}
    }

    if core:
        conf['repos']['MediaWiki core'] = repo_info('mediawiki/core')

    data = get_extdist_repos()
    if exts:
        for ext in data['query']['extdistrepos']['extensions']:
            conf['repos']['Extension:%s' % ext] = repo_info(
                'mediawiki/extensions/%s' % ext
            )

    if skins:
        for skin in data['query']['extdistrepos']['skins']:
            conf['repos']['Skin:%s' % skin] = repo_info(
                'mediawiki/skins/%s' % skin
            )

    directory = os.path.join(DATA, directory)
    if not os.path.isdir(directory):
        os.mkdir(directory)
    with open(os.path.join(directory, 'config.json'), 'w') as f:
        json.dump(conf, f, indent='\t')


def main():
    make_conf('hound-search')
    make_conf('hound-core', exts=False, skins=False)
    make_conf('hound-extensions', core=False, skins=False)
    make_conf('hound-skins', core=False, exts=False)
    make_conf('hound-things', core=False)


if __name__ == '__main__':
    main()
