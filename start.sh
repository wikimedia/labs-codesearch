#!/bin/bash
docker run -d -p 6080:6080 --name hound -v $(pwd):/data etsy/hound
