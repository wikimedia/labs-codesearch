FROM rust AS builder

RUN rustup target add wasm32-unknown-unknown && cargo install wasm-pack
COPY Cargo.toml .
COPY src/ src/
RUN wasm-pack build --target web --out-name package

FROM nginx:latest

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /srv/
COPY static/ /srv/static/
COPY --from=builder pkg/ /srv/pkg/
