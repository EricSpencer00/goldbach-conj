#!/usr/bin/env python3
"""
Goldbach verifier: check every even number from 4..1_000_000
Find two primes that sum to each even number. Print examples and report
if any counterexample is found.

Usage: python3 goldbach_check.py
"""
import time

MAX_N = 1_000_000

def sieve(max_n):
    is_prime = bytearray(b"\x01") * (max_n + 1)
    is_prime[:2] = b"\x00\x00"
    p = 2
    while p * p <= max_n:
        if is_prime[p]:
            step = p
            start = p * p
            is_prime[start:max_n+1:step] = b"\x00" * (((max_n - start) // step) + 1)
        p += 1
    primes = [i for i, val in enumerate(is_prime) if val]
    return is_prime, primes

def verify_goldbach(max_n):
    is_prime, primes = sieve(max_n)
    samples = []
    checked = 0
    start_time = time.time()

    prime_set = is_prime  # bytearray supports indexing -> truthiness

    for n in range(4, max_n + 1, 2):
        checked += 1
        found = False
        # iterate primes up to n//2
        for p in primes:
            if p > n // 2:
                break
            if prime_set[n - p]:
                if len(samples) < 10:
                    samples.append((n, p, n - p))
                found = True
                break
        if not found:
            elapsed = time.time() - start_time
            print(f"Counterexample found: {n} has no prime sum decomposition")
            print(f"Checked {checked} even numbers in {elapsed:.3f}s")
            return False, samples, checked, elapsed

    elapsed = time.time() - start_time
    return True, samples, checked, elapsed

def main():
    ok, samples, checked, elapsed = verify_goldbach(MAX_N)
    if ok:
        print(f"All even numbers 4..{MAX_N} verified for Goldbach conjecture.")
        print(f"Total even numbers checked: {checked}")
        print(f"Elapsed time: {elapsed:.3f}s")
        print("Sample decompositions (up to 10):")
        for n, a, b in samples:
            print(f"{n} = {a} + {b}")
        return 0
    else:
        print("Counterexample detected — investigation needed.")
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
