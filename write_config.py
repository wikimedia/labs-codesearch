#!/usr/bin/env python3
"""
Generate a hound config.json file
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

import functools
import json
import os
import requests

from ports import PORTS

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


def phab_repo(callsign):
    return {
        'url': 'https://phabricator.wikimedia.org/diffusion/' + callsign,
        'url-pattern': {
            'base-url': 'https://phabricator.wikimedia.org/diffusion/'
                        '%s/browse/master/{path}{anchor}' % callsign,
            'anchor': '${line}'
        },
        'ms-between-poll': POLL,
    }


def repo_info(gerrit_name):
    return {
        'url': 'https://gerrit.wikimedia.org/r/' + gerrit_name,
        'url-pattern': {
            'base-url': 'https://gerrit.wikimedia.org/g/' +
                        '%s/+/master/{path}{anchor}' % gerrit_name,
            'anchor': '#{line}'
        },
        'ms-between-poll': POLL,
    }


def gh_repo(gh_name):
    return {
        'url': 'https://github.com/' + gh_name,
        'ms-between-poll': POLL,
    }


def generate_service(name):
    # Leave whitespace at the top so it's easy to read, lstrip() at the bottom
    return """
[Unit]
Description={name}
After=docker.service
Requires=docker.service

[Service]
TimeoutStartSec=0
ExecStartPre=-/usr/bin/docker kill {name}
ExecStartPre=-/usr/bin/docker rm -f {name}
ExecStartPre=/usr/bin/docker pull etsy/hound
ExecStart=/usr/bin/docker run -p {port}:6080 --name {name} -v /srv/hound/{name}:/data etsy/hound
ExecStop=/usr/bin/docker stop {name}

[Install]
WantedBy=multi-user.target
""".format(name='hound-' + name, port=PORTS[name]).lstrip()


def make_conf(name, core=False, exts=False, skins=False, ooui=False,
              operations=False, armchairgm=False, twn=False, milkshake=False):
    conf = {
        'max-concurrent-indexers': 2,
        'dbpath': 'data',
        'repos': {}
    }

    if core:
        conf['repos']['MediaWiki core'] = repo_info('mediawiki/core')

    if ooui:
        conf['repos']['OOUI'] = repo_info('oojs/ui')

    data = get_extdist_repos()
    if exts:
        for ext in data['query']['extdistrepos']['extensions']:
            conf['repos']['Extension:%s' % ext] = repo_info(
                'mediawiki/extensions/%s' % ext
            )
        conf['repos']['VisualEditor core'] = repo_info(
            'VisualEditor/VisualEditor'
        )

    if skins:
        for skin in data['query']['extdistrepos']['skins']:
            conf['repos']['Skin:%s' % skin] = repo_info(
                'mediawiki/skins/%s' % skin
            )

    if operations:
        conf['repos']['Wikimedia DNS'] = repo_info(
            'operations/dns'
        )
        conf['repos']['Wikimedia MediaWiki config'] = repo_info(
            'operations/mediawiki-config'
        )
        # TODO: Add puppet once non-master branches are supported

    if armchairgm:
        conf['repos']['ArmchairGM'] = phab_repo('AMGM')

    if twn:
        conf['repos']['translatewiki.net'] = repo_info('translatewiki')

    if milkshake:
        ms_repos = ['jquery.uls', 'jquery.ime', 'jquery.webfonts', 'jquery.i18n',
                    'language-data']
        for ms_repo in ms_repos:
            conf['repos'][ms_repo] = gh_repo('wikimedia/' + ms_repo)

    dirname = 'hound-' + name
    directory = os.path.join(DATA, dirname)
    if not os.path.isdir(directory):
        os.mkdir(directory)
    with open(os.path.join(directory, 'config.json'), 'w') as f:
        json.dump(conf, f, indent='\t')
    with open(os.path.join(os.path.dirname(__file__), dirname + '.service'), 'w') as f:
        f.write(generate_service(name))


def main():
    make_conf('search', core=True, exts=True, skins=True, ooui=True,
              operations=True, twn=True)
    make_conf('core', core=True)
    make_conf('extensions', exts=True)
    make_conf('skins', skins=True)
    make_conf('things', exts=True, skins=True)
    make_conf('ooui', ooui=True)
    make_conf('operations', operations=True)
    make_conf('armchairgm', armchairgm=True)
    make_conf('milkshake', milkshake=True)


if __name__ == '__main__':
    main()
