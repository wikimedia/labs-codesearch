#!/bin/sh

set -eu

MODE=${MODE:-start}

# Match "profile::codesearch::ports" in operations/puppet:/hiera/codesearch/common.yaml
systemctl $MODE hound-search
systemctl $MODE hound-search
systemctl $MODE hound-extensions
systemctl $MODE hound-skins
systemctl $MODE hound-things
systemctl $MODE hound-core
systemctl $MODE hound-ooui
systemctl $MODE hound-operations
systemctl $MODE hound-armchairgm
systemctl $MODE hound-milkshake
systemctl $MODE hound-bundled
systemctl $MODE hound-deployed
systemctl $MODE hound-pywikibot
systemctl $MODE hound-services
systemctl $MODE hound-libraries
systemctl $MODE hound-analytics
systemctl $MODE hound-puppet
systemctl $MODE hound-shouthow
systemctl $MODE hound-wmcs
systemctl $MODE hound-devtools
systemctl $MODE hound-apps
