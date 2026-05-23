from fastapi import APIRouter, Request, Header
from core.config import settings
from models import PRPayload
from services.handle import handle_pr

router = APIRouter()

@router.post("/webhook")
async def webhook(req: Request, x_github_event: str = Header(None)):
    payload = await req.json()

    if (x_github_event == "pull_request"):
        payload = PRPayload(**await payload)
        handle_pr(payload)

    return {"status":"success"}

