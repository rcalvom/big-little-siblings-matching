"""Command-line interface for canonical private matching workflows."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import unicodedata
from contextlib import contextmanager
from pathlib import Path

from .config import load_config
from .data import (
    load_declared_matches_with_hash,
    read_canonical_csv_with_hash,
    validate_participants,
)
from .manifest import build_run_manifest, software_provenance
from .optimizer import solve_matching
from .reporting import (
    write_infeasibility_reports,
    write_matching_reports,
    write_validation_report,
)
from .review import build_review_queue
from .scoring import build_candidate_scores


def _load_inputs(args: argparse.Namespace):
    config = load_config(args.config)
    bigs, big_hash = read_canonical_csv_with_hash(args.big, "big")
    littles, little_hash = read_canonical_csv_with_hash(args.little, "little")
    declared, declared_hash = load_declared_matches_with_hash(args.declared)
    validation = validate_participants(bigs, littles, declared, config)
    input_hashes = {
        "big_sha256": big_hash,
        "little_sha256": little_hash,
        "declared_sha256": declared_hash,
    }
    return config, bigs, littles, declared, validation, input_hashes


def _validate_report_destination(args: argparse.Namespace) -> None:
    report = Path(args.report)
    if report.exists() or report.is_symlink():
        raise ValueError("The validation report path must not already exist.")
    report_path = report.resolve(strict=False)
    inputs = [args.big, args.little, args.declared, args.config]
    if any(
        report_path == Path(path).resolve(strict=False)
        for path in inputs
        if path is not None
    ):
        raise ValueError("The validation report path must differ from every input path.")


def command_validate(args: argparse.Namespace) -> int:
    _validate_report_destination(args)
    _, _, _, _, validation, _ = _load_inputs(args)
    write_validation_report(validation, args.report)
    print(
        f"Validation report written with {len(validation.errors)} errors and "
        f"{len(validation.warnings)} warnings."
    )
    return 0 if validation.is_valid else 2


@contextmanager
def _output_transaction(path: str | Path):
    destination = Path(path)
    if destination.exists() or destination.is_symlink():
        raise ValueError("The output directory must not already exist.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging_prefix = f".{destination.name}.staging-"
    if any(destination.parent.glob(f"{staging_prefix}*")):
        raise ValueError(
            "A stale private staging directory requires authorized review."
        )
    lock = destination.with_name(f".{destination.name}.lock")
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise ValueError("Another run holds the output-directory lock.") from error
    staging: Path | None = None
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode("ascii"))
        os.fsync(descriptor)
        staging = Path(
            tempfile.mkdtemp(
                prefix=staging_prefix, dir=destination.parent
            )
        )
        yield staging
        if destination.exists() or destination.is_symlink():
            raise ValueError("The output destination appeared during the run.")
        _fsync_directory(staging)
        os.rename(staging, destination)
        _fsync_directory(destination.parent)
    except BaseException:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        os.close(descriptor)
        lock.unlink(missing_ok=True)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _validate_operator(value: str) -> None:
    if (
        not value
        or value != value.strip()
        or value != unicodedata.normalize("NFC", value)
        or any(unicodedata.category(char) in {"Cc", "Cs"} for char in value)
    ):
        raise ValueError("--operator must be non-empty clean canonical text.")


def command_match(args: argparse.Namespace) -> int:
    _validate_operator(args.operator)
    status = 0
    message = ""
    message_is_error = False
    with _output_transaction(args.output_dir) as destination:
        config, bigs, littles, declared, validation, input_hashes = _load_inputs(
            args
        )
        write_validation_report(validation, destination / "validation.json")
        if not validation.is_valid:
            status = 2
            message_is_error = True
            message = (
                f"Matching stopped: validation found {len(validation.errors)} "
                "errors. See validation.json."
            )
        else:
            provenance = software_provenance()
            pair_scores, exclusions = build_candidate_scores(
                bigs, littles, config, declared
            )
            result = solve_matching(bigs, littles, pair_scores, declared)
            manifest = build_run_manifest(
                result,
                input_hashes=input_hashes,
                config=config,
                exclusions=exclusions,
                operator=args.operator,
                include_contacts=args.include_contacts,
                software=provenance,
            )
            if not result.is_complete:
                write_infeasibility_reports(
                    result,
                    pair_scores,
                    destination,
                    config=config,
                    manifest=manifest,
                    exclusions=exclusions,
                )
                status = 3
                message_is_error = True
                message = (
                    "Matching is infeasible under the hard policy. See "
                    "infeasibility.json; no matches.csv was produced."
                )
            else:
                review_cases = build_review_queue(
                    result, bigs, littles, pair_scores, declared, config
                )
                write_matching_reports(
                    result,
                    bigs,
                    littles,
                    pair_scores,
                    review_cases,
                    destination,
                    config=config,
                    manifest=manifest,
                    include_contacts=args.include_contacts,
                    exclusions=exclusions,
                )
                message = (
                    f"Wrote {len(result.matches)} complete assignments to "
                    "private reports."
                )
    print(message, file=sys.stderr if message_is_error else sys.stdout)
    return status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="csap-siblings-match",
        description="Exact, auditable matching from canonical private CSV inputs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_matching_inputs(command: argparse.ArgumentParser) -> None:
        command.add_argument("--big", required=True, help="Canonical Big CSV.")
        command.add_argument("--little", required=True, help="Canonical Little CSV.")
        command.add_argument("--declared", help="Canonical declared-match CSV.")
        command.add_argument("--config", help="Private policy catalog override YAML.")

    validate = subparsers.add_parser("validate", help="Validate canonical private inputs.")
    add_matching_inputs(validate)
    validate.add_argument("--report", required=True)
    validate.set_defaults(handler=command_validate)

    match = subparsers.add_parser("match", help="Run exact complete matching.")
    add_matching_inputs(match)
    match.add_argument("--output-dir", required=True)
    match.add_argument("--operator", required=True)
    match.add_argument("--include-contacts", action="store_true")
    match.set_defaults(handler=command_match)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (KeyError, TypeError):
        print("Command failed: invalid input or configuration structure.", file=sys.stderr)
        return 2
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Command failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
