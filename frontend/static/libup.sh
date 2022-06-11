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
