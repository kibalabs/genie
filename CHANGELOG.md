# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) with some additions:
- For all changes include one of [PATCH | MINOR | MAJOR] with the scope of the change being made.

## [Unreleased]

### Added
- [MAJOR] Initial version: `geniespec build --spec api.yaml --target python-server [--output .]` validates an api.yaml spec and writes the target's package into the output directory (for `python-server`, `<service>_api/v<major>/` with `api`, `endpoints`, `resources`, `internal` and `exceptions`), only touching that package: changed files are rewritten and files it no longer generates are removed
- [MINOR] Added `geniespec watch`, which rebuilds whenever the spec changes (keeping the previous output when the spec is invalid); given a command after `--` it runs it after the first build, exits with its exit code and stops it when watch is stopped
- [MINOR] Supports resources, nested resources, standard (`LIST`, `GET`, `CREATE`, `UPDATE`, `DELETE`) and custom transitions, root transitions, exceptions, `Json` and `Mapping` types, `accessibleFrom`, request field defaults and bounds, `responseType: stream | redirect` and `source: query-parameters` request fields
- [MINOR] Added the `typescript-client` target, which writes a `@kibalabs/core` `ServiceClient` with typed resources and request params, parses dates, mappings and nested resources, keeps `null` apart from left-out fields on updates and streams items to a callback
- [MINOR] Added enums: a top-level `enums` list (`name` and `values`) whose names can be used as types, and inline `type: Enum` with `enumValues` on attributes, request fields and response fields (including as a `List` value type). `python-server` generates `typing.Literal` types (named enums as `<Name>V<major>` aliases in `resources`), so requests with other values are rejected; `typescript-client` generates string literal unions (named enums as exported `<Name>V<major>` types)
- [MINOR] Added `type: File` request fields on POST transitions. `python-server` passes them to internal methods as kiba-core's `UploadedFile` (needs kiba-core 0.5.3.dev87 or later, which parses multipart bodies); `typescript-client` sends the request as a multipart form. Other fields of a transition with File fields must be single primitive or enum values

### Changed
- [MINOR] Generated `python-server` internal methods take their parameters as keyword-only, so type checkers reject implementations that rename a parameter instead of failing at runtime

### Removed
