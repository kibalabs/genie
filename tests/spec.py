import pathlib

import yaml  # type: ignore[import-untyped]

BASE_SPEC = """
version: 1.0.0
serviceName: genie-test
pythonClientPackageName: genie-test
typescriptClientPackageName: genie-test
defaultAuthentication: none
"""


def write_spec(specYaml: str, directory: pathlib.Path) -> pathlib.Path:
    specPath = directory / 'api.yaml'
    specPath.write_text(yaml.safe_dump({**yaml.safe_load(BASE_SPEC), **yaml.safe_load(specYaml)}))
    return specPath
