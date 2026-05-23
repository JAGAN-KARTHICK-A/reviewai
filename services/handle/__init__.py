from models import PRPayload, ReviewCommentPayload, IssueCommentPayload
from app.github_client import github_client
from app.diff_parser import parse_diff
from services.ai import llm_interface
from services.ai.prompt_builder import build_summary
from services.review import run_review_pipeline
import traceback

REVIEW_COMMENTS = {"/review", "/reviewai", "/bot review"}

async def handle_pr(payload: PRPayload):
    owner = payload.repository.owner.login
    repo = payload.repository.name
    pr_number = payload.pull_request.number
    commit_sha = payload.pull_request.head.sha
    installation_id = payload.installation.id

    print(f"Reviewing PR#{pr_number} in {owner}/{repo} @ {commit_sha[:7]}")

    try:
        await run_review_pipeline(owner, repo, pr_number, commit_sha, installation_id)
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(traceback.format_exc())
        try:
            await github_client.post_error_comment(owner, repo, pr_number, installation_id, error_msg)
        except:
            pass
    
    print("Finished PR review")


async def handle_review_comment(payload: ReviewCommentPayload):
    owner = payload.repository.owner.login
    repo = payload.repository.name
    pr_number = payload.pull_request.number
    installation_id = payload.installation.id

    comment = payload.comment
    comment_id = comment.id
    user_question = comment.body

    diff_hunk = comment.diff_hunk

    in_reply_to_id = comment.in_reply_to_id

    try:
        llm_reply = await llm_interface.review_comment(owner, repo, installation_id, diff_hunk, user_question, in_reply_to_id)
        await github_client.post_reply(owner, repo, pr_number, comment_id, installation_id, llm_reply)
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(traceback.format_exc())
        try:
            await github_client.post_error_reply(owner, repo, pr_number, comment_id, installation_id, error_msg)
        except:
            pass

    print(f"Replied to comment {comment_id} on PR#{pr_number}")

async def handle_issue_comment(payload: IssueCommentPayload):
    command = payload.comment.body.strip().lower()

    custom_instruction = None
    triggered = False
    for comment in REVIEW_COMMENTS:
        if command.startswith(comment):
            triggered = True
            reminder = command[len(comment):].strip()
            if reminder: custom_instruction = reminder
            break
    
    if not triggered: return

    if payload.issue.pull_request is None: return

    owner = payload.repository.owner.login
    repo = payload.repository.name
    pr_number = payload.issue.number
    installation_id = payload.installation.id

    print(f"Manual review triggered for PR#{pr_number} by {payload.comment.user.login}")

    try:
        if custom_instruction:
            ack = (
                f"## 🔍 AI Code Review\n\n"
                f"Review requested with custom focus: **{custom_instruction}**\n\n"
                f"Analyzing your PR now..."
            )
        else:
            ack = "## 🔍 AI Code Review\n\nReview requested — analyzing your PR now..."
            
        await github_client.post_summary(
            owner, repo, pr_number, installation_id,
            ack
        )

        pr_data = await github_client.get_pull_request(owner, repo, pr_number, installation_id)
        commit_sha = pr_data["head"]["sha"]

        await run_review_pipeline(owner, repo, pr_number, commit_sha, installation_id, custom_instruction)
        
    except Exception as e:
        import traceback
        print(f"Manual review failed: {e}")
        print(traceback.format_exc())
        await github_client.post_error_comment(
            owner, repo, pr_number, installation_id, str(e)
        )



