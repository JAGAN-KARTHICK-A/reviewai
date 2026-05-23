import time
from datetime import datetime
import jwt
import httpx
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from core.config import settings
import base64

class GithubClient():
    def __init__(self):
        with open(settings.GITHUB_PRIVATE_KEY_PATH, "rb") as f:
            pem_data = f.read()

        self.app_id = settings.GITHUB_APP_ID
        self.private_key = load_pem_private_key(pem_data, password=None)

        self._token_cache:str = None
        self._token_expires_at:float = 0
    def _build_jwt(self):
        now = int(time.time())
        payload = {
            "iat":now-60,
            "exp":now+600,
            "iss":self.app_id
        }
        return jwt.encode(payload, self.private_key, algorithm="RS256")
    async def _get_installation_token(self, installation_id:int):
        if self._token_cache and time.time() < self._token_expires_at - 60:
            return self._token_cache
        
        jwt_payload = self._build_jwt()
        async with httpx.AsyncClient() as cl:
            resp = await cl.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization" : f"Bearer {jwt_payload}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version" : "2026-03-10"
                }
            )
            resp.raise_for_status()
            data = resp.json()
        
        self._token_cache = data["token"]
        expires = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        self._token_expires_at = expires.timestamp()

        return self._token_cache
    def _determine_review_event(self, issues: list[dict]):
        severities = {issue["severity"] for issue in issues}
        if not issues:
            return "APPROVE"
        elif "critical" in severities:
            return "REQUEST_CHANGES"
        else:
            return "COMMENT"
    async def get_pull_req_diff(self, owner:str, repo:str, pr_number:int, installation_id:int):
        token = await self._get_installation_token(installation_id)
        async with httpx.AsyncClient() as cl:
            resp = await cl.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
                headers={
                    "Authorization" : f"Bearer {token}",
                    "Accept": "application/vnd.github.diff",
                    "X-GitHub-Api-Version" : "2026-03-10"
                }
            )
            resp.raise_for_status()
            return resp.text
    async def post_review(self, owner:str, repo:str, pr_number:int, commit_sha:str, installation_id:int, comments: list[dict]):
        token = await self._get_installation_token(installation_id)

        github_comments = []
        for issue in comments:
            severity_label = {
                "critical" : "[🔥] CRITICAL",
                "warning" : "[⚠️] WARNING",
                "suggestion" : "[💡] SUGGESTION"
            }.get(issue["severity"], issue["severity"].upper())
            
            body = (
                f"**{severity_label} - {issue['category'].upper()}**\n\n"
                f"{issue['comment']}"
            )

            github_comments.append({
                "path": issue["file_path"],
                "line": issue["new_file_line"],
                "side":"RIGHT",
                "body": body
            })
        
        event = self._determine_review_event(comments)

        async with httpx.AsyncClient() as cl:
            resp = await cl.post(
                f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version" : "2026-03-10"
                },
                json = {
                    "commit_id": commit_sha,
                    "event": event,
                    "comments": github_comments
                }
            )
            resp.raise_for_status()
    async def get_comment(self, owner:str, repo:str, comment_id:int, installation_id:int):
        token = await self._get_installation_token(installation_id)
        async with httpx.AsyncClient() as cl:
            resp = await cl.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls/comments/{comment_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2026-03-10"
                }
            )
            resp.raise_for_status()
            return resp.json()["body"]
    async def post_reply(self, owner:str, repo:str, pr_number:int, comment_id:int, installation_id:int, body: str):
        token = await self._get_installation_token(installation_id)
        async with httpx.AsyncClient() as cl:
            resp = await cl.post(
                f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments/{comment_id}/replies",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2026-03-10"
                },
                json={"body": body}
            )
            resp.raise_for_status()
    async def post_summary(self, owner:str, repo:str, pr_number:int, installation_id:int, body:str):
        token = await self._get_installation_token(installation_id)
        async with httpx.AsyncClient() as cl:
            resp = await cl.post(
                f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2026-03-10"
                },
                json={"body": body}
            )
            resp.raise_for_status()
    async def post_error_comment(self, owner:str, repo:str, pr_number:int, installation_id:int, error:str):
        body = (
            "## ⚠️ AI Code Review — Failed\n\n"
            "The automated review encountered an error and could not complete.\n\n"
            f"**Error:** `{error}`\n\n"
            "You can re-trigger the review by closing and reopening this PR, "
            "or pushing a new commit."
        )
        await self.post_summary(owner, repo, pr_number, installation_id, body)
    async def post_error_reply(self, owner:str, repo:str, pr_number:int, comment_id:int, installation_id:int, error:str):
        body = (
            "## ⚠️ AI Code Review — Failed\n\n"
            "The automated review encountered an error and could not complete.\n\n"
            f"**Error:** `{error}`\n\n"
            "You can re-trigger the review by making another comment."
        )
        await self.post_reply(owner, repo, pr_number, comment_id, installation_id, body)
    async def get_pull_request(self, owner:str, repo:str, pr_number:str, installation_id:int):
        token = await self._get_installation_token(installation_id)
        async with httpx.AsyncClient() as cl:
            resp = await cl.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2026-03-10"
                }
            )
            resp.raise_for_status()
            return resp.json()
    async def get_file_content(self, owner:str, repo:str, file_path:str, ref:str, installation_id:int):
        token = await self._get_installation_token(installation_id)
        async with httpx.AsyncClient() as cl:
            resp = await cl.get(
                f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2026-03-10"
                },
                params={"ref":ref}
            )

            if resp.status_code == 404:
                return None
            
            resp.raise_for_status()
            data = resp.json()

            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")

github_client = GithubClient()
