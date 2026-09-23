from __future__ import annotations

import argparse
from pathlib import Path
import sys

from counterparty_sampling.core import SamplingError
from counterparty_sampling.workbook import run_sampling, write_results


def _parse_override(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Use ALERT_ID=PARTY_ID for focal overrides.")
    alert_id, party_id = (part.strip() for part in value.split("=", 1))
    if not alert_id or not party_id:
        raise argparse.ArgumentTypeError("Use ALERT_ID=PARTY_ID for focal overrides.")
    return alert_id, party_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sample alert counterparties using mapped, auditable methodologies."
    )
    instructions = parser.add_mutually_exclusive_group(required=True)
    instructions.add_argument("--instructions-file", type=Path)
    instructions.add_argument("--instructions-text")
    parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("--transactions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--focal-party",
        action="append",
        default=[],
        type=_parse_override,
        metavar="ALERT_ID=PARTY_ID",
        help="Override focal-party inference for an alert; may be repeated.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        instruction_text = (
            args.instructions_file.read_text(encoding="utf-8")
            if args.instructions_file
            else args.instructions_text
        )
        overrides = dict(args.focal_party)
        results = run_sampling(
            instruction_text,
            args.mapping,
            args.transactions,
            focal_party_overrides=overrides,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_results(
            args.output,
            results,
            instruction_text,
            args.mapping,
            args.transactions,
        )
    except (OSError, SamplingError) as exc:
        print(f"Sampling failed: {exc}", file=sys.stderr)
        return 1

    selected_count = sum(len(result.selected) for result in results)
    print(
        f"Processed {len(results)} alert(s); selected {selected_count} counterparty record(s). "
        f"Output: {args.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
