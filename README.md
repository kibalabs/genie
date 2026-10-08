# Genie

Genie (`geniespec` on PyPI) generates API code from an `api.yaml` spec. The output is a package you install, not code you commit.

```
uvx geniespec build --spec api.yaml [--output .genie]
uvx geniespec watch --spec api.yaml [--output .genie]
```

- `build` writes `<output>/python`: a project with `pyproject.toml` and `src/<service>_api/v<major>/` (`api`, `endpoints`, `resources`, `internal`, `exceptions`). Only changed files are rewritten and files it no longer generates are removed.
- `watch` rebuilds whenever the spec changes. If the spec is invalid it logs the error and keeps the previous output.
- Consumers depend on the output as an editable path dependency, e.g. `my-service-api = { path = ".genie/python", editable = true }` in `[tool.uv.sources]`, and import it as `my_service_api.v1`.
- Generated code needs `kiba-core` (`core.api`, `core.util.typing_util`), `pydantic` and `starlette` from the consumer.

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
