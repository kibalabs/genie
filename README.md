# Genie

Genie (`geniespec` on PyPI) generates API code from an `api.yaml` spec. Install it like any other tool and run it from your build scripts; the generated code is gitignored, not committed.

```
geniespec build --spec api.yaml --target python-server [--output .]
geniespec watch --spec api.yaml --target python-server [--output .] [-- <command>]
```

- `build` writes the target's package into the output directory, e.g. `./<service>_api/v<major>/` (`api`, `endpoints`, `resources`, `internal`, `exceptions`) for `python-server`. Only files in that package are touched: changed files are rewritten and files it no longer generates are removed.
- `watch` builds, then rebuilds whenever the spec changes. If the spec is invalid it logs the error and keeps the previous output. Given a command after `--`, it runs it once the first build is done, keeps rebuilding while it runs, exits with its exit code and stops it when watch itself is stopped, e.g. `geniespec watch --spec api.yaml --target python-server -- uvicorn app:app --reload`.
- Code run from the output directory imports the package directly, e.g. `from my_service_api.v1 import api`. Generated `python-server` code needs `kiba-core` (`core.api`, `core.util.typing_util`), `pydantic` and `starlette`.
- The bundled templates are examples of a kibalabs-style target.

# Development

```
make install
make lint-check type-check test
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
