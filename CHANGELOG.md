# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) with some additions:
- For all changes include one of [PATCH | MINOR | MAJOR] with the scope of the change being made.

## [Unreleased]

### Added
- [MAJOR] Initial version: `geniespec build --spec api.yaml [--output .genie]` validates an api.yaml spec and writes a python package to `<output>/python` (`pyproject.toml` and `src/<service>_api/v<major>/` with `api`, `endpoints`, `resources`, `internal` and `exceptions`), rewriting only changed files and removing files it no longer generates; `geniespec watch` rebuilds whenever the spec changes and keeps the previous output when the spec is invalid
- [MINOR] Supports resources, nested resources, standard (`LIST`, `GET`, `CREATE`, `UPDATE`, `DELETE`) and custom transitions, root transitions, exceptions, `Json` and `Mapping` types, `accessibleFrom`, request field defaults and bounds, `responseType: stream | redirect` and `source: query-parameters` request fields

### Changed

### Removed
