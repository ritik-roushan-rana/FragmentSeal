"""Scheme parameters. These travel with the document inside the QR manifest."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

#: Side length in pixels of one authentication fragment (macro-block).
#: Must be a multiple of 8 so it tiles whole DCT sub-blocks.
DEFAULT_FRAGMENT = 32

#: Bits of HMAC tag retained per fragment. 64 bits keeps forgery odds at 2^-64
#: per fragment while still fitting one DCT-QIM payload exactly.
DEFAULT_TAG_BITS = 64

#: Carrier identifiers as written into the QR manifest. Never renumber these:
#: an old document's QR must keep meaning what it meant when it was issued.
CARRIER_CODES = {"dct": 0, "lsb": 1}


@dataclass(frozen=True)
class Params:
    fragment: int = DEFAULT_FRAGMENT
    tag_bits: int = DEFAULT_TAG_BITS
    carrier: str = "dct"          # "dct" (semi-fragile) or "lsb" (fragile)
    strength: float = 8.0         # QIM quantisation step; ignored by "lsb"
    grid_rows: int = 0            # filled in at embed time
    grid_cols: int = 0

    def __post_init__(self) -> None:
        # The QR stores the step in quarter-level units, so quantise it here:
        # embedding with a strength the manifest cannot express exactly would
        # leave the verifier decoding against the wrong lattice.
        object.__setattr__(self, "strength", round(self.strength * 4) / 4)
        if not 0 < self.strength <= 63.75:
            raise ValueError(f"strength must be in 0..63.75, got {self.strength}")
        if self.fragment % 8:
            raise ValueError(f"fragment must be a multiple of 8, got {self.fragment}")
        if self.tag_bits % 8 or not 0 < self.tag_bits <= 256:
            raise ValueError(f"tag_bits must be a byte-multiple in 1..256, got {self.tag_bits}")
        if not 0 < self.fragment <= 255:
            raise ValueError(f"fragment must be in 1..255, got {self.fragment}")
        if self.carrier not in CARRIER_CODES:
            raise ValueError(f"unknown carrier {self.carrier!r}")

    @property
    def n_fragments(self) -> int:
        return self.grid_rows * self.grid_cols

    def with_grid(self, rows: int, cols: int) -> "Params":
        return dataclasses.replace(self, grid_rows=rows, grid_cols=cols)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Params":
        fields = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in fields})
