# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) with some additions:
- For all changes include one of [PATCH | MINOR | MAJOR] with the scope of the change being made.

## [Unreleased]

### Added
- [MAJOR] Initial version: `geniespec build --spec api.yaml --target python-server [--output .]` validates an api.yaml spec and writes the target's package into the output directory (for `python-server`, `<service>_api/v<major>/` with `api`, `endpoints`, `resources`, `internal` and `exceptions`), only touching that package: changed files are rewritten and files it no longer generates are removed
- [MINOR] Added `geniespec watch`, which rebuilds whenever the spec changes (keeping the previous output when the spec is invalid); given a command after `--` it runs it after the first build, exits with its exit code and stops it when watch is stopped
- [MINOR] Supports resources, nested resources, standard (`LIST`, `GET`, `CREATE`, `UPDATE`, `DELETE`) and custom transitions, root transitions, exceptions, `Json` and `Mapping` types, `accessibleFrom`, request field defaults and bounds, `responseType: stream | redirect` and `source: query-parameters` request fields

### Changed

### Removed
