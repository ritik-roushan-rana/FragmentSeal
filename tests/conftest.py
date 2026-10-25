import numpy as np
import pytest

from qlfw.config import Params
from qlfw.keystore import KeyFile


@pytest.fixture(scope="session")
def keys() -> KeyFile:
    return KeyFile.generate()


@pytest.fixture
def page() -> np.ndarray:
    """A synthetic document: white background, dark text-like strokes, a seal."""
    rng = np.random.default_rng(7)
    img = np.full((320, 256), 250, dtype=np.uint8)
    for y in range(24, 300, 18):
        width = rng.integers(60, 200)
        img[y:y + 7, 20:20 + width] = rng.integers(10, 70)
    yy, xx = np.mgrid[0:320, 0:256]
    seal = (yy - 250) ** 2 + (xx - 200) ** 2
    img[(seal > 900) & (seal < 1300)] = 30
    return img


@pytest.fixture(params=["dct", "lsb"])
def params(request) -> Params:
    return Params(carrier=request.param, fragment=32, tag_bits=64)
