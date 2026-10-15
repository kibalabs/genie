FROM python:3.14.8-slim

RUN apt-get update && apt-get install --yes --no-install-recommends make git
COPY --from=node:24.13.0-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:24.13.0-slim /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm

WORKDIR /app
COPY makefile .

COPY pyproject.toml .
COPY uv.lock .
RUN make install-dependencies

COPY tests/typescript_client/package.json tests/typescript_client/package.json
COPY tests/typescript_client/package-lock.json tests/typescript_client/package-lock.json
RUN make install-typescript-client

COPY . .
RUN make install
