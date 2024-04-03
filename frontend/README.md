## codesearch-frontend

### Local development

```
composer serve
```

Open <http://localhost:4000>

### "Production" mode

```
docker build . -t codesearch-frontend \
&& docker run -it --rm -p 3003:80 codesearch-frontend
```

Open <http://localhost:3003>

Set CODESEARCH_HOUND_BASE to access codesearch-backend directly
through a local address, without intermediary CDN throttling.
