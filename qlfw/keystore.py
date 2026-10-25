"""Key file handling. One file holds both keys the scheme needs.

The HMAC key is the *verification secret*: whoever holds it can authenticate
fragments. The Ed25519 pair is the *issuer identity*: its public half lets
anyone confirm who issued a document, without being able to verify or forge
fragments. Keeping them separate is what lets a document be publicly
attributable but privately verifiable.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from . import crypto


@dataclass
class KeyFile:
    hmac_key: bytes
    sign_sk: bytes
    sign_pk: bytes

    @classmethod
    def generate(cls) -> "KeyFile":
        sk, pk = crypto.generate_keypair()
        return cls(hmac_key=os.urandom(32), sign_sk=sk, sign_pk=pk)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "hmac": self.hmac_key.hex(),
            "sign_sk": self.sign_sk.hex(),
            "sign_pk": self.sign_pk.hex(),
        }, indent=2) + "\n")
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600: it is a secret

    @classmethod
    def load(cls, path: str | Path) -> "KeyFile":
        d = json.loads(Path(path).read_text())
        return cls(hmac_key=bytes.fromhex(d["hmac"]),
                   sign_sk=bytes.fromhex(d["sign_sk"]),
                   sign_pk=bytes.fromhex(d["sign_pk"]))
