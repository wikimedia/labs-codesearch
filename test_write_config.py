"""
Copyright (C) 2020 Kunal Mehta <legoktm@member.fsf.org>

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
