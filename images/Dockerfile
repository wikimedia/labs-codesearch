FROM alpine

ENV GOPATH /go

RUN apk update \
	&& apk add go git subversion libc-dev mercurial bzr openssh \
	&& go get github.com/hound-search/hound/cmds/houndd \
	&& apk del go \
	&& rm -f /var/cache/apk/* \
	&& rm -rf /go/src /go/pkg

VOLUME ["/data"]

EXPOSE 6080

ENTRYPOINT ["/go/bin/houndd", "-conf", "/data/config.json"]
