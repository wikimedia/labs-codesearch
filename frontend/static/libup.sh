#!/bin/bash

LIB_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

BOOTSTRAP_VERION='5.1.3'
SUBDIR="$LIB_DIR/lib/bootstrap-$BOOTSTRAP_VERION"
mkdir -p "$SUBDIR"
cd "$SUBDIR"
curl -O "https://tools-static.wmflabs.org/cdnjs/ajax/libs/twitter-bootstrap/$BOOTSTRAP_VERION/css/bootstrap.min.css"
curl -O "https://tools-static.wmflabs.org/cdnjs/ajax/libs/twitter-bootstrap/$BOOTSTRAP_VERION/css/bootstrap.min.css.map"
curl -O -L "https://github.com/twbs/bootstrap/raw/v$BOOTSTRAP_VERION/LICENSE"

FUZZYSORT_VERSION="2.0.1"
SUBDIR="$LIB_DIR/lib/fuzzysort-$FUZZYSORT_VERSION"
mkdir -p "$SUBDIR"
cd "$SUBDIR"
curl -O -L "https://github.com/farzher/fuzzysort/raw/v$FUZZYSORT_VERSION/fuzzysort.js"
curl -O -L "https://github.com/farzher/fuzzysort/raw/v$FUZZYSORT_VERSION/LICENSE"

CODEX_DESIGN_TOKENS_VERSION="2.5.1"
# version matches codex_design_tokens in MediaWiki core at download time
CODEX_DESIGN_TOKENS_BASE_URL="https://gerrit.wikimedia.org/g/mediawiki/core/+/refs/heads/master/resources/lib/codex-design-tokens"
SUBDIR="$LIB_DIR/lib/codex-design-tokens-$CODEX_DESIGN_TOKENS_VERSION"
mkdir -p "$SUBDIR"
cd "$SUBDIR"
download_codex_design_token_file() {
	local file="$1"
	curl --fail -L "$CODEX_DESIGN_TOKENS_BASE_URL/$file?format=TEXT" | base64 --decode > "$file"
}
download_codex_design_token_file "theme-wikimedia-ui-root.css"
download_codex_design_token_file "theme-wikimedia-ui-mode-dark.css"
download_codex_design_token_file "LICENSE"