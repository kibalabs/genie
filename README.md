# Genie

Genie (`geniespec` on PyPI) generates API code from an `api.yaml` spec. Install it like any other tool and run it from your build scripts; the generated code is gitignored, not committed.

```
geniespec build --spec api.yaml --target <python-server | typescript-client> [--output .]
geniespec watch --spec api.yaml --target <python-server | typescript-client> [--output .] [-- <command>]
```

- `build` writes the target's package into the output directory. Only files in that package are touched: changed files are rewritten and files it no longer generates are removed.
  - `python-server`: `./<service>_api/v<major>/` (`api`, `endpoints`, `resources`, `internal`, `exceptions`). Code run from the output directory imports it directly, e.g. `from my_service_api.v1 import api`. Needs `kiba-core` (`core.api`, `core.util.typing_util`; 0.5.3.dev87 or later for `File` fields), `pydantic` and `starlette`.
  - `typescript-client`: `./<service>-api/v<major>/` (`client`, `endpoints`, `resources`, `index`) with a `<Service>ApiV<major>Client` that extends `@kibalabs/core`'s `ServiceClient`. Construct it with the url the API version is mounted at, e.g. `new MyServiceApiV1Client(requester, 'https://api.example.com/v1')`. Methods take path parameters, then a params object for the request fields, and return the response field; stream transitions take a callback for each item; transitions with `File` fields send a multipart form. Transitions with `responseType: redirect` or a `query-parameters` field are left out, as browsers open redirects directly and query-parameters fields receive third-party callbacks. Needs `@kibalabs/core`.
- `watch` builds, then rebuilds whenever the spec changes. If the spec is invalid it logs the error and keeps the previous output. Given a command after `--`, it runs it once the first build is done, keeps rebuilding while it runs, exits with its exit code and stops it when watch itself is stopped, e.g. `geniespec watch --spec api.yaml --target python-server -- uvicorn app:app --reload`.
- The bundled templates are examples of a kibalabs-style target.

## Enums, oneOfs and files

Enums are string values limited to a list. Name them at the top level to reuse them, or give a field its own:

```yaml
enums:
  - name: ViewKind
    values: [member, cycle-start]
resources:
  - singleName: View
    collectionName: Views
    attributes:
      - name: kind
        type: ViewKind
      - name: size
        type: Enum
        enumValues: [small, large]
```

`python-server` types them as `typing.Literal[...]` (named ones as `ViewKindV1` in `resources`) and rejects requests with other values; `typescript-client` types them as `'member' | 'cycle-start'` (named ones as an exported `ViewKindV1`).

`type: File` request fields upload a file. They are only allowed on POST transitions, and the transition's other fields must be single primitive or enum values, as the request is sent as a multipart form. Internal methods receive kiba-core's `UploadedFile` (`filename`, `contentType`, `content`); clients pass a `File`.

A oneOf is a value that is one of several resources, told apart by a discriminator attribute. Each member resource needs that attribute as a non-nullable enum with a single value:

```yaml
oneOfs:
  - name: ViewContent
    discriminator: kind
    types: [ChartContent, TableContent]
resources:
  - singleName: ChartContent
    collectionName: ChartContents
    attributes:
      - name: kind
        type: Enum
        enumValues: [chart]
```

Fields use it like any other type (`type: ViewContent`, also inside `List` and `Mapping`). `python-server` generates a `ViewContentV1` pydantic discriminated union in `resources`; `typescript-client` generates a `ViewContentV1` union type and a `viewContentV1FromObject` function that builds the member class named by the discriminator (and throws for unknown values).

`type: Uuid` is a string that must be a valid UUID. It works anywhere `String` does, including as a primary attribute in paths. `python-server` types it as `uuid.UUID`, so pydantic rejects other strings with a 400, internal methods get `uuid.UUID` objects and responses write them in the standard lowercase hyphenated form; `typescript-client` types it as `string`.

`type: BigInt` is an integer of any size that travels as a JSON string, because JSON numbers past 2^53 lose precision in JavaScript. `python-server` types it as `int` (a `BigInt` alias in `resources`), accepts `"123"` or `123` in requests, always writes it as a string and documents it as `{"type": "string"}`; `typescript-client` types it as `bigint`, parsed with `BigInt(...)` and sent with `String(...)`.

