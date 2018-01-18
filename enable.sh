#!/bin/bash
# Keep in sync with start.sh
systemctl enable hound-search
systemctl enable hound-core
systemctl enable hound-extensions
systemctl enable hound-skins
systemctl enable hound-things
systemctl enable hound_proxy
