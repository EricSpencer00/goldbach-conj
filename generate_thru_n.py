#!/usr/bin/env python3
"""
Generate a file with Goldbach decompositions for every even number
from 4 through 1,000,000 and write the results to `runs/thru1-000-000.txt`.

Usage: python3 generate_thru1_000_000.py
"""
import time
from pathlib import Path

from goldbach_check import sieve

MAX_N = 1_000_000_000
# Build the filename first, then join with Path to avoid TypeError
OUT_PATH = Path(__file__).resolve().parent / 'runs' / (f"thru{MAX_N:,}".replace(',', '-') + '.txt')

def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    is_prime, primes = sieve(MAX_N)
    prime_set = is_prime

    start = time.time()
    total = 0
    with OUT_PATH.open('w', encoding='utf-8') as f:
        f.write(f"Goldbach decompositions for even numbers 4..{MAX_N}\n")
        f.write("Format: n = p + q\n")
        f.write("\n")

        for n in range(4, MAX_N + 1, 2):
            total += 1
            found = False
            for p in primes:
                if p > n // 2:
                    break
                if prime_set[n - p]:
                    f.write(f"{n} = {p} + {n - p}\n")
                    found = True
                    break
            if not found:
                f.write(f"{n} = NO_DECOMPOSITION_FOUND\n")

            if total % 100000 == 0:
                elapsed = time.time() - start
                print(f"Progress: wrote {total} decompositions ({elapsed:.1f}s)")

    elapsed = time.time() - start
    print(f"Wrote {total} decompositions to: {OUT_PATH}")
    print(f"Elapsed time: {elapsed:.3f}s")


if __name__ == '__main__':
    raise SystemExit(main())
