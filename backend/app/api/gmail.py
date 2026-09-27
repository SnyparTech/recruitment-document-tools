import logging

from fastapi import APIRouter, HTTPException, status

from app.pipeline.recruitment_pipeline import RecruitmentPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gmail", tags=["Gmail"])

_pipeline = RecruitmentPipeline()


@router.post("/sync", summary="Pull new Gmail messages and run the full recruitment pipeline on each")
async def sync_gmail(max_results: int = 20):
    try:
        results = await _pipeline.run(max_results=max_results)
    except Exception as exc:
        logger.exception("Gmail sync failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={
            "error": "GMAIL_SYNC_FAILED",
            "message": f"Could not sync Gmail: {exc}",
        })
    return {"processed": len(results), "results": [r.__dict__ for r in results]}
