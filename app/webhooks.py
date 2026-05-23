import hmac
import hashlib
from core.config import settings
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from app.github_client import github_client
from services.handle import handle_pr, handle_review_comment, handle_issue_comment
from models import PRPayload, ReviewCommentPayload, IssueCommentPayload
import json

router = APIRouter()

def verify_signature(payload:bytes, signature:str, secret:str) -> bool:
    expected = "sha256="+hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

@router.post("/webhook/github")
async def github_webhook(request: Request, bg_tasks: BackgroundTasks):
    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_signature(payload, signature, settings.GITHUB_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid Signature")
    
    event = request.headers.get("X-GitHub-Event", "")
    data = await request.json()

    if event == "pull_request" and data.get("action") in ["opened", "synchronize"]:
        data = PRPayload(**data)
        bg_tasks.add_task(handle_pr, data)
    
    elif event == "pull_request_review_comment" and data.get("action") == "created":
        data = ReviewCommentPayload(**data)
        commenter = data.comment.user.login
        if "[bot]" not in commenter:
            bg_tasks.add_task(handle_review_comment, data)
    
    elif event == "issue_comment" and data.get("action") == "created":
        data = IssueCommentPayload(**data)
        commenter = data.comment.user.login
        if "[bot]" not in commenter:
            bg_tasks.add_task(handle_issue_comment, data)

    return {"status":"accepted"}
