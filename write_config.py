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
from typing import List
import yaml

# 90 minutes
POLL = 90 * 60 * 1000
DATA = '/srv/hound'


@functools.lru_cache()
def get_extdist_repos() -> dict:
    r = requests.get(
        'https://www.mediawiki.org/w/api.php',
        params={
            "action": "query",
            "format": "json",
            'formatversion': "2",
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
        elif 'phabricator.nichework.com' in url:
            # FIXME: implement
            continue
        else:
            raise RuntimeError(f'Unsure how to handle URL: {url}')

    return repos


def _get_gerrit_file(gerrit_name: str, path: str) -> str:
    url = f'https://gerrit.wikimedia.org/g/{gerrit_name}/+/master/{path}?format=TEXT'
    print('Fetching ' + url)
    r = requests.get(url)
    return base64.b64decode(r.text).decode()


@functools.lru_cache()
def _settings_yaml() -> dict:
    return yaml.safe_load(_get_gerrit_file('mediawiki/tools/release',
                                           'make-release/settings.yaml'))


def gerrit_prefix_list(prefix: str) -> dict:
    """Generator based on Gerrit prefix search"""
    req = requests.get('https://gerrit.wikimedia.org/r/projects/', params={
        'b': 'master',
        'p': prefix,
    })
    req.raise_for_status()
    data = json.loads(req.text[4:])
    repos = {}
    for repo in data:
        info = data[repo]
        if info['state'] != 'ACTIVE':
            continue
        repos[repo] = repo_info(repo)

    return repos


def bundled_repos() -> List[str]:
    return [name for name in _settings_yaml()['bundles']['base']]


def wikimedia_deployed_repos() -> List[str]:
    return [name for name in _settings_yaml()['bundles']['wmf_core']]


def phab_repo(callsign: str) -> dict:
    return {
        'url': f'https://phabricator.wikimedia.org/diffusion/{callsign}',
        'url-pattern': {
            'base-url': 'https://phabricator.wikimedia.org/diffusion/'
                        '%s/browse/{rev}/{path}{anchor}' % callsign,
            'anchor': '${line}'
        },
        'ms-between-poll': POLL,
    }


def repo_info(gerrit_name: str) -> dict:
    return {
        'url': f'https://gerrit-replica.wikimedia.org/r/{gerrit_name}.git',
        'url-pattern': {
            'base-url': 'https://gerrit.wikimedia.org/g/' +
                        '%s/+/{rev}/{path}{anchor}' % gerrit_name,
            'anchor': '#{line}'
        },
        'ms-between-poll': POLL,
    }


def bitbucket_repo(bb_name: str) -> dict:
    return {
        'url': f'https://bitbucket.org/{bb_name}.git',
        'url-pattern': {
            'base-url': 'https://bitbucket.org/%s/src/{rev}/{path}' % bb_name,
            # The anchor syntax used by bitbucket is too complicated for hound to
            # be able to generate. It's `#basename({path})-{line}`.
            'anchor': ''
        },
        'ms-between-poll': POLL,
    }


def gitlab_repo(gl_name: str) -> dict:
    # Lazy/avoid duplication
    return gh_repo(gl_name, host='gitlab.com')


def gh_repo(gh_name: str, host: str = 'github.com') -> dict:
    return {
        'url': f'https://{host}/{gh_name}',
        'ms-between-poll': POLL,
    }


def make_conf(name, core=False, exts=False, skins=False, ooui=False,
              operations=False, armchairgm=False, twn=False, milkshake=False,
              bundled=False, vendor=False, wikimedia=False, pywikibot=False,
              services=False, libs=False):
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
        # Sanity check (T223771)
        if not data['query']['extdistrepos']['extensions']:
            raise RuntimeError('Why are there no Gerrit extensions?')
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
        conf['repos']['Wikimedia conftool'] = repo_info(
            'operations/software/conftool'
        )
        # CI config T217716
        conf['repos']['Wikimedia continuous integration config'] = repo_info(
            'integration/config'
        )
        # puppet is very special because of the non-master branch
        puppet = repo_info('operations/puppet')
        puppet['url'] = 'file:///operations/puppet'
        conf['repos']['Wikimedia Puppet'] = puppet

    if armchairgm:
        conf['repos']['ArmchairGM'] = gh_repo('mary-kate/ArmchairGM')

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
        # Also mw-config (T214341)
        conf['repos']['Wikimedia MediaWiki config'] = repo_info(
            'operations/mediawiki-config'
        )

    if vendor:
        conf['repos']['mediawiki/vendor'] = repo_info('mediawiki/vendor')

    if services:
        conf['repos']['Parsoid service'] = repo_info('mediawiki/services/parsoid')
        conf['repos']['Mobile apps'] = repo_info('mediawiki/services/mobileapps')
        conf['repos']['EventStreams'] = repo_info('mediawiki/services/eventstreams')
        conf['repos']['PoolCounter'] = repo_info('mediawiki/services/poolcounter')
        conf['repos']['CX server'] = repo_info('mediawiki/services/cxserver')
        conf['repos']['Kask'] = repo_info('mediawiki/services/kask')

    if libs:
        conf['repos'].update(gerrit_prefix_list('mediawiki/libs/'))
        conf['repos']['AhoCorasick'] = repo_info('AhoCorasick')
        conf['repos']['cdb'] = repo_info('cdb')
        conf['repos']['CLDRPluralRuleParser'] = repo_info('CLDRPluralRuleParser')
        conf['repos']['HtmlFormatter'] = repo_info('HtmlFormatter')
        conf['repos']['IPSet'] = repo_info('IPSet')
        conf['repos']['RelPath'] = repo_info('RelPath')
        conf['repos']['RunningStat'] = repo_info('RunningStat')
        conf['repos']['WrappedString'] = repo_info('WrappedString')

        conf['repos']['WikibaseDataModel'] = gh_repo('wmde/WikibaseDataModel')
        conf['repos']['WikibaseDataModelSerialization'] = \
            gh_repo('wmde/WikibaseDataModelSerialization')
        conf['repos']['WikibaseDataModelServices'] = gh_repo('wmde/WikibaseDataModelServices')
        conf['repos']['WikibaseInternalSerialization'] = \
            gh_repo('wmde/WikibaseInternalSerialization')
        conf['repos']['wikibase-termbox'] = repo_info('wikibase/termbox')
        conf['repos']['wikibase-vuejs-components'] = repo_info('wikibase/vuejs-components')

    dirname = f'hound-{name}'
    directory = os.path.join(DATA, dirname)
    if not os.path.isdir(directory):
        os.mkdir(directory)
    with open(os.path.join(directory, 'config.json'), 'w') as f:
        json.dump(conf, f, indent='\t')


def main():
    # "Search" profile should include everything unless there's a good reason
    make_conf('search',
              core=True,
              exts=True,
              skins=True,
              ooui=True,
              operations=True,
              # A dead codebase used by just one person
              armchairgm=False,
              twn=True,
              # FIXME: Justify
              milkshake=False,
              # All of these should already be included via core/exts/skins
              bundled=False,
              # Avoiding upstream libraries; to reconsider, see T227704
              vendor=False,
              # All of these should already be included via core/exts/skins
              wikimedia=False,
              pywikibot=True,
              services=True,
              libs=True)

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
    make_conf('deployed', core=True, wikimedia=True, vendor=True, services=True)
    make_conf('services', services=True)
    make_conf('libraries', ooui=True, milkshake=True, libs=True)


if __name__ == '__main__':
    main()