## Rate limits

Name rate limits at the top level, then pick one per transition with `rateLimit`. `defaultRateLimit` applies to every transition that doesn't set one, and `rateLimit: none` turns it off for a transition, the same way `defaultAuthentication` and `authentication` work:

```yaml
rateLimits:
  - name: standard-read
    perMinute: 30
    perHour: 300
  - name: public-read
    perMinute: 30
    perHour: 300
    keyBy: ip
defaultRateLimit: standard-read
transitions:
  - action: GET-HEALTH
    method: GET
    authentication: none
    rateLimit: public-read
```

A rate limit needs at least one of `perMinute`, `perFiveMinutes`, `perHour` and `perDay`. `keyBy` is `user` (the default) or `ip`. Requests over any window are rejected with a 429. Limits keyed by `user` count per authenticated user, so a transition using one needs `authentication`. `python-server` writes each rate limit as a `RATE_LIMIT_<NAME>` kiba-core `RateLimitConfig` and passes it to `route`; keying by `ip` needs kiba-core's `OriginIpMiddleware`. `typescript-client` ignores rate limits.

## API docs

Transitions can set `operationId`, `summary`, `description`, `tags` and `extensions`, and attributes, request fields and response fields can set a `description`:

```yaml
resources:
  - singleName: Member
    collectionName: Members
    attributes:
      - name: member-id
        type: Uuid
        isPrimary: true
        description: The member's id.
    transitions:
      - action: GET
        operationId: getMember
        summary: Get a member
        description: Returns one member.
        tags: [Members]
        extensions: {deprecated: true}
```

`python-server` passes the transition fields to kiba-core's `route`, whose `OpenApiSchemaGenerator` documents every route with an `operationId` (and skips the rest); `extensions` reach `OpenApiExtension`s as `metadata['extensions']`. Field descriptions become pydantic `Field(description=...)`, so they show up in the request and response schemas. Each `operationId` must be unique, so a transition that generates more than one route (for example `GET` on a resource with unique attributes) can't set one. `typescript-client` ignores these fields.

## Overrides

`overrides` keep an API that existed before genie working the same way once it moves to genie. They are meant to be dropped in the next major version of that API.

- `shouldPrefixParentName: false` on a child resource names it without its parent's name: `Agent` under `User` stays `Agent` (not `UserAgent`), so its primary attribute is `agent-id` rather than `user-agent-id` and its fields keep their names. Its path is unchanged (`/users/{userId}/agents/{agentId}`).
- `responseFieldName` on a `GET`, `LIST`, `CREATE` or `UPDATE` transition renames the field its response puts the resource in (for example `memories` instead of `agentMemories`). Custom transitions name it with `responseField`.

# Development

```
make install
make lint-check type-check test
```

`tests/python_server` covers the core and the `python-server` target (the core tests generate through it) and runs in `Dockerfile`. `tests/typescript_client` covers the `typescript-client` target; it needs node and runs in `typescript-client.Dockerfile`:

```
make install-typescript-client
make test-typescript-client
```

Merges to `main` publish a dev version to PyPI, except for changes that only touch the landing page. To release, bump `version` in `pyproject.toml` in a PR, then run the Release workflow on `main` (Actions → Release → Run workflow). It tags `vX.Y.Z` and the Publish workflow publishes it. Only the release workflow can push version tags.

`landing/` is the static site for geniespec.com (plain HTML, CSS and JS, no build step). Preview it with `python3 -m http.server --directory landing`. Merges that touch it sync it to the kiba sites bucket and invalidate CloudFront (`.github/workflows/landing-deploy.yml`).

# Things that need work

## Typing of params and fields in general

I think we need to create an object for Type. what would it look like?


```
class BaseFieldType:
    isNullable: bool


class RawFieldType(BaseFieldType):
    name: str


class ClassFieldType(BaseFieldType):
    fieldType: RawFieldType


class ListFieldType:(BaseFieldType)
    fieldType: RawFieldType
    isNullable: bool


class MappingFieldType(BaseFieldType):
    keyFieldType: RawFieldType
    valueFieldType: RawFieldType


class OneOfFieldType(BaseFieldType):
    fieldTypes: list[RawFieldType]


class EnumFieldType(BaseFieldType):
    values: list[str]

```
