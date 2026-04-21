"""SimHash utilities for near-duplicate text detection.

Not integrated into the pipeline yet — prepared for future use in Phase 2.

API:
  simhash(text, bits=64)       -> int   64-bit fingerprint of the text
  hamming_distance(h1, h2)     -> int   bit-difference between two fingerprints

Typical usage (future):
  threshold = 10  # Hamming ≤ 10 bits in 64 ≈ near-duplicate
  if hamming_distance(simhash(a), simhash(b)) <= threshold:
      # treat as near-duplicate
"""
from __future__ import annotations

import hashlib


def simhash(text: str, bits: int = 64) -> int:
    """Return a SimHash fingerprint of *text* with *bits* precision.

    Algorithm (Charikar 2002):
      1. Tokenise text into unigrams (whitespace split after lowercase).
      2. For each token, compute a full-width hash (MD5, interpreted as integer).
      3. Accumulate a dimension vector: for each bit position, +1 if the
         hash bit is set, -1 otherwise.
      4. Collapse: bit i of the fingerprint = 1 if v[i] > 0, else 0.

    The resulting integer has the property that the Hamming distance between
    two fingerprints approximates the cosine distance between the bag-of-words
    representations of the two documents.
    """
    tokens = text.lower().split()
    v = [0] * bits
    for token in tokens:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        for i in range(bits):
            v[i] += 1 if (h >> i) & 1 else -1
    return sum(1 << i for i, x in enumerate(v) if x > 0)


def hamming_distance(h1: int, h2: int) -> int:
    """Return the number of differing bits between two integer fingerprints."""
    return bin(h1 ^ h2).count('1')
