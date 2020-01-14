#!/bin/sh

set -e
set -u

MODE=${MODE:-start}

systemctl $MODE hound-search
systemctl $MODE hound-core
systemctl $MODE hound-extensions
systemctl $MODE hound-skins
systemctl $MODE hound-things
systemctl $MODE hound-ooui
systemctl $MODE hound-operations
systemctl $MODE hound-armchairgm
systemctl $MODE hound-milkshake
systemctl $MODE hound-bundled
systemctl $MODE hound-deployed
systemctl $MODE hound-pywikibot
systemctl $MODE hound-services
