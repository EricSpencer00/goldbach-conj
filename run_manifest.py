#!/usr/bin/env python3
"""Create and verify provenance manifests for Goldbach run artifacts.

This module deliberately does not establish primality or validate each
decomposition.  ``verify_run.py`` owns that mathematical validation.  A
manifest answers a different question: do the exact artifact bytes and the
source files named by a reproduction command still match the recorded run?

Examples::

    python3 run_manifest.py create runs/thru1-000-000.txt \
        --manifest runs/thru1-000-000.json
    python3 run_manifest.py verify runs/thru1-000-000.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from re import Match, compile
from typing import Any, Sequence


SCHEMA_VERSION = 1
FORMAT_LINE = "Format: n = p + q"
HEADER_RE = compile(r"^Goldbach decompositions for even numbers (\d+)\.\.(\d+)$")


class ManifestError(ValueError):
    """A run manifest or one of its referenced files is invalid."""


@dataclass(frozen=True)
class RunFacts:
    """Stable facts about the shape of a generated run artifact."""

    start: int
    end: int
    records: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise ManifestError(f"{label} is not a readable file: {path}")
    return path


def _relative_path(path: Path, directory: Path) -> str:
    try:
        return Path(os.path.relpath(path.resolve(), directory.resolve())).as_posix()
    except ValueError as exc:
        raise ManifestError(f"cannot make {path} relative to {directory}") from exc


def _manifest_path(value: Any, manifest_directory: Path, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ManifestError(f"manifest field {label!r} must be a non-empty path")
    path = Path(value)
    if path.is_absolute():
        raise ManifestError(f"manifest field {label!r} must be relative")
    return _require_file((manifest_directory / path).resolve(), label)


def _read_run_facts(path: Path) -> RunFacts:
    """Read only the declared range and record count from a run artifact."""

    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            header = handle.readline().rstrip("\n")
            header_match: Match[str] | None = HEADER_RE.fullmatch(header)
            if header_match is None:
                raise ManifestError(
                    f"{path}: expected a declared even-number range in the first line"
                )

            start, end = (int(value) for value in header_match.groups())
            if start != 4 or end < start or end % 2:
                raise ManifestError(f"{path}: declared range must be 4..an even number")
            if handle.readline().rstrip("\n") != FORMAT_LINE:
                raise ManifestError(f"{path}: unexpected format line")
            if handle.readline().rstrip("\n") != "":
                raise ManifestError(f"{path}: expected a blank line before records")

            records = 0
            for line in handle:
                if not line.rstrip("\n"):
                    raise ManifestError(f"{path}: blank record line")
                records += 1
    except OSError as exc:
        raise ManifestError(f"cannot read run artifact {path}: {exc}") from exc

    expected_records = ((end - start) // 2) + 1
    if records != expected_records:
        raise ManifestError(
            f"{path}: expected {expected_records} records, found {records}"
        )
    return RunFacts(start=start, end=end, records=records)


def _metadata(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def create_manifest(
    run_path: str | Path,
    manifest_path: str | Path,
    generator_path: str | Path,
    checker_path: str | Path,
    command: Sequence[str],
) -> dict[str, Any]:
    """Create a stable JSON manifest and return its payload."""

    run = _require_file(Path(run_path).resolve(), "run artifact")
    manifest = Path(manifest_path).resolve()
    generator = _require_file(Path(generator_path).resolve(), "generator source")
    checker = _require_file(Path(checker_path).resolve(), "checker source")
    facts = _read_run_facts(run)
    command_values = [str(value) for value in command]
    if not command_values:
        raise ManifestError("reproduction command must not be empty")

    manifest_directory = manifest.parent
    payload: dict[str, Any] = {
        "artifact": {
            "path": _relative_path(run, manifest_directory),
            **_metadata(run),
        },
        "command": command_values,
        "range": {
            "end": facts.end,
            "records": facts.records,
            "start": facts.start,
        },
        "schema": SCHEMA_VERSION,
        "sources": {
            "checker": {
                "path": _relative_path(checker, manifest_directory),
                **_metadata(checker),
            },
            "generator": {
                "path": _relative_path(generator, manifest_directory),
                **_metadata(generator),
            },
        },
    }

    manifest.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest.with_name(f".{manifest.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(manifest)
    return payload


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"manifest field {label!r} must be an object")
    return value


def _check_metadata(path: Path, metadata: dict[str, Any], label: str) -> None:
    expected_bytes = metadata.get("bytes")
    expected_sha = metadata.get("sha256")
    if not isinstance(expected_bytes, int) or expected_bytes < 0:
        raise ManifestError(f"manifest field {label}.bytes is invalid")
    if not isinstance(expected_sha, str) or len(expected_sha) != 64:
        raise ManifestError(f"manifest field {label}.sha256 is invalid")

    actual = _metadata(path)
    if actual != {"bytes": expected_bytes, "sha256": expected_sha}:
        raise ManifestError(
            f"{label} changed: expected {expected_bytes} bytes/{expected_sha}, "
            f"found {actual['bytes']} bytes/{actual['sha256']}"
        )


def verify_manifest(manifest_path: str | Path) -> dict[str, Any]:
    """Verify every recorded file and stable run fact in a manifest."""

    manifest = Path(manifest_path).resolve()
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot read manifest {manifest}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ManifestError("manifest root must be an object")
    if payload.get("schema") != SCHEMA_VERSION:
        raise ManifestError(f"unsupported manifest schema: {payload.get('schema')!r}")

    artifact_metadata = _mapping(payload.get("artifact"), "artifact")
    artifact = _manifest_path(
        artifact_metadata.get("path"), manifest.parent, "artifact.path"
    )
    _check_metadata(artifact, artifact_metadata, "artifact")

    sources = _mapping(payload.get("sources"), "sources")
    for source_name in ("generator", "checker"):
        source_metadata = _mapping(sources.get(source_name), f"sources.{source_name}")
        source = _manifest_path(
            source_metadata.get("path"),
            manifest.parent,
            f"sources.{source_name}.path",
        )
        _check_metadata(source, source_metadata, f"sources.{source_name}")

    facts = _read_run_facts(artifact)
    recorded_range = _mapping(payload.get("range"), "range")
    expected_facts = {
        "start": recorded_range.get("start"),
        "end": recorded_range.get("end"),
        "records": recorded_range.get("records"),
    }
    actual_facts = {
        "start": facts.start,
        "end": facts.end,
        "records": facts.records,
    }
    if expected_facts != actual_facts:
        raise ManifestError(
            f"artifact range changed: expected {expected_facts}, found {actual_facts}"
        )

    command = payload.get("command")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(value, str) and value for value in command)
    ):
        raise ManifestError("manifest command must be a non-empty list of strings")
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)

    create = subparsers.add_parser("create", help="create a provenance manifest")
    create.add_argument("run", type=Path, help="generated run artifact")
    create.add_argument("--manifest", required=True, type=Path)
    create.add_argument(
        "--generator",
        type=Path,
        default=Path(__file__).with_name("generate_thru_n.py"),
    )
    create.add_argument(
        "--checker",
        type=Path,
        default=Path(__file__).with_name("goldbach_check.py"),
    )
    create.add_argument(
        "--command",
        default="python3 generate_thru_n.py",
        help="reproduction command recorded in the manifest",
    )

    verify = subparsers.add_parser("verify", help="verify a provenance manifest")
    verify.add_argument("manifest", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.action == "create":
            payload = create_manifest(
                args.run,
                args.manifest,
                args.generator,
                args.checker,
                shlex.split(args.command),
            )
            print(f"Created manifest: {args.manifest}")
            print(
                "Recorded range: "
                f"{payload['range']['start']}..{payload['range']['end']} "
                f"({payload['range']['records']} records)"
            )
            return 0

        payload = verify_manifest(args.manifest)
        print(f"Valid run manifest: {args.manifest}")
        print(
            "Recorded range: "
            f"{payload['range']['start']}..{payload['range']['end']} "
            f"({payload['range']['records']} records)"
        )
        print(f"Artifact SHA-256: {payload['artifact']['sha256']}")
        return 0
    except (ManifestError, OSError, ValueError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
