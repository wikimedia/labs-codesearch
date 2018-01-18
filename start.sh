#!/bin/bash
# Keep in sync with enable.sh
systemctl start hound-search
systemctl start hound-core
systemctl start hound-extensions
systemctl start hound-skins
systemctl start hound-things
systemctl start hound_proxy
