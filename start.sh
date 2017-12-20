#!/bin/bash
docker run -d -p 6080:6080 --name hound-search -v /srv/codesearch/search:/data etsy/hound
docker run -d -p 6081:6080 --name hound-extensions -v /srv/codesearch/extensions:/data etsy/hound
docker run -d -p 6082:6080 --name hound-skins -v /srv/codesearch/skins:/data etsy/hound
docker run -d -p 6083:6080 --name hound-things -v /srv/codesearch/things:/data etsy/hound
