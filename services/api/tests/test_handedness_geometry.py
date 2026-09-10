"""Dominant-side landmarks: left handedness must use LEFT_* for smash/clear metrics."""
from __future__ import annotations

from app.services.scoring.geometry import measure_metric, pick_contact_frame


def _frame(y_wrist: float, side: str = "RIGHT") -> dict:
    other = "LEFT" if side == "RIGHT" else "RIGHT"
    return {
        "landmarks": [
            {"name": f"{side}_SHOULDER", "x": 0.6, "y": 0.30, "z": 0.0, "visibility": 1.0},
            {"name": f"{side}_ELBOW", "x": 0.7, "y": 0.25, "z": 0.0, "visibility": 1.0},
            {"name": f"{side}_WRIST", "x": 0.75, "y": y_wrist, "z": 0.0, "visibility": 1.0},
            {"name": f"{other}_SHOULDER", "x": 0.4, "y": 0.30, "z": 0.0, "visibility": 1.0},
            {"name": f"{other}_ELBOW", "x": 0.3, "y": 0.40, "z": 0.0, "visibility": 1.0},
            {"name": f"{other}_WRIST", "x": 0.25, "y": 0.55, "z": 0.0, "visibility": 1.0},
            {"name": "LEFT_HIP", "x": 0.45, "y": 0.55, "z": 0.0, "visibility": 1.0},
            {"name": "RIGHT_HIP", "x": 0.55, "y": 0.55, "z": 0.0, "visibility": 1.0},
        ]
    }


def test_pick_contact_uses_dominant_wrist():
    frames = [_frame(0.40, "RIGHT"), _frame(0.10, "RIGHT"), _frame(0.05, "LEFT")]
    # right-hand: highest RIGHT wrist is frame1 (y=0.10), LEFT high on frame2 ignored
    c = pick_contact_frame(frames, handedness="right")
    assert c is frames[1]
    c_left = pick_contact_frame(frames, handedness="left")
    assert c_left is frames[2]


def test_elbow_flexion_left_uses_left_arm():
    frames = [
        _frame(0.18, "LEFT"),
    ]
    # With only LEFT arm in "contact" pose and right arm low, left handedness should measure
    v_left = measure_metric("elbow_flexion_at_contact", frames, handedness="left")
    v_right = measure_metric("elbow_flexion_at_contact", frames, handedness="right")
    assert v_left is not None
    assert v_right is not None
    # Different arms → different angles in this fixture
    assert abs(v_left - v_right) > 1.0
