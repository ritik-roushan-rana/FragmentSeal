"""SHA-256 Merkle tree with inclusion proofs.

Leaves are hex SHA-256 digests of document fragments, in fragment order.
Internal nodes hash the concatenation of child *bytes* with a domain-separation
prefix so that leaf and node pre-images can never collide. An odd node count at
any level duplicates the last node (Bitcoin-style).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_leaf(fragment_hash_hex: str) -> str:
    return sha256_hex(LEAF_PREFIX + bytes.fromhex(fragment_hash_hex))


def hash_node(left_hex: str, right_hex: str) -> str:
    return sha256_hex(NODE_PREFIX + bytes.fromhex(left_hex) + bytes.fromhex(right_hex))


@dataclass
class MerkleTree:
    leaves: list[str]
    levels: list[list[str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.leaves:
            self.levels = [[sha256_hex(b"")]]
            return
        level = [hash_leaf(h) for h in self.leaves]
        self.levels = [level]
        while len(level) > 1:
            if len(level) % 2 == 1:
                level = level + [level[-1]]
            level = [hash_node(level[i], level[i + 1]) for i in range(0, len(level), 2)]
            self.levels.append(level)

    @property
    def root(self) -> str:
        return self.levels[-1][0]

    def proof(self, index: int) -> list[dict[str, str]]:
        """Audit path for leaf `index`: list of {position, hash} siblings."""
        if index < 0 or index >= len(self.leaves):
            raise IndexError("leaf index out of range")
        path: list[dict[str, str]] = []
        idx = index
        for level in self.levels[:-1]:
            working = level + [level[-1]] if len(level) % 2 == 1 else level
            sibling = idx ^ 1
            position = "right" if sibling > idx else "left"
            path.append({"position": position, "hash": working[sibling]})
            idx //= 2
        return path


def verify_proof(fragment_hash_hex: str, proof: list[dict[str, str]], root: str) -> bool:
    current = hash_leaf(fragment_hash_hex)
    for step in proof:
        if step["position"] == "right":
            current = hash_node(current, step["hash"])
        else:
            current = hash_node(step["hash"], current)
    return current == root


def build_root(fragment_hashes: list[str]) -> str:
    return MerkleTree(fragment_hashes).root
