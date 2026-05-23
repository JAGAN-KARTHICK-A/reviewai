from pydantic import BaseModel
from typing import Optional

class PRHead(BaseModel):
    sha: str
    ref: str

class RepoOwner(BaseModel):
    login: str

class PullRequest(BaseModel):
    number: int
    title: str
    head: PRHead

class Repository(BaseModel):
    name: str
    owner: RepoOwner

class Installation(BaseModel):
    id: int

class PRPayload(BaseModel):
    action: str
    pull_request: PullRequest
    repository: Repository
    installation: Installation

class ReviewComment(BaseModel):
    id: int
    body: str
    diff_hunk: str
    in_reply_to_id: Optional[int] = None
    user: RepoOwner

class ReviewCommentPayload(BaseModel):
    action: str
    comment: ReviewComment
    repository: Repository
    pull_request: PullRequest
    installation: Installation

class IssuePR(BaseModel):
    url: str

class Issue(BaseModel):
    number: int
    pull_request: Optional[IssuePR] = None

class IssueUser(BaseModel):
    login: str

class UserComment(BaseModel):
    body: str
    user: IssueUser

class IssueCommentPayload(BaseModel):
    action: str
    issue: Issue
    comment: UserComment
    repository: Repository
    installation: Installation
