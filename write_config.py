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

import base64
from configparser import ConfigParser
import functools
import json
import os
import requests
import yaml

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


@functools.lru_cache()
def mwstake_extensions():
    r = requests.get(
        'https://raw.githubusercontent.com/MWStake/nonwmf-extensions/master/.gitmodules'
    )
    r.raise_for_status()
    config = ConfigParser()
    config.read_string(r.text)
    repos = []
    for section in config.sections():
        # TODO: Use a proper URL parser instead of string manipulation
        url = config[section]['url']
        if url.endswith('.git'):
            url = url[:-4]
        if 'github.com' in url:
            name = url.replace('git@github.com:', '').replace('https://github.com/', '')
            repos.append((name, gh_repo(name)))
        elif 'bitbucket.org' in url:
            name = url.replace('https://bitbucket.org/', '')
            repos.append((name, bitbucket_repo(name)))
        elif 'gitlab.com' in url:
            name = url.replace('https://gitlab.com/', '')
            repos.append((name, gitlab_repo(name)))
        else:
            raise RuntimeError('Unsure how to handle URL: %s' % url)

    return repos


def _get_gerrit_file(gerrit_name, path):
    url = 'https://gerrit.wikimedia.org/g/{}/+/master/{}?format=TEXT'.format(gerrit_name, path)
    print('Fetching ' + url)
    r = requests.get(url)
    return base64.b64decode(r.text).decode()


@functools.lru_cache()
def bundled_repos():
    config = yaml.safe_load(_get_gerrit_file(
        'mediawiki/tools/release', 'make-release/settings.yaml'))
    return ['mediawiki/' + name for name in config['bundles']['base']]


@functools.lru_cache()
def wikimedia_deployed_repos():
    conf = json.loads(_get_gerrit_file(
        'mediawiki/tools/release', 'make-wmf-branch/config.json'))

    # Intentionally ignore special_extensions because they're special
    return ['mediawiki/' + name for name in conf['extensions']]


def phab_repo(callsign):
    return {
        'url': 'https://phabricator.wikimedia.org/diffusion/' + callsign,
        'url-pattern': {
            'base-url': 'https://phabricator.wikimedia.org/diffusion/'
                        '%s/browse/{rev}/{path}{anchor}' % callsign,
            'anchor': '${line}'
        },
        'ms-between-poll': POLL,
    }


def repo_info(gerrit_name):
    return {
        'url': 'https://gerrit.wikimedia.org/r/' + gerrit_name,
        'url-pattern': {
            'base-url': 'https://gerrit.wikimedia.org/g/' +
                        '%s/+/{rev}/{path}{anchor}' % gerrit_name,
            'anchor': '#{line}'
        },
        'ms-between-poll': POLL,
    }


def bitbucket_repo(bb_name):
    return {
        'url': 'https://bitbucket.org/%s.git' % bb_name,
        'url-pattern': {
            'base-url': 'https://bitbucket.org/%s/src/{rev}/{path}' % bb_name,
            # The anchor syntax used by bitbucket is too complicated for hound to
            # be able to generate. It's `#basename({path})-{line}`.
            'anchor': ''
        },
        'ms-between-poll': POLL,
    }


def gitlab_repo(gl_name):
    # Lazy/avoid duplication
    return gh_repo(gl_name, host='gitlab.com')


def gh_repo(gh_name, host='github.com'):
    return {
        'url': 'https://%s/%s' % (host, gh_name),
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
              operations=False, armchairgm=False, twn=False, milkshake=False,
              bundled=False, vendor=False, wikimedia=False, pywikibot=False):
    conf = {
        'max-concurrent-indexers': 2,
        'dbpath': 'data',
        'repos': {}
    }

    if core:
        conf['repos']['MediaWiki core'] = repo_info('mediawiki/core')

    if pywikibot:
        conf['repos']['Pywikibot'] = repo_info('pywikibot/core')

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
        for repo_name, info in mwstake_extensions():
            conf['repos'][repo_name] = info

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

    if bundled:
        for repo_name in bundled_repos():
            conf['repos'][repo_name] = repo_info(repo_name)

    if wikimedia:
        for repo_name in wikimedia_deployed_repos():
            conf['repos'][repo_name] = repo_info(repo_name)

    if vendor:
        conf['repos']['mediawiki/vendor'] = repo_info('mediawiki/vendor')

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
              operations=True, twn=True, pywikibot=True)
    make_conf('core', core=True)
    make_conf('pywikibot', pywikibot=True)
    make_conf('extensions', exts=True)
    make_conf('skins', skins=True)
    make_conf('things', exts=True, skins=True)
    make_conf('ooui', ooui=True)
    make_conf('operations', operations=True)
    make_conf('armchairgm', armchairgm=True)
    make_conf('milkshake', milkshake=True)
    make_conf('bundled', core=True, bundled=True, vendor=True)
    make_conf('deployed', core=True, wikimedia=True, vendor=True)


if __name__ == '__main__':
    main()
