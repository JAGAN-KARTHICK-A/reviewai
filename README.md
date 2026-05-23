# ReviewAI — AI-Powered GitHub Code Reviewer

A production-grade GitHub App that automatically reviews pull requests using Claude (Anthropic), posts inline comments, and responds to developer follow-up questions.

## Features

- **Automatic PR reviews** — triggers on every opened or updated pull request
- **Inline comments** — posts issues directly on the changed lines with severity labels
- **Interactive replies** — responds to follow-up questions on its own comments
- **`/review` command** — re-trigger a review with optional custom focus instructions
- **PR summary** — posts an overall review summary on every PR
- **Smart filtering** — only reviews added lines, skips ignored files
- **Multi-file context** — fetches full file content for cross-file issue detection
- **Severity-based outcomes** — requests changes on critical issues, approves clean PRs
- **Repo configuration** — per-repo `.reviewai.yml` for custom rules and ignore patterns
- **Error handling** — posts fallback comments if the review pipeline fails

## Tech Stack

- **Backend** — Python, FastAPI
- **LLM** — Anthropic Claude (claude-sonnet-4-5)
- **Auth** — GitHub App JWT authentication
- **Webhooks** — GitHub Webhooks with HMAC-SHA256 signature verification

## Architecture

```
GitHub PR event → FastAPI webhook receiver → signature verification
    → diff fetched via GitHub API → parsed into hunks
        → each hunk reviewed by Claude → issues mapped to line numbers
            → inline review posted → PR summary posted
```

## Setup

### 1. Create a GitHub App

Go to GitHub → Settings → Developer settings → GitHub Apps → New.

Required permissions:
- Contents: Read
- Pull requests: Read & Write
- Issues: Read & Write
- Metadata: Read (mandatory)

Subscribe to events: Pull request, Pull request review comment, Issue comment

### 2. Configure environment

```bash
cp .env.example .env
```

Fill in:
```
GITHUB_APP_ID=your_app_id
GITHUB_WEBHOOK_SECRET=your_webhook_secret
GITHUB_PRIVATE_KEY_PATH=./github-app.pem
ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Run locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Forward webhooks locally
smee --url https://smee.io/your-channel --target http://localhost:8000/webhook/github
```

## Usage

### Automatic review
Open or update any pull request on an installed repository. The bot reviews within seconds.

### Manual review
Comment `/review` on any PR to trigger a fresh review.

### Custom focus
```
/review focus on security vulnerabilities only
/review check for memory leaks
/review is this thread-safe?
```

### Repo configuration
Add `.reviewai.yml` to your repo root:
```yaml
severity_threshold: warning
auto_approve: true
ignored_files:
  - "migrations/*"
  - "*.min.js"
language_hints:
  python: "Django application, check for ORM misuse"
max_comments: 15
```

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app
│   ├── github_client.py     # GitHub API wrapper with JWT auth
│   ├── diff_parser.py       # Unified diff parser
│   ├── prompt_builder.py    # LLM prompt construction
│   └── config_loader.py     # .reviewai.yml parser
├── services/
│   ├── handle/              # PR webhook handler
│   ├── reply/               # Review comment reply handler
│   ├── issue_comment/       # /review command handler
│   ├── pipeline.py          # Core review pipeline
│   ├── summary.py           # PR summary builder
│   └── ai/                  # LLM interface
├── core/
│   └── config.py            # Settings loader
└── models.py                # Pydantic request models
```

## Environment Variables

| Variable | Description |
|---|---|
| `GITHUB_APP_ID` | Your GitHub App's numeric ID |
| `GITHUB_WEBHOOK_SECRET` | Secret for HMAC webhook verification |
| `GITHUB_PRIVATE_KEY_PATH` | Path to your `.pem` private key file |
| `ANTHROPIC_API_KEY` | Anthropic API key |

## Resume Bullet

> Built a GitHub App (Python, FastAPI, Anthropic Claude) that automatically reviews pull requests by parsing unified diffs, posting inline comments with severity scoring, and responding to developer follow-up questions. Implemented JWT-based GitHub App auth, HMAC webhook verification, multi-file context analysis, and per-repo YAML configuration. Deployed live as a GitHub App.