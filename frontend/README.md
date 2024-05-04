## codesearch-frontend

### Local development

If it's the first time you're running the frontend, install the dependencies:

```console
composer update
```

Start the development server:
```console
composer serve
```

Open <http://localhost:4000>.

### "Production" mode

```console
docker build . -t codesearch-frontend \
&& docker run -it --rm -p 3003:80 codesearch-frontend
```

Open <http://localhost:3003>.

**Tip:** Set `CODESEARCH_HOUND_BASE` to access codesearch-backend directly
through a local address, without intermediary CDN throttling.
