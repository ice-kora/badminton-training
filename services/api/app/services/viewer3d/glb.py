"""Minimal synthetic_demo stick-figure GLB (static T-pose lines). No mocap."""
from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

# Compact stick joints in meters (synthetic_demo)
_JOINTS: list[tuple[str, float, float, float]] = [
    ("hips", 0.0, 0.95, 0.0),
    ("spine", 0.0, 1.25, 0.0),
    ("neck", 0.0, 1.45, 0.0),
    ("head", 0.0, 1.65, 0.0),
    ("l_shoulder", -0.22, 1.40, 0.0),
    ("l_elbow", -0.42, 1.15, 0.0),
    ("l_wrist", -0.55, 0.95, 0.05),
    ("r_shoulder", 0.22, 1.40, 0.0),
    ("r_elbow", 0.42, 1.15, 0.0),
    ("r_wrist", 0.55, 0.95, 0.05),
    ("l_hip", -0.10, 0.95, 0.0),
    ("l_knee", -0.12, 0.50, 0.02),
    ("l_ankle", -0.12, 0.05, 0.0),
    ("r_hip", 0.10, 0.95, 0.0),
    ("r_knee", 0.12, 0.50, 0.02),
    ("r_ankle", 0.12, 0.05, 0.0),
]

_BONES: list[tuple[int, int]] = [
    (0, 1),
    (1, 2),
    (2, 3),
    (2, 4),
    (4, 5),
    (5, 6),
    (2, 7),
    (7, 8),
    (8, 9),
    (0, 10),
    (10, 11),
    (11, 12),
    (0, 13),
    (13, 14),
    (14, 15),
]


def _pack_glb(gltf: dict[str, Any], bin_chunk: bytes) -> bytes:
    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    # pad to 4-byte boundary with spaces
    while len(json_bytes) % 4:
        json_bytes += b" "
    while len(bin_chunk) % 4:
        bin_chunk += b"\x00"
    total = 12 + 8 + len(json_bytes) + 8 + len(bin_chunk)
    header = struct.pack("<4sII", b"glTF", 2, total)
    json_chunk = struct.pack("<I4s", len(json_bytes), b"JSON") + json_bytes
    bin_hdr = struct.pack("<I4s", len(bin_chunk), b"BIN\x00") + bin_chunk
    return header + json_chunk + bin_hdr


def build_stick_figure_glb() -> bytes:
    """Return a tiny GLB: green line stick-figure marked synthetic_demo."""
    positions: list[float] = []
    for _name, x, y, z in _JOINTS:
        positions.extend([x, y, z])
    indices: list[int] = []
    for a, b in _BONES:
        indices.extend([a, b])

    pos_bytes = struct.pack(f"<{len(positions)}f", *positions)
    idx_bytes = struct.pack(f"<{len(indices)}H", *indices)
    # align idx after pos
    pad = (4 - (len(pos_bytes) % 4)) % 4
    bin_chunk = pos_bytes + (b"\x00" * pad) + idx_bytes

    pos_max = [0.55, 1.65, 0.05]
    pos_min = [-0.55, 0.05, 0.0]
    gltf = {
        "asset": {
            "version": "2.0",
            "generator": "badminton-ai-coach-v3-synthetic_demo",
            "extras": {
                "synthetic_demo": True,
                "banner": "工程演示基准（非教练标定）",
                "note": "static stick-figure GLB — not mocap / not coach-verified",
            },
        },
        "scene": 0,
        "scenes": [{"nodes": [0], "name": "synthetic_demo_stick"}],
        "nodes": [{"mesh": 0, "name": "StickFigure"}],
        "meshes": [
            {
                "name": "StickLines",
                "primitives": [
                    {
                        "attributes": {"POSITION": 0},
                        "indices": 1,
                        "mode": 1,  # LINES
                        "material": 0,
                    }
                ],
            }
        ],
        "materials": [
            {
                "name": "SyntheticGreen",
                "extras": {"synthetic_demo": True},
                "pbrMetallicRoughness": {
                    "baseColorFactor": [0.31, 0.78, 0.47, 1.0],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 1.0,
                },
            }
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": len(_JOINTS),
                "type": "VEC3",
                "max": pos_max,
                "min": pos_min,
            },
            {
                "bufferView": 1,
                "componentType": 5123,
                "count": len(indices),
                "type": "SCALAR",
            },
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(pos_bytes), "target": 34962},
            {
                "buffer": 0,
                "byteOffset": len(pos_bytes) + pad,
                "byteLength": len(idx_bytes),
                "target": 34963,
            },
        ],
        "buffers": [{"byteLength": len(bin_chunk)}],
    }
    return _pack_glb(gltf, bin_chunk)


def write_stick_figure_glb(path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_stick_figure_glb())
    return path
