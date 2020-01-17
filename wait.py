#!/usr/bin/env python3
"""
Waits until no hound instances are starting up
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

import os
import random
import requests
import time


def main():
    """Wait until no hound instances are starting up"""
    wait = True
    while wait:
        req = requests.get('http://localhost:3002/_health.json')
        req.raise_for_status()
        health = req.json()
        wait_for = [name for name in health if health[name] == 'starting up']
        if wait_for:
            wait = True
            print('{}: Sleeping while waiting for {}'.format(
                os.environ.get('HOUND_NAME', 'unknown'),
                ', '.join(wait_for))
            )
            # Random skew so all the waits hopefully
            # don't give up at the same time
            time.sleep(random.randint(5, 20))


if __name__ == '__main__':
    main()
