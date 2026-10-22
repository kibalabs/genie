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

Merges to `main` publish a dev version to PyPI. To release, bump `version` in `pyproject.toml` in a PR, then run the Release workflow on `main` (Actions → Release → Run workflow). It tags `vX.Y.Z` and the Publish workflow publishes it. Only the release workflow can push version tags.

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
