"""
Copyright (C) 2020 Kunal Mehta <legoktm@debian.org>

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
import write_config


def test_gerrit_prefix_list():
    d = {}
    d.update(write_config.gerrit_prefix_list('mediawiki/libs/'))
    # Test one example repo
    assert 'mediawiki/libs/alea' in d
    assert d['mediawiki/libs/alea']['url'] ==\
           'https://gerrit-replica.wikimedia.org/r/mediawiki/libs/alea.git'


def test_parse_args():
    assert write_config.parse_args([]).restart is False
    assert write_config.parse_args(['--restart']).restart is True


def test_repo_info_gitlab():
    assert write_config.wmf_gitlab_repo('repos/releng/scap')['url'] == \
        'https://gitlab.wikimedia.org/repos/releng/scap.git'
    assert write_config.wmf_gitlab_repo('repos/releng/scap')['url-pattern']['anchor'] == '#L{line}'
    assert write_config.wmf_gitlab_repo('repos/releng/scap')['url-pattern']['base-url'] == \
        'https://gitlab.wikimedia.org/repos/releng/scap/-/tree/{rev}/{path}{anchor}'


def test_repo_info_gerrit():
    assert write_config.repo_info('operations/alerts')['url'] == \
        'https://gerrit-replica.wikimedia.org/r/operations/alerts.git'
    assert write_config.repo_info('operations/alerts')['url-pattern']['anchor'] == '#{line}'
    assert write_config.repo_info('operations/alerts')['url-pattern']['base-url'] == \
        'https://gerrit.wikimedia.org/g/operations/alerts/+/{rev}/{path}{anchor}'


def test_repo_info_github():
    assert write_config.gh_repo('wmde/WikibaseDataModel')['url'] == \
        'https://github.com/wmde/WikibaseDataModel'


def test_repo_info_gogs():
    assert write_config.gogs_repo('ashley/ShoutHow', host='git.legoktm.com')['url'] == \
        'https://git.legoktm.com/ashley/ShoutHow'


def test_repo_info_generic():
    assert write_config.generic_repo('ashley/ShoutHow', host='git.legoktm.com')['url'] == \
        'https://git.legoktm.com/ashley/ShoutHow'


def test_wmf_gitlab_group_projects():
    assert "toolforge-repos/zoomviewer" in \
        write_config.wmf_gitlab_group_projects("toolforge-repos/")
