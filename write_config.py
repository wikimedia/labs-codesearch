#!/usr/bin/env python3
"""
Generate a hound config.json file
Copyright (C) 2017-2018 Kunal Mehta <legoktm@debian.org>

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

import argparse
import base64
from configparser import ConfigParser
import functools
import json
import os
import requests
import subprocess
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
def parse_gitmodules(url):
    r = requests.get(url)
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
        elif 'gitlab.wikimedia.org' in url:
            name = url.replace('https://gitlab.wikimedia.org/', '')
            repos.append((name, wmf_gitlab_repo(name)))
        elif 'invent.kde.org' in url:
            name = url.replace('https://invent.kde.org/', '')
            repos.append((name, generic_repo(name, host='invent.kde.org')))
        elif 'phabricator.nichework.com' in url:
            # FIXME: implement
            continue
        elif 'gitlab.wikibase.nl' in url:
            # FIXME: Implement a general gitlab handler
            # XXX: Security-wise, is it safe to do so?
            continue
        else:
            raise RuntimeError(f'Unsure how to handle URL: {url}')

    return repos


def _get_gerrit_file(gerrit_name: str, path: str) -> str:
    url = f'https://gerrit.wikimedia.org/g/{gerrit_name}/+/master/{path}?format=TEXT'
    print('Fetching ' + url)
    r = requests.get(url)
    return base64.b64decode(r.text).decode()


def _get_gitlab_file(repo_name: str, path: str, branch="master") -> str:
    url = f'https://gitlab.wikimedia.org/{repo_name}/-/raw/{branch}/{path}'
    print('Fetching ' + url)
    r = requests.get(url)
    return r.text


@functools.lru_cache()
def _settings_yaml() -> dict:
    return yaml.safe_load(_get_gitlab_file('repos/releng/release',
                                           'make-release/settings.yaml', branch='main'))


def gerrit_prefix_list(prefix: str) -> dict:
    """Generator based on Gerrit prefix search"""
    req = requests.get('https://gerrit.wikimedia.org/r/projects/', params={
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


def phab_repo(name: str) -> dict:
    return {
        'url': f'https://phabricator.wikimedia.org/source/{name}',
        'url-pattern': {
            'base-url': 'https://phabricator.wikimedia.org/source/'
                        '%s/browse/master/{path};{rev}{anchor}' % name,
            'anchor': '${line}'
        },
        'ms-between-poll': POLL,
    }


def repo_info(gerrit_name: str) -> dict:
    return {
        'url': f'https://gerrit.wikimedia.org/r/{gerrit_name}.git',
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


def gogs_repo(repo_name: str, host: str) -> dict:
    return {
        'url': f'https://{host}/{repo_name}',
        # The default in Hound uses /blob/, which does something else in Gogs.
        # The file browser in Gogs uses /src/ instead.
        # https://phabricator.wikimedia.org/T304879
        'url-pattern': {
            'base-url': '{url}/src/{rev}/{path}{anchor}',
            'anchor': '#L{line}'
        },
        'ms-between-poll': POLL,
    }


def generic_repo(repo_name: str, host: str) -> dict:
    return {
        'url': f'https://{host}/{repo_name}',
        'ms-between-poll': POLL,
    }


def gitlab_repo(gl_name: str) -> dict:
    return generic_repo(gl_name, 'gitlab.com')


def gh_repo(gh_name: str) -> dict:
    return generic_repo(gh_name, 'github.com')


def wmf_gitlab_repo(name: str) -> dict:
    return {
        'url': f'https://gitlab.wikimedia.org/{name}.git',
        'url-pattern': {
            'base-url': 'https://gitlab.wikimedia.org/%s/-/tree/{rev}/{path}{anchor}' % name,
            'anchor': '#L{line}'
        },
        'ms-between-poll': POLL,
    }


def wmf_gitlab_group_projects(group: str) -> dict:
    """Recursively list all repos within a specific group"""
    group = group.strip('/')
    repos = {}
    max_pages = 10
    next_page = 1
    while next_page and next_page < max_pages:
        resp = requests.get(
            f"https://gitlab.wikimedia.org/groups/{group}/-/children.json",
            params={'per_page': 100, "page": next_page}
        )
        resp.raise_for_status()
        if resp.headers.get('X-Next-Page'):
            next_page = int(resp.headers['X-Next-Page'])
        else:
            next_page = False
        for child in resp.json():
            child_path = child["relative_path"].lstrip("/")
            if child["type"] == "group":
                repos.update(wmf_gitlab_group_projects(group=child_path))
            elif child["type"] == "project":
                repos[child_path] = wmf_gitlab_repo(name=child_path)

    return repos


def make_conf(name, args, core=False, exts=False, skins=False, ooui=False,
              operations=False, armchairgm=False, twn=False, milkshake=False,
              bundled=False, vendor=False, wikimedia=False, pywikibot=False,
              services=False, libs=False, analytics=False, puppet=False,
              shouthow=False, schemas=False, wmcs=False, devtools=False):
    conf = {
        'max-concurrent-indexers': 2,
        'dbpath': 'data',
        'vcs-config': {
            'git': {
                'detect-ref': True
            },
        },
        'repos': {}
    }

    if core:
        conf['repos']['MediaWiki core'] = repo_info('mediawiki/core')

    if pywikibot:
        conf['repos']['Pywikibot'] = repo_info('pywikibot/core')

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
        for repo_name, info in parse_gitmodules(
                "https://raw.githubusercontent.com/MWStake/nonwmf-extensions/master/.gitmodules"
        ):
            conf['repos'][repo_name] = info

    if skins:
        for skin in data['query']['extdistrepos']['skins']:
            conf['repos']['Skin:%s' % skin] = repo_info(
                'mediawiki/skins/%s' % skin
            )

        for repo_name, info in parse_gitmodules(
                "https://raw.githubusercontent.com/MWStake/nonwmf-skins/master/.gitmodules"
        ):
            conf['repos'][repo_name] = info

    if puppet:
        conf['repos']['operations/puppet'] = repo_info('operations/puppet')
        conf['repos']['labs/private'] = repo_info('labs/private')

    if puppet or wmcs:
        conf['repos']['cloud/instance-puppet'] = repo_info('cloud/instance-puppet')
        # instance-puppet for the codfw1dev testing deployment
        conf['repos']['cloud/instance-puppet-dev'] = repo_info('cloud/instance-puppet-dev')

    if operations:
        conf['repos']['operations/dns'] = repo_info('operations/dns')
        # Special Netbox repo
        conf['repos']['netbox DNS'] = phab_repo('netbox-exported-dns')
        conf['repos']['operations/mediawiki-config'] = repo_info(
            'operations/mediawiki-config'
        )

        conf['repos']['operations/alerts'] = repo_info('operations/alerts')
        conf['repos']['operations/cookbooks'] = repo_info('operations/cookbooks')
        conf['repos']['operations/deployment-charts'] = repo_info(
            'operations/deployment-charts'
        )
        conf['repos']['operations/docker-images/production-images'] = repo_info(
            'operations/docker-images/production-images'
        )
        conf['repos']['operations/software'] = repo_info('operations/software')
        conf['repos']['operations/software/benchmw'] = repo_info(
            'operations/software/benchmw'
        )
        conf['repos']['sre/conftool'] = wmf_gitlab_repo('repos/sre/conftool')
        conf['repos']['operations/software/spicerack'] = repo_info(
            'operations/software/spicerack'
        )
        conf['repos']['operations/software/purged'] = repo_info(
            'operations/software/purged'
        )

        conf['repos']['operations/homer/public'] = repo_info(
            'operations/homer/public'
        )

        conf['repos'].update(gerrit_prefix_list('performance/'))
        conf['repos'].update(gerrit_prefix_list('mediawiki/php/'))

    if devtools:
        # Continous integration T217716, T332995
        conf['repos'].update(gerrit_prefix_list('integration/'))
        conf['repos'].update(gerrit_prefix_list('mediawiki/tools/'))

        conf['repos']['mediawiki/vagrant'] = repo_info('mediawiki/vagrant')

        conf['repos']['scap'] = wmf_gitlab_repo('repos/releng/scap')
        conf['repos']['releng/release'] = wmf_gitlab_repo('repos/releng/release')
        conf['repos']['Blubber'] = wmf_gitlab_repo('repos/releng/blubber')

        # (T354852) Important BlueSpice repos outside the extensions/ tree
        conf['repos']['BlueSpiceMWConfig'] = repo_info('bluespice/mw-config')
        conf['repos']['BlueSpiceMWConfigOverrides'] = repo_info('bluespice/mw-config/overrides')

    if armchairgm:
        conf['repos']['ArmchairGM'] = gh_repo('mary-kate/ArmchairGM')

    if twn:
        conf['repos']['translatewiki.net'] = repo_info('translatewiki')

    if bundled:
        for repo_name in bundled_repos():
            conf['repos'][repo_name] = repo_info(repo_name)

    if wikimedia:
        for repo_name in wikimedia_deployed_repos():
            conf['repos'][repo_name] = repo_info(repo_name)
        # Also mw-config (T214341)
        conf['repos']['operations/mediawiki-config'] = repo_info(
            'operations/mediawiki-config'
        )
        conf['repos']['WikimediaDebug'] = repo_info('performance/WikimediaDebug')
        conf['repos'].update(gerrit_prefix_list('mediawiki/php/'))

        conf['repos']['function-schemata'] = wmf_gitlab_repo(
            'repos/abstract-wiki/wikifunctions/function-schemata'
        )
        conf['repos']['wikilambda-cli'] = wmf_gitlab_repo(
            'repos/abstract-wiki/wikifunctions/wikilambda-cli'
        )

    if vendor:
        conf['repos']['mediawiki/vendor'] = repo_info('mediawiki/vendor')

    if services:
        conf['repos'].update(gerrit_prefix_list('mediawiki/services/'))
        conf['repos']['mwaddlink'] = repo_info('research/mwaddlink')
        conf['repos']['Wikidata Query GUI'] = repo_info('wikidata/query/gui')
        conf['repos']['New Lexeme form'] = gh_repo('wmde/new-lexeme-special-page')
        conf['repos']['Wikidata Query RDF'] = repo_info('wikidata/query/rdf')
        conf['repos']['iPoid'] = wmf_gitlab_repo('repos/mediawiki/services/ipoid')
        conf['repos']['Function Orchestrator'] = wmf_gitlab_repo(
            'repos/abstract-wiki/wikifunctions/function-orchestrator'
        )
        conf['repos']['Function Evaluator'] = wmf_gitlab_repo(
            'repos/abstract-wiki/wikifunctions/function-evaluator'
        )

    if libs:
        conf['repos'].update(gerrit_prefix_list('mediawiki/libs/'))
        conf['repos']['AhoCorasick'] = repo_info('AhoCorasick')
        conf['repos']['at-ease'] = repo_info('at-ease')
        conf['repos']['base-convert'] = repo_info('base-convert')
        conf['repos']['cdb'] = repo_info('cdb')
        conf['repos']['CLDRPluralRuleParser'] = repo_info('CLDRPluralRuleParser')
        conf['repos']['css-sanitizer'] = repo_info('css-sanitizer')
        conf['repos']['DeadlinkChecker'] = gh_repo('wikimedia/DeadlinkChecker')
        conf['repos']['HtmlFormatter'] = repo_info('HtmlFormatter')
        conf['repos']['IPSet'] = repo_info('IPSet')
        conf['repos']['jQuery Client'] = repo_info('jquery-client')
        conf['repos']['mwbot-rs'] = wmf_gitlab_repo('repos/mwbot-rs/mwbot')
        conf['repos']['oauthclient-php'] = repo_info('mediawiki/oauthclient-php')
        conf['repos']['php-session-serializer'] = repo_info('php-session-serializer')
        conf['repos']['phan-taint-check-plugin'] = \
            repo_info('mediawiki/tools/phan/SecurityCheckPlugin')
        conf['repos']['RelPath'] = repo_info('RelPath')
        conf['repos']['RunningStat'] = repo_info('RunningStat')
        conf['repos']['WrappedString'] = repo_info('WrappedString')
        conf['repos']['Purtle'] = repo_info('purtle')
        conf['repos']['testing-access-wrapper'] = repo_info('testing-access-wrapper')
        conf['repos']['TextCat'] = repo_info('wikimedia/textcat')
        conf['repos']['wvui'] = repo_info('wvui')
        conf['repos']['codex'] = repo_info('design/codex')
        conf['repos']['wikipeg'] = repo_info('wikipeg')

        # Wikibase libraries
        conf['repos']['WikibaseDataModel'] = gh_repo('wmde/WikibaseDataModel')
        conf['repos']['WikibaseDataModelSerialization'] = \
            gh_repo('wmde/WikibaseDataModelSerialization')
        conf['repos']['WikibaseDataModelServices'] = gh_repo('wmde/WikibaseDataModelServices')
        conf['repos']['WikibaseInternalSerialization'] = \
            gh_repo('wmde/WikibaseInternalSerialization')
        conf['repos']['wikibase-termbox'] = repo_info('wikibase/termbox')
        conf['repos']['wikibase-vuejs-components'] = repo_info('wikibase/vuejs-components')
        conf['repos']['WikibaseDataValuesValueView'] = repo_info('data-values/value-view')
        conf['repos']['WikibaseJavascriptAPI'] = repo_info('wikibase/javascript-api')
        conf['repos']['WikibaseDataValuesJavaScript'] = gh_repo('wmde/DataValuesJavaScript')
        conf['repos']['WikibaseSerializationJavaScript'] = \
            gh_repo('wmde/WikibaseSerializationJavaScript')
        conf['repos']['WikibaseDataModelJavaScript'] = gh_repo('wmde/WikibaseDataModelJavaScript')

    if ooui:
        conf['repos']['oojs/core'] = repo_info('oojs/core')
        conf['repos']['oojs/ui'] = repo_info('oojs/ui')
        conf['repos']['oojs/router'] = repo_info('oojs/router')

    if milkshake:
        ms_repos = ['jquery.uls', 'jquery.ime', 'jquery.webfonts', 'jquery.i18n',
                    'language-data']
        for ms_repo in ms_repos:
            conf['repos'][ms_repo] = gh_repo('wikimedia/' + ms_repo)

    if analytics:
        conf["repos"].update(gerrit_prefix_list("analytics/"))
        conf["repos"].update(wmf_gitlab_group_projects("repos/data-engineering/"))
    if schemas:
        # schemas/event/ requested in T275705
        conf['repos'].update(gerrit_prefix_list('schemas/event/'))

    if shouthow:
        conf['repos']['ShoutHow'] = gogs_repo('ashley/ShoutHow', host='git.legoktm.com')

    if wmcs:
        # toolforge infra
        conf['repos'].update(gerrit_prefix_list('operations/software/tools-'))
        conf['repos'].update(gerrit_prefix_list('cloud/toolforge/'))
        conf['repos']['operations/docker-images/toollabs-images'] = repo_info(
            'operations/docker-images/toollabs-images'
        )
        # custom horizon panels, but not upstream code
        conf['repos'].update(gerrit_prefix_list('openstack/horizon/wmf-'))

        # user repos for Toolforge, gadgets, and VPS projects.
        # including first-party tools such as:
        # - labs/tools/maintain-kubeusers
        # - labs/tools/registry-admission-webhook
        conf['repos'].update(gerrit_prefix_list('labs/tools/'))
        conf['repos'].update(gerrit_prefix_list('mediawiki/gadgets/'))
        conf['repos'].update(gerrit_prefix_list('wikipedia/gadgets/'))
        conf['repos'].update(gerrit_prefix_list('labs/codesearch'))
        # T358983
        conf['repos'].update(gerrit_prefix_list('labs/toollabs'))
        # T371992
        conf['repos'].update(wmf_gitlab_group_projects('toolforge-repos/'))

    dirname = f'hound-{name}'
    directory = os.path.join(DATA, dirname)
    if not os.path.isdir(directory):
        os.mkdir(directory)
    dest = os.path.join(directory, 'config.json')
    if os.path.exists(dest):
        with open(dest) as f:
            old = extract_urls(json.load(f))
    else:
        old = set()
    new = extract_urls(conf)
    # Write the new config always, in case names or other stuff changed
    print(f'{dirname}: writing new config')
    with open(dest, 'w') as f:
        json.dump(conf, f, indent='\t')
    if args.restart:
        if new != old:
            try:
                subprocess.check_call(['systemctl', 'status', dirname])
            except subprocess.CalledProcessError:
                print(f'{dirname}: not in systemd yet, skipping restart')
                return
            print(f'{dirname}: restarting...')
            subprocess.check_call(['systemctl', 'restart', dirname])
        else:
            print(f'{dirname}: skipping restart')


def extract_urls(conf) -> set:
    """extract a set of unique URLs from the config"""
    return {repo['url'] for repo in conf['repos'].values()}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Generate hound configuration')
    parser.add_argument('--restart', help='Restart hound instances if necessary',
                        action='store_true')
    return parser.parse_args(args=argv)


def main():
    args = parse_args()
    # "Search" profile should include everything unless there's a good reason
    make_conf('search', args,
              core=True,
              exts=True,
              skins=True,
              ooui=True,
              operations=True,
              puppet=True,
              twn=True,
              milkshake=True,
              pywikibot=True,
              services=True,
              libs=True,
              analytics=True,
              wmcs=True,
              schemas=True,
              devtools=True,
              # A dead codebase used by just one person
              armchairgm=False,
              # All of these should already be included via core/exts/skins
              bundled=False,
              # Avoiding upstream libraries; to reconsider, see T227704
              vendor=False,
              # All of these should already be included via core/exts/skins
              wikimedia=False,
              # Heavily duplicates MediaWiki core + extensions
              shouthow=False,
              )

    make_conf('core', args, core=True)
    make_conf('pywikibot', args, pywikibot=True)
    make_conf('extensions', args, exts=True)
    make_conf('skins', args, skins=True)
    make_conf('things', args, exts=True, skins=True)
    make_conf('ooui', args, ooui=True)
    make_conf('operations', args, operations=True, puppet=True)
    make_conf('armchairgm', args, armchairgm=True)
    make_conf('milkshake', args, milkshake=True)
    make_conf('bundled', args, core=True, bundled=True, vendor=True)
    make_conf('deployed', args, core=True, wikimedia=True, vendor=True, services=True, schemas=True)
    make_conf('services', args, services=True)
    make_conf('libraries', args, ooui=True, milkshake=True, libs=True)
    make_conf('analytics', args, analytics=True, schemas=True)
    make_conf('wmcs', args, wmcs=True)
    make_conf('puppet', args, puppet=True)
    make_conf('shouthow', args, shouthow=True)
    make_conf('devtools', args, devtools=True)


if __name__ == '__main__':
    main()
