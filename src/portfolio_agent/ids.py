from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256_bytes(encoded)


def dataset_id_for(payload: bytes, namespace: str = "") -> str:
    namespaced = namespace.encode("utf-8") + b"\0" + payload
    return f"ds_{sha256_bytes(namespaced)[:24]}"
