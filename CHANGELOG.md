# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) with some additions:
- For all changes include one of [PATCH | MINOR | MAJOR] with the scope of the change being made.

## [Unreleased]

### Added
- [MINOR] Added rate limits: a top-level `rateLimits` list (`name`, any of `perMinute`, `perFiveMinutes`, `perHour` and `perDay`, and `keyBy: user | ip`), a `defaultRateLimit`, and `rateLimit` on transitions (`none` turns the default off). Transitions using a user-keyed limit must have authentication. `python-server` writes each one as a `RATE_LIMIT_<NAME>` `RateLimitConfig` and passes it to kiba-core's `route`, which rejects requests over the limit with a 429
- [MINOR] Added the `Uuid` type: a string that must be a valid UUID, usable anywhere `String` is (including primary attributes in paths). `python-server` types it as `uuid.UUID`, so requests with other strings get a 400 and responses use the lowercase hyphenated form; `typescript-client` types it as `string`
- [MINOR] Added API docs fields: `operationId`, `summary`, `description`, `tags` and `extensions` on transitions, and `description` on attributes, request fields and response fields. `python-server` passes the transition fields to kiba-core's `route` (so kiba-core's OpenAPI generator documents routes with an `operationId`) and writes field descriptions as pydantic `Field(description=...)`. Duplicate `operationId`s are rejected
- [MINOR] Added resource `overrides` for moving an existing API to genie: `shouldPrefixParentName: false` names a child resource without its parent's name (so `Agent` under `User` keeps an `agent-id` primary attribute)
- [MINOR] Added the `BigInt` type: an integer of any size sent as a JSON string. `python-server` types it as `int` (a `BigInt` alias in `resources` that serializes to a string and is documented as one); `typescript-client` types it as `bigint`
- [MINOR] Added transition `overrides.responseFieldName`, which renames the response field of a `GET`, `LIST`, `CREATE` or `UPDATE` transition

### Changed
- [MINOR] `defaultAuthentication` and `authentication` policy names can contain underscores (e.g. `resource_owner`)
- [PATCH] Generated `python-server` and `typescript-client` modules only import what they use (for example `datetime`, `collections.abc`, `uuid`, `resources` and kiba-core's `RawObject`), and the `typescript-client` index only re-exports `endpoints` when it has classes

### Removed

## [0.1.1] - 2026-10-22

### Added
- [MAJOR] Initial version: `geniespec build --spec api.yaml --target python-server [--output .]` validates an api.yaml spec and writes the target's package into the output directory (for `python-server`, `<service>_api/v<major>/` with `api`, `endpoints`, `resources`, `internal` and `exceptions`), only touching that package: changed files are rewritten and files it no longer generates are removed
- [MINOR] Added `geniespec watch`, which rebuilds whenever the spec changes (keeping the previous output when the spec is invalid); given a command after `--` it runs it after the first build, exits with its exit code and stops it when watch is stopped
- [MINOR] Supports resources, nested resources, standard (`LIST`, `GET`, `CREATE`, `UPDATE`, `DELETE`) and custom transitions, root transitions, exceptions, `Json` and `Mapping` types, `accessibleFrom`, request field defaults and bounds, `responseType: stream | redirect` and `source: query-parameters` request fields
- [MINOR] Added the `typescript-client` target, which writes a `@kibalabs/core` `ServiceClient` with typed resources and request params, parses dates, mappings and nested resources, keeps `null` apart from left-out fields on updates and streams items to a callback
- [MINOR] Added enums: a top-level `enums` list (`name` and `values`) whose names can be used as types, and inline `type: Enum` with `enumValues` on attributes, request fields and response fields (including as a `List` value type). `python-server` generates `typing.Literal` types (named enums as `<Name>V<major>` aliases in `resources`), so requests with other values are rejected; `typescript-client` generates string literal unions (named enums as exported `<Name>V<major>` types)
- [MINOR] Added `type: File` request fields on POST transitions. `python-server` passes them to internal methods as kiba-core's `UploadedFile` (needs kiba-core 0.5.3.dev87 or later, which parses multipart bodies); `typescript-client` sends the request as a multipart form. Other fields of a transition with File fields must be single primitive or enum values
- [MINOR] Added oneOfs: a top-level `oneOfs` list (`name`, `discriminator` and member resource `types`) whose names can be used as types. Each member needs the discriminator attribute as a non-nullable single-value enum. `python-server` generates pydantic discriminated unions; `typescript-client` generates union types and a `<name>V<major>FromObject` function that picks the member class by the discriminator

### Changed
- [MINOR] Generated `python-server` internal methods take their parameters as keyword-only, so type checkers reject implementations that rename a parameter instead of failing at runtime

### Removed
