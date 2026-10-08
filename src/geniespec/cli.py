import argparse
import pathlib
import signal
import subprocess
import sys
import tempfile
import time
import types

import yaml  # type: ignore[import-untyped]
from core import logging

from geniespec.genie import TARGET_LANGUAGE_CODES
from geniespec.genie import Renderer
from geniespec.genie import SyntacticApiValidator
from geniespec.types import KibaApi

WATCH_INTERVAL_SECONDS = 0.5
COMMAND_STOP_TIMEOUT_SECONDS = 10


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


def build(specPath: pathlib.Path, target: str, outputDirectoryPath: pathlib.Path) -> list[pathlib.Path]:
    with open(specPath) as specFile:
        apiYaml = yaml.safe_load(specFile)
    SyntacticApiValidator().validate(apiYaml)
    api = KibaApi(**apiYaml)
    with tempfile.TemporaryDirectory() as renderDirectory:
        Renderer(target=target).render_directory(api=api, outputDirectoryPath=renderDirectory)
        changedPaths: list[pathlib.Path] = []
        # NOTE(krishan711): only sync the packages the target generates so other files in the output directory are never touched
        for packagePath in sorted(pathlib.Path(renderDirectory).iterdir()):
            changedPaths += _sync_directory(sourceDirectoryPath=packagePath, targetDirectoryPath=outputDirectoryPath / packagePath.name)
        return changedPaths


def _build_and_log(specPath: pathlib.Path, target: str, outputDirectoryPath: pathlib.Path) -> None:
    changedPaths = build(specPath=specPath, target=target, outputDirectoryPath=outputDirectoryPath)
    logging.info(f'geniespec: built {specPath} into {outputDirectoryPath} ({len(changedPaths)} files changed)')


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=COMMAND_STOP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def watch(specPath: pathlib.Path, target: str, outputDirectoryPath: pathlib.Path, command: list[str]) -> int:
    lastModifiedTime: int | None = None
    process: subprocess.Popen[bytes] | None = None
    try:
        while True:
            try:
                modifiedTime: int | None = specPath.stat().st_mtime_ns
            except FileNotFoundError:
                modifiedTime = lastModifiedTime
            if modifiedTime != lastModifiedTime:
                lastModifiedTime = modifiedTime
                try:
                    _build_and_log(specPath=specPath, target=target, outputDirectoryPath=outputDirectoryPath)
                except Exception as exception:  # noqa: BLE001
                    logging.error(f'geniespec: failed to build {specPath}, keeping the previous output: {exception}')
            if command and process is None:
                process = subprocess.Popen(command)  # noqa: S603
            if process is not None and process.poll() is not None:
                return process.returncode
            time.sleep(WATCH_INTERVAL_SECONDS)
    finally:
        if process is not None:
            _stop_process(process=process)


def _exit_on_terminate(signalNumber: int, frame: types.FrameType | None) -> None:  # noqa: ARG001
    sys.exit(128 + signalNumber)


def main() -> None:
    parser = argparse.ArgumentParser(prog='geniespec')
    subparsers = parser.add_subparsers(dest='subcommand', required=True)
    for subcommand in ('build', 'watch'):
        subparser = subparsers.add_parser(subcommand)
        subparser.add_argument('--spec', type=pathlib.Path, required=True)
        subparser.add_argument('--target', choices=sorted(TARGET_LANGUAGE_CODES), required=True)
        subparser.add_argument('--output', type=pathlib.Path, default=pathlib.Path())
    subparsers.choices['watch'].add_argument('command', nargs=argparse.REMAINDER, help='command to run while watching, after --')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.subcommand == 'build':
        _build_and_log(specPath=args.spec, target=args.target, outputDirectoryPath=args.output)
        return
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    signal.signal(signal.SIGTERM, _exit_on_terminate)
    try:
        sys.exit(watch(specPath=args.spec, target=args.target, outputDirectoryPath=args.output, command=command))
    except KeyboardInterrupt:
        return


if __name__ == '__main__':
    main()
