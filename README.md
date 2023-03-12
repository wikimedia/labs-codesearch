# MediaWiki Codesearch (powered by Hound)

We use Etsy's Hound as the backend for Codesearch. The search functionality
is great, but the UI is a bit lacking, so we work around it a bit.

## Setup

This guide is based on setting up a new instance on the Wikimedia
Cloud VPS infrastructure. Currently we use Debian Buster medium
sized images.

After creating the instance, add and mount the cinder volume.

If we're creating a fresh volume, we want to modify the filesystem
so we get some more inodes per available storage.

 sudo umount /srv
 sudo mkfs.ext4 -T news /dev/sdb
 sudo systemctl daemon-reload
 sudo mount /srv

Running `df -hi` should show an increase in available inodes. You can
proceed with actually setting up codesearch now by enabling the puppet
role: `role::codesearch`. Then, force a puppet run:
 sudo puppet agent -tv

If you get errors related to iptables and docker, reboot the instance
and they should fix themselves.

You might also need to force Hound configuration to be written by running:
 sudo systemctl start codesearch-write-config

If all that works, then `curl http://localhost:3002/` should work, and you can
point a web proxy to that port.

The hound- instances will be automatically restarted by systemd after 24
hours, which will pick up any new config changes.

## Constraints

We don't want to modify or fork Hound. Really we just want to use the upstream
docker images without modification. So we use a flask application to proxy
requests to Hound, and inject our HTML during that process.

## License

Hound is (C) 2014, Etsy, Inc. under the terms of the MIT license, see
<https://github.com/hound-search/hound/blob/master/LICENSE> for details.

Codesearch is (C) 2017-2020, Kunal Mehta under the terms of the GPL, v3 or any
later version. See COPYING for details.

The favicon is a combination of the [MediaWiki logo](https://commons.wikimedia.org/wiki/File:MediaWiki-2020-icon.svg) (CC-BY-SA 4.0) by Serhio Magpie,
and the [Git logo](https://commons.wikimedia.org/wiki/File:Git-icon-black.svg) (CC-BY 3.0) by Jason Long.
See <https://creativecommons.org/licenses/by/3.0/> for details.
