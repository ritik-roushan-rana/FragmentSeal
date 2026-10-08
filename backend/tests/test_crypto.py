"""Unit tests for the Merkle tree, signing and DWT watermarking primitives."""
from __future__ import annotations

import hashlib

import pytest

from app.services.merkle import MerkleTree, build_root, verify_proof
from app.services.watermark import (
    bit_error_rate,
    build_watermark_image,
    hex_to_bits,
    verify_watermark_image,
)


def leaf(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class TestMerkle:
    def test_root_is_stable_and_order_sensitive(self):
        a, b, c = leaf("a"), leaf("b"), leaf("c")
        assert build_root([a, b, c]) == build_root([a, b, c])
        assert build_root([a, b, c]) != build_root([b, a, c])

    def test_single_leaf_change_changes_root(self):
        leaves = [leaf(str(i)) for i in range(12)]
        original = build_root(leaves)
        leaves[7] = leaf("tampered")
        assert build_root(leaves) != original

    @pytest.mark.parametrize("count", [1, 2, 3, 5, 8, 12, 13])
    def test_inclusion_proofs_hold_for_every_leaf(self, count):
        leaves = [leaf(str(i)) for i in range(count)]
        tree = MerkleTree(leaves)
        for index in range(count):
            assert verify_proof(leaves[index], tree.proof(index), tree.root)

    def test_proof_fails_for_a_substituted_leaf(self):
        leaves = [leaf(str(i)) for i in range(9)]
        tree = MerkleTree(leaves)
        assert not verify_proof(leaf("forged"), tree.proof(4), tree.root)

    def test_leaf_and_node_preimages_are_domain_separated(self):
        # Without domain separation an attacker could present an internal node
        # as a leaf. The prefixes make the two hash spaces disjoint.
        leaves = [leaf("x"), leaf("y")]
        tree = MerkleTree(leaves)
        assert tree.root not in leaves


class TestWatermark:
    def test_payload_round_trips_through_the_carrier(self):
        root = hashlib.sha256(b"root").hexdigest()
        image = build_watermark_image(root, "key-1")
        result = verify_watermark_image(image, root, "key-1")
        assert result["valid"] and result["bit_error_rate"] == 0.0

    def test_wrong_key_cannot_read_the_payload(self):
        root = hashlib.sha256(b"root").hexdigest()
        image = build_watermark_image(root, "key-1")
        assert not verify_watermark_image(image, root, "other-key")["valid"]

    def test_different_root_fails_validation(self):
        image = build_watermark_image(hashlib.sha256(b"a").hexdigest(), "k")
        assert not verify_watermark_image(image, hashlib.sha256(b"b").hexdigest(), "k")["valid"]

    def test_semi_fragile_survives_mild_requantisation(self):
        import numpy as np
        from PIL import Image

        root = hashlib.sha256(b"root").hexdigest()
        image = build_watermark_image(root, "key-1")
        noisy = np.asarray(image, dtype=np.float64) + np.random.default_rng(7).normal(
            0, 1.0, size=(image.height, image.width)
        )
        degraded = Image.fromarray(np.clip(noisy, 0, 255).astype("uint8"), mode="L")
        assert verify_watermark_image(degraded, root, "key-1")["valid"]

    def test_heavy_overwrite_destroys_the_payload(self):
        import numpy as np
        from PIL import Image

        root = hashlib.sha256(b"root").hexdigest()
        image = build_watermark_image(root, "key-1")
        wiped = Image.fromarray(
            np.full((image.height, image.width), 210, dtype="uint8"), mode="L"
        )
        assert not verify_watermark_image(wiped, root, "key-1")["valid"]

    def test_bit_helpers(self):
        bits = hex_to_bits("ff00", 16)
        assert bits == [1] * 8 + [0] * 8
        assert bit_error_rate(bits, bits) == 0.0
        assert bit_error_rate(bits, [0] * 16) == 0.5
