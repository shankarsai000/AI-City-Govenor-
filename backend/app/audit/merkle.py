from __future__ import annotations

from typing import TypedDict

from app.audit.hashing import canonical_json, sha256_hex


class MerkleSibling(TypedDict):
    position: str
    hash: str


def _pair_hash(left: str, right: str) -> str:
    return sha256_hex(canonical_json({"left": left, "right": right}))


def compute_merkle_root(leaf_hashes: list[str]) -> str | None:
    if not leaf_hashes:
        return None

    layer = leaf_hashes[:]
    while len(layer) > 1:
        next_layer: list[str] = []
        for index in range(0, len(layer), 2):
            left = layer[index]
            right = layer[index + 1] if index + 1 < len(layer) else left
            next_layer.append(_pair_hash(left, right))
        layer = next_layer
    return layer[0]


def build_merkle_proof(leaf_hashes: list[str], target_index: int) -> tuple[str | None, list[MerkleSibling]]:
    if not leaf_hashes or target_index < 0 or target_index >= len(leaf_hashes):
        return None, []

    proof: list[MerkleSibling] = []
    index = target_index
    layer = leaf_hashes[:]

    while len(layer) > 1:
        if index % 2 == 0:
            sibling_index = index + 1 if index + 1 < len(layer) else index
            proof.append({"position": "right", "hash": layer[sibling_index]})
        else:
            sibling_index = index - 1
            proof.append({"position": "left", "hash": layer[sibling_index]})

        next_layer: list[str] = []
        for pair_index in range(0, len(layer), 2):
            left = layer[pair_index]
            right = layer[pair_index + 1] if pair_index + 1 < len(layer) else left
            next_layer.append(_pair_hash(left, right))
        layer = next_layer
        index //= 2

    return layer[0], proof


def verify_merkle_proof(leaf_hash: str, proof: list[MerkleSibling], expected_root: str) -> bool:
    current_hash = leaf_hash
    for sibling in proof:
        if sibling["position"] == "left":
            current_hash = _pair_hash(sibling["hash"], current_hash)
        else:
            current_hash = _pair_hash(current_hash, sibling["hash"])
    return current_hash == expected_root
