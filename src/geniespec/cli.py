import argparse
import pathlib
import tempfile
import time

import yaml  # type: ignore[import-untyped]
from core import logging

from geniespec.genie import Renderer
from geniespec.genie import SyntacticApiValidator
from geniespec.types import KibaApi

WATCH_INTERVAL_SECONDS = 0.5


def _sync_directory(sourceDirectoryPath: pathlib.Path, targetDirectoryPath: pathlib.Path) -> list[pathlib.Path]:
    changedPaths: list[pathlib.Path] = []
    sourceRelativePaths = {path.relative_to(sourceDirectoryPath) for path in sourceDirectoryPath.rglob('*') if path.is_file()}
    for relativePath in sorted(sourceRelativePaths):
        content = (sourceDirectoryPath / relativePath).read_bytes()
        targetPath = targetDirectoryPath / relativePath
        if targetPath.is_file() and targetPath.read_bytes() == content:
            continue
        targetPath.parent.mkdir(parents=True, exist_ok=True)
        temporaryPath = targetPath.with_name(f'.{targetPath.name}.tmp')
        temporaryPath.write_bytes(content)
        temporaryPath.replace(targetPath)
        changedPaths.append(targetPath)
    stalePaths = [path for path in targetDirectoryPath.rglob('*') if path.is_file() and '__pycache__' not in path.parts and path.relative_to(targetDirectoryPath) not in sourceRelativePaths]
    for stalePath in stalePaths:
        stalePath.unlink()
    return changedPaths + stalePaths


def build(specPath: pathlib.Path, outputDirectoryPath: pathlib.Path) -> list[pathlib.Path]:
    with open(specPath) as specFile:
        apiYaml = yaml.safe_load(specFile)
    SyntacticApiValidator().validate(apiYaml)
    api = KibaApi(**apiYaml)
    with tempfile.TemporaryDirectory() as renderDirectory:
        Renderer().render_directory(api=api, outputDirectoryPath=renderDirectory)
        return _sync_directory(sourceDirectoryPath=pathlib.Path(renderDirectory), targetDirectoryPath=outputDirectoryPath / 'python')


def _build_and_log(specPath: pathlib.Path, outputDirectoryPath: pathlib.Path) -> None:
    changedPaths = build(specPath=specPath, outputDirectoryPath=outputDirectoryPath)
    logging.info(f'geniespec: built {specPath} into {outputDirectoryPath} ({len(changedPaths)} files changed)')


def watch(specPath: pathlib.Path, outputDirectoryPath: pathlib.Path) -> None:
    lastModifiedTime: int | None = None
    while True:
        try:
            modifiedTime: int | None = specPath.stat().st_mtime_ns
        except FileNotFoundError:
            modifiedTime = lastModifiedTime
        if modifiedTime != lastModifiedTime:
            lastModifiedTime = modifiedTime
            try:
                _build_and_log(specPath=specPath, outputDirectoryPath=outputDirectoryPath)
            except Exception as exception:  # noqa: BLE001
                logging.error(f'geniespec: failed to build {specPath}, keeping the previous output: {exception}')
        time.sleep(WATCH_INTERVAL_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(prog='geniespec')
    subparsers = parser.add_subparsers(dest='command', required=True)
    for command in ('build', 'watch'):
        subparser = subparsers.add_parser(command)
        subparser.add_argument('--spec', type=pathlib.Path, required=True)
        subparser.add_argument('--output', type=pathlib.Path, default=pathlib.Path('.genie'))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.command == 'build':
        _build_and_log(specPath=args.spec, outputDirectoryPath=args.output)
        return
    try:
        watch(specPath=args.spec, outputDirectoryPath=args.output)
    except KeyboardInterrupt:
        return


if __name__ == '__main__':
    main()
