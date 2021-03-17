## frontend

Built using [seed](https://seed-rs.org/).

### Local development

* Install rust using [rustup](https://rustup.rs/)
* `cargo install cargo-make`
* In a background window, run `cargo make serve`
  * Sets up a webserver in the background to run on `localhost:8000`
* In your primary window, run `cargo make watch`
  * Builds the project and rebuilds whenever a change is detected.
  
If you want to test with a release optimized version locally, run `cargo make build_release`.

### "Production" mode

* `docker build . -t codesearch-frontend`
* `docker run -it --rm -p 3003:80 codesearch-frontend`
