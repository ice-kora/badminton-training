"""MediaPipe Pose landmark names + bone connections (33 points).

No angle standards / scoring. FakePoseExtractor uses the same 33-name list
1:1 (synthetic coords); there is no reduced-point remapping.
"""

from __future__ import annotations

POSE_LANDMARK_NAMES: list[str] = [
    "NOSE",
    "LEFT_EYE_INNER",
    "LEFT_EYE",
    "LEFT_EYE_OUTER",
    "RIGHT_EYE_INNER",
    "RIGHT_EYE",
    "RIGHT_EYE_OUTER",
    "LEFT_EAR",
    "RIGHT_EAR",
    "MOUTH_LEFT",
    "MOUTH_RIGHT",
    "LEFT_SHOULDER",
    "RIGHT_SHOULDER",
    "LEFT_ELBOW",
    "RIGHT_ELBOW",
    "LEFT_WRIST",
    "RIGHT_WRIST",
    "LEFT_PINKY",
    "RIGHT_PINKY",
    "LEFT_INDEX",
    "RIGHT_INDEX",
    "LEFT_THUMB",
    "RIGHT_THUMB",
    "LEFT_HIP",
    "RIGHT_HIP",
    "LEFT_KNEE",
    "RIGHT_KNEE",
    "LEFT_ANKLE",
    "RIGHT_ANKLE",
    "LEFT_HEEL",
    "RIGHT_HEEL",
    "LEFT_FOOT_INDEX",
    "RIGHT_FOOT_INDEX",
]

# MediaPipe Pose topology: pairs of landmark indices (i, j).
# Same order as BlazePose / mediapipe solutions.drawing_utils POSE_CONNECTIONS.
POSE_CONNECTIONS: list[tuple[int, int]] = [
    # Face
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 7),
    (0, 4),
    (4, 5),
    (5, 6),
    (6, 8),
    (9, 10),
    # Torso
    (11, 12),
    (11, 23),
    (12, 24),
    (23, 24),
    # Left arm
    (11, 13),
    (13, 15),
    (15, 17),
    (15, 19),
    (15, 21),
    (17, 19),
    # Right arm
    (12, 14),
    (14, 16),
    (16, 18),
    (16, 20),
    (16, 22),
    (18, 20),
    # Left leg
    (23, 25),
    (25, 27),
    (27, 29),
    (27, 31),
    (29, 31),
    # Right leg
    (24, 26),
    (26, 28),
    (28, 30),
    (28, 32),
    (30, 32),
]


def bone_edges(*, landmark_count: int | None = None) -> list[dict]:
    """Return bone edge descriptors clipped to available landmark count.

    Fake and MediaPipe extractors both emit 33 landmarks, so the full
    MediaPipe topology applies. If a future extractor stores fewer points,
    edges whose endpoints are out of range are dropped (document mapping
    in that extractor).
    """
    n = landmark_count if landmark_count is not None else len(POSE_LANDMARK_NAMES)
    edges: list[dict] = []
    for i, j in POSE_CONNECTIONS:
        if i >= n or j >= n:
            continue
        edges.append(
            {
                "from": i,
                "to": j,
                "from_name": POSE_LANDMARK_NAMES[i],
                "to_name": POSE_LANDMARK_NAMES[j],
            }
        )
    return edges
