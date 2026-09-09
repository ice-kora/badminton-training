"""V3 offline 3D standard-action viewer (manifest + optional GLB). Not realtime."""

from app.services.viewer3d.manifest import (
    PLAYBACK_SPEEDS,
    VIEWER3D_NOTICE,
    build_viewer3d_manifest,
)

__all__ = [
    "PLAYBACK_SPEEDS",
    "VIEWER3D_NOTICE",
    "build_viewer3d_manifest",
]
