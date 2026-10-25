import numpy as np
import pytest

from qlfw import crypto


def test_dispersal_is_a_derangement():
    perm = crypto.dispersal(b"k" * 32, "doc", 256)
    assert sorted(perm) == list(range(256)), "must be a permutation"
    assert all(perm[i] != i for i in range(256)), "no fragment may guard itself"


def test_dispersal_is_key_and_document_bound():
    a = crypto.dispersal(b"a" * 32, "doc", 64)
    assert a != crypto.dispersal(b"b" * 32, "doc", 64)
    assert a != crypto.dispersal(b"a" * 32, "other", 64)
    assert a == crypto.dispersal(b"a" * 32, "doc", 64), "must be deterministic"


def test_tag_binds_content_and_position():
    k, d = b"k" * 32, b"\x11" * 32
    base = crypto.fragment_tag(k, "doc", 5, d, 64)
    assert base != crypto.fragment_tag(k, "doc", 6, d, 64), "position must matter"
    assert base != crypto.fragment_tag(k, "doc", 5, b"\x22" * 32, 64)
    assert base != crypto.fragment_tag(b"j" * 32, "doc", 5, d, 64)
    assert len(base) == 8


def test_merkle_root_detects_any_leaf_change():
    leaves = [bytes([i]) * 8 for i in range(9)]  # odd count exercises promotion
    root = crypto.merkle_root(leaves)
    for i in range(len(leaves)):
        swapped = list(leaves)
        swapped[i] = b"\xff" * 8
        assert crypto.merkle_root(swapped) != root


def test_merkle_root_is_order_sensitive():
    leaves = [b"a" * 8, b"b" * 8]
    assert crypto.merkle_root(leaves) != crypto.merkle_root(leaves[::-1])


def test_signature_round_trip():
    sk, pk = crypto.generate_keypair()
    sig = crypto.sign(sk, b"anchor")
    assert crypto.verify_signature(pk, b"anchor", sig)
    assert not crypto.verify_signature(pk, b"anchor!", sig)
    _, other = crypto.generate_keypair()
    assert not crypto.verify_signature(other, b"anchor", sig)
