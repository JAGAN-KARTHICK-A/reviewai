from app.diff_parser import DiffHunk
from app.github_client import github_client

SYSTEM_PROMPT_DIFF = SYSTEM_PROMPT = """You are a strict and precise senior code reviewer.

Your task is to analyze a Git diff hunk and identify ONLY real, actionable issues.
Do NOT speculate. Do NOT invent problems. If unsure, skip it.

Lines in the diff are labeled:
- [NEW] (pos=N) — newly added lines. ONLY comment on these. Use their pos=N as "position".
- [REMOVED] — deleted lines. Use for context only, never assign a position to these.
- [CONTEXT] — unchanged lines. Use for context only, never assign a position to these.

Focus ONLY on:
- Security vulnerabilities (e.g., SQL injection, hardcoded secrets, XSS)
- Functional bugs and logic errors
- Resource leaks (files, DB connections, memory, etc.)
- Performance issues (inefficient loops, unnecessary operations)
- Missing or incorrect error handling

Ignore:
- Minor style issues unless they affect readability or correctness
- Anything outside the provided diff

STRICT OUTPUT RULES:
- Return ONLY a valid JSON array
- Do NOT include markdown, explanations, or extra text
- Do NOT wrap in code blocks
- Output must be directly parseable with json.loads()

Each issue must follow EXACTLY this schema:
{
  "position": <integer from pos=N of a [NEW] line only>,
  "severity": "critical" | "warning" | "suggestion",
  "category": "security" | "bug" | "performance" | "style",
  "comment": "<concise explanation + specific fix>"
}

Severity guidelines:
- critical → security issues, crashes, data loss
- warning → likely bugs or bad practices
- suggestion → improvements with low risk

Additional rules:
- Use ONLY positions that appear in the diff as [pos=N]
- One issue per object, no grouping
- Keep comments short, concrete, and actionable
- Prefer fewer high-quality findings over many weak ones

If there are NO valid issues, return: []"""

REPLY_SYSTEM_PROMPT = """You are an AI code reviewer assistant. 
A developer is asking a follow-up question about a code review comment you previously made.
Be concise, helpful, and specific. Reference the actual code when relevant.
If suggesting a fix, show a short code snippet."""


def build_prompt_diff(hunk: DiffHunk, custom_instruction: str | None = None, file_context: dict[str, str] | None = None, language_hint: str | None = None) -> str:
    lines_text = ""
    for dl in hunk.lines:
        if dl.line_type == "added":
            lines_text += f"[pos={dl.position}][NEW] {dl.content}\n"
        elif dl.line_type == "removed":
            lines_text += f"[REMOVED] {dl.content} \n"
        else:
            lines_text += f"[CONTEXT] {dl.content} \n"
    
    context_block = ""
    if file_context:
        other_files = {
            path: content
            for path, content in file_context.items()
            if path != hunk.file_path
        }
        if other_files:
            context_block = "\n\n--- OTHER CHANGED FILES (for context only) ---\n"
            for path, content in other_files.items():
                truncated = content[:3000]
                if len(content) > 3000:
                    truncated += f"\n... (truncated, {len(content)} chars total)"
                context_block += f"\n### {path}\n{truncated}\n"
            context_block += "--- END CONTEXT ---\n"

        if hunk.file_path in file_context:
            full_file = file_context[hunk.file_path][:5000]
            context_block += (
                f"\n\n--- FULL CURRENT FILE: {hunk.file_path} ---\n"
                f"{full_file}\n"
                f"--- END FILE ---\n"
            )
    
    instruction_block = ""
    if language_hint:
        instruction_block += f"\nProject context: {language_hint}\n"
    if custom_instruction:
        instruction_block = (
            f"\nAdditional instructions from the developer:\n"
            f"{custom_instruction}\n"
            f"Prioritize findings that match these instructions, "
            f"but still report critical security or bug issues regardless.\n"
        )
    
    return f""" File: {hunk.file_path} (starting at line {hunk.new_start_line})
                {instruction_block}\n\n
                f"{context_block}\n\n"
                Diff hunk — only comment on [NEW] lines, using their [pos=N] number:
                {lines_text}
            """

async def build_prompt_reply_comment(owner:str, repo:str, installation_id:int, diff_hunk: str, user_question: str, in_reply_to_id: int):
    context = f"""Code context (diff hunk):
    {diff_hunk}

    Developer's question:
    {user_question}"""

    if in_reply_to_id != None:
        original = await github_client.get_comment(owner, repo, in_reply_to_id, installation_id)
        context = f"""Original review comment:
        {original}

        Code context (diff hunk):
        {diff_hunk}

        Developer's follow-up question:
        {user_question}
        """
    return context

def build_summary(all_issues: list[dict], posted_count: int | None = None, threshold: str | None = None):
    if not all_issues:
        return (
            "## ✅ AI Code Review\n\n"
            "No issues found. Looks clean!"
        )
    counts = {"critical":0, "warning":0, "suggestion":0}
    for issue in all_issues:
        severity = issue.get("severity", "suggestion")
        counts[severity] = counts.get(severity, 0) + 1
    
    parts = []
    if counts["critical"]:
        parts.append(f"🔥 **{counts['critical']} critical**")
    if counts["warning"]:
        parts.append(f"⚠️ **{counts['warning']} warnings**")
    if counts["suggestion"]:
        parts.append(f"💡 **{counts['suggestion']} suggestions**")
    
    header = "## 🔍 AI Code Review\n\n"
    header += "Found " + ", ".join(parts) + "\n\n"

    if posted_count is not None and posted_count < len(all_issues):
        header += (
            f"> ℹ️ Showing {posted_count} of {len(all_issues)} issues "
            f"(threshold: `{threshold}`, configure in `.reviewai.yml`)\n\n"
        )

    by_file = {}
    for issue in all_issues:
        file_path = issue.get("file_path", "unknown")
        if file_path not in by_file:
            by_file[file_path] = []
        by_file[file_path].append(issue)
    
    body = ""
    severity_icon = {
        "critical": "🔥",
        "warning": "⚠️",
        "suggestion": "💡"
    }

    for file_path, issues in by_file.items():
        body += f"### `{file_path}`\n"
        for issue in issues:
            icon = severity_icon.get(issue["severity"], "•")
            body += (
                f"- {icon} **{issue['severity'].upper()}** "
                f"(line {issue['new_file_line']}): "
                f"{issue['comment']}\n"
            )
        body += "\n"
    
    return header + body
