from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """
    Liveness + public client config.

    video_ttl_days is single-source-of-truth here: the miniprogram privacy
    badge ("原片约 N 天删除") renders from this value instead of a hardcoded
    duplicate that would drift from the server's purge policy.
    """
    settings = get_settings()
    return {
        "status": "ok",
        "service": "badminton-ai-coach-api",
        "video_ttl_days": int(settings.video_ttl_days),
    }
