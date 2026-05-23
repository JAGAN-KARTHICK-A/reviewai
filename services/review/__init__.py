from app.github_client import github_client
from app.diff_parser import parse_diff
from services.ai import llm_interface
from services.ai.prompt_builder import build_summary
from app.config_loader import parse_config, DEFAULT_CONFIG
import fnmatch

def should_ignore(file_path: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(file_path, pattern):
            return True
    return False

def get_language_hint(file_path: str, hints: dict[str, str]) -> str | None:
    ext_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".go": "go", ".rs": "rust", ".java": "java", ".rb": "ruby"
    }
    ext = "." + file_path.rsplit(".", 1)[-1] if "." in file_path else ""
    language = ext_map.get(ext)
    return hints.get(language) if language else None

SEVERITY_ORDER = {"suggestion": 0, "warning": 1, "critical": 2}

def meets_threshold(issue: dict, threshold: str) -> bool:
    issue_level = SEVERITY_ORDER.get(issue["severity"], 0)
    threshold_level = SEVERITY_ORDER.get(threshold, 0)
    return issue_level >= threshold_level

async def run_review_pipeline(owner:str, repo:str, pr_number:int, commit_sha:str, installation_id:int, custom_instruction:str | None = None):
    raw_config = await github_client.get_file_content(
        owner, repo, ".reviewai.yml", commit_sha, installation_id
    )
    config = parse_config(raw_config) if raw_config else DEFAULT_CONFIG
    print(f"Config loaded — threshold: {config.severity_threshold}, "
          f"ignored: {config.ignored_files}")
    
    diff = await github_client.get_pull_req_diff(owner, repo, pr_number, installation_id)

    hunks = parse_diff(diff)

    if config.ignored_files:
        original_count = len(hunks)
        hunks = [h for h in hunks if not should_ignore(h.file_path, config.ignored_files)]
        ignored_count = original_count - len(hunks)
        if ignored_count:
            print(f"Skipped {ignored_count} ignored file(s)")
            
    all_issues = []

    if not hunks:
        await github_client.post_summary(
            owner, repo, pr_number, installation_id,
            "## ✅ AI Code Review\n\nNo changes to review."
        )
        return
    
    file_context = {}
    changed_files = list({hunk.file_path for hunk in hunks})

    for file_path in changed_files:
        content = await github_client.get_file_content(owner, repo, file_path, commit_sha, installation_id)
        if content:
            file_context[file_path] = content
            print(f"Fetched context for {file_path} ({len(content)} chars)")

    for hunk in hunks:
        language_hint = get_language_hint(hunk.file_path, config.language_hints)
        try:
            issues = await llm_interface.review_hunk(hunk, custom_instruction, file_context, language_hint)
        except Exception as e:
            print(f"LLM failed on {hunk.file_path}: {e}")
            continue

        for issue in issues:
            issue["file_path"] = hunk.file_path
            for dl in hunk.lines:
                if dl.position == issue["position"]:
                    issue["new_file_line"] = dl.new_file_line
                    break
            else:
                continue
            all_issues.append(issue)
    
    filtered_issues = [
        i for i in all_issues
        if meets_threshold(i, config.severity_threshold)
    ]

    if len(filtered_issues) > config.max_comments:
        print(f"Capping {len(filtered_issues)} issues to {config.max_comments}")
        filtered_issues.sort(
            key=lambda i: SEVERITY_ORDER.get(i["severity"], 0),
            reverse=True
        )
        filtered_issues = filtered_issues[:config.max_comments]
        
    if filtered_issues:
        await github_client.post_review(
            owner, repo, pr_number, commit_sha, installation_id, filtered_issues
        )
        
    summary = build_summary(all_issues)
    await github_client.post_summary(
        owner, repo, pr_number, installation_id, summary
    ) 
