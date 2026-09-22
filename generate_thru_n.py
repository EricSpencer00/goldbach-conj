#!/usr/bin/env python3
"""Generate a deterministic Goldbach decomposition run.

The default remains the historical 1-billion-number run.  ``--max-n`` and
``--output`` make bounded reproduction runs possible without editing source.
Use ``--manifest`` to record a provenance manifest alongside the artifact.
"""
import argparse
import time
from pathlib import Path
from typing import Sequence

from goldbach_check import sieve

MAX_N = 1_000_000_000


def default_output_path(max_n: int) -> Path:
    """Return the historical filename for a requested upper bound."""

    return Path(__file__).resolve().parent / "runs" / (
        f"thru{max_n:,}".replace(",", "-") + ".txt"
    )


# Preserve the old module-level default for callers that imported it.
OUT_PATH = default_output_path(MAX_N)


def generate_run(max_n: int, out_path: str | Path) -> int:
    """Generate every first-found decomposition through ``max_n``."""

    if max_n < 4 or max_n % 2:
        raise ValueError("max_n must be an even number at least 4")

    output = Path(out_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    is_prime, primes = sieve(max_n)
    prime_set = is_prime

    start = time.perf_counter()
    total = 0
    with output.open("w", encoding="utf-8") as handle:
        handle.write(f"Goldbach decompositions for even numbers 4..{max_n}\n")
        handle.write("Format: n = p + q\n")
        handle.write("\n")

        for n in range(4, max_n + 1, 2):
            total += 1
            found = False
            for p in primes:
                if p > n // 2:
                    break
                if prime_set[n - p]:
                    handle.write(f"{n} = {p} + {n - p}\n")
                    found = True
                    break
            if not found:
                handle.write(f"{n} = NO_DECOMPOSITION_FOUND\n")

            if total % 100000 == 0:
                elapsed = time.perf_counter() - start
                print(f"Progress: wrote {total} decompositions ({elapsed:.1f}s)")

    elapsed = time.perf_counter() - start
    print(f"Wrote {total} decompositions to: {output}")
    print(f"Elapsed time: {elapsed:.3f}s")
    return total


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-n", type=int, default=MAX_N)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        help="write a provenance manifest for the generated artifact",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = args.output or default_output_path(args.max_n)
    generate_run(args.max_n, output)

    if args.manifest:
        from run_manifest import create_manifest

        create_manifest(
            output,
            args.manifest,
            Path(__file__),
            Path(__file__).with_name("goldbach_check.py"),
            ("python3", Path(__file__).name, "--max-n", str(args.max_n)),
        )
        print(f"Wrote provenance manifest to: {args.manifest}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
