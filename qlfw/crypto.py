"""Keying, fragment tags, the dispersal permutation and the Merkle anchor.

Two independent guarantees are stacked here:

* an HMAC tag per fragment, derived from a secret key, makes a fragment's
  content unforgeable without that key;
* an Ed25519 signature over the Merkle root makes the *whole-document* anchor
  publicly verifiable, so a third party can check a document without ever
  holding the embedding key.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_HASH = hashlib.sha256


def derive(key: bytes, label: str, length: int = 32) -> bytes:
    """HKDF-style subkey derivation so one master key yields separate domains."""
    return hashlib.pbkdf2_hmac("sha256", key, label.encode(), 1, dklen=length)


def fragment_tag(key: bytes, doc_id: str, index: int, digest: bytes, bits: int) -> bytes:
    """Unforgeable authenticator binding a fragment's content to its position.

    Including ``index`` is what stops a cut-and-paste attack: a fragment lifted
    from elsewhere in the same document carries a tag for the wrong position.
    """
    mac = hmac.new(derive(key, "tag"), digestmod=_HASH)
    mac.update(doc_id.encode())
    mac.update(index.to_bytes(4, "big"))
    mac.update(digest)
    return mac.digest()[: bits // 8]


def dispersal(key: bytes, doc_id: str, n: int) -> list[int]:
    """Key-driven derangement: fragment ``i``'s tag is stored in fragment ``p[i]``.

    Separating a fragment from its own authenticator is the "fragmented" half of
    the scheme. An attacker who edits fragment ``i`` must also repair ``p[i]``,
    which invalidates ``p[p[i]]``, and so on -- local forgery cascades into a
    document-wide one that the secret key makes infeasible.
    """
    if n < 2:
        return list(range(n))
    seed = derive(key, f"disperse:{doc_id}:{n}")
    perm = list(range(n))
    # Fisher-Yates driven by a deterministic SHA-256 keystream.
    stream, counter = b"", 0
    for i in range(n - 1, 0, -1):
        while len(stream) < 8:
            stream += _HASH(seed + counter.to_bytes(4, "big")).digest()
            counter += 1
        j = int.from_bytes(stream[:8], "big") % (i + 1)
        stream = stream[8:]
        perm[i], perm[j] = perm[j], perm[i]
    # Break any fixed points so no fragment ever guards itself.
    for i in range(n):
        if perm[i] == i:
            j = (i + 1) % n
            perm[i], perm[j] = perm[j], perm[i]
    return perm


def merkle_root(leaves: Sequence[bytes]) -> bytes:
    """Binary Merkle root with domain-separated leaf/node prefixes."""
    if not leaves:
        return _HASH(b"\x00empty").digest()
    level = [_HASH(b"\x00" + leaf).digest() for leaf in leaves]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            _HASH(b"\x01" + level[i] + level[i + 1]).digest()
            for i in range(0, len(level), 2)
        ]
    return level[0]


# --- Ed25519 anchor signing -------------------------------------------------

def generate_keypair() -> tuple[bytes, bytes]:
    """Return (private_raw32, public_raw32)."""
    sk = Ed25519PrivateKey.generate()
    return (
        sk.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        ),
        sk.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        ),
    )


def sign(private_raw: bytes, message: bytes) -> bytes:
    return Ed25519PrivateKey.from_private_bytes(private_raw).sign(message)


def verify_signature(public_raw: bytes, message: bytes, signature: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(public_raw).verify(signature, message)
    except (InvalidSignature, ValueError):
        return False
    return True
