# Genie

Genie (`geniespec` on PyPI) generates API code from an `api.yaml` spec. Install it like any other tool and run it from your build scripts; the generated code is gitignored, not committed.

```
geniespec build --spec api.yaml --target <python-server | typescript-client> [--output .]
geniespec watch --spec api.yaml --target <python-server | typescript-client> [--output .] [-- <command>]
```

- `build` writes the target's package into the output directory. Only files in that package are touched: changed files are rewritten and files it no longer generates are removed.
  - `python-server`: `./<service>_api/v<major>/` (`api`, `endpoints`, `resources`, `internal`, `exceptions`). Code run from the output directory imports it directly, e.g. `from my_service_api.v1 import api`. Needs `kiba-core` (`core.api`, `core.util.typing_util`), `pydantic` and `starlette`.
  - `typescript-client`: `./<service>-api/v<major>/` (`client`, `endpoints`, `resources`, `index`) with a `<Service>ApiV<major>Client` that extends `@kibalabs/core`'s `ServiceClient`. Construct it with the url the API version is mounted at, e.g. `new MyServiceApiV1Client(requester, 'https://api.example.com/v1')`. Methods take path parameters, then a params object for the request fields, and return the response field; stream transitions take a callback for each item. Transitions with `responseType: redirect` or a `query-parameters` field are left out, as browsers open redirects directly and query-parameters fields receive third-party callbacks. Needs `@kibalabs/core`.
- `watch` builds, then rebuilds whenever the spec changes. If the spec is invalid it logs the error and keeps the previous output. Given a command after `--`, it runs it once the first build is done, keeps rebuilding while it runs, exits with its exit code and stops it when watch itself is stopped, e.g. `geniespec watch --spec api.yaml --target python-server -- uvicorn app:app --reload`.
- The bundled templates are examples of a kibalabs-style target.

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

Enum and OneOf not supported yet

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
