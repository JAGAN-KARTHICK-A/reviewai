import json
from app.diff_parser import DiffHunk
from services.ai.prompt_builder import SYSTEM_PROMPT_DIFF, REPLY_SYSTEM_PROMPT, build_prompt_diff, build_prompt_reply_comment
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from core.config import settings

class LLM_Interface():
    def __init__(self):
        self._api_key = settings.GEMINI_API_KEY
        self._llm = None
        self._init_model()
    def _init_model(self):
        self._llm = ChatGoogleGenerativeAI(
            model=settings.MODEL_NAME,
            temperature=0.7,
            google_api_key=self._api_key
        )
    def _invoke_llm(self, system_prompt, content):
        return self._llm.invoke(system_prompt+[HumanMessage(content=content)]).content.strip()
    async def review_hunk(self, hunk:DiffHunk, custom_instruction:str | None = None, file_context: dict[str, str] | None = None, language_hint: str | None = None):
        added_lines = [l for l in hunk.lines if l.line_type == "added"]
        if not added_lines: return []

        meaningful_lines = [dl for dl in added_lines if dl.content.strip()]
        if not meaningful_lines: return []

        prompt = build_prompt_diff(hunk, custom_instruction, file_context, language_hint)
        response = self._invoke_llm([SystemMessage(content=SYSTEM_PROMPT_DIFF)], prompt)

        try:
            issues = json.loads(response)
            if not isinstance(issues, list): return []
            return issues
        except json.JSONDecodeError:
            print(f"LLM returned non-JSON: {response[:200]}")
            return []
    async def review_comment(self, owner:str, repo:str, installation_id:int, diff_hunk:str, user_question, in_reply_to_id):
        prompt = await build_prompt_reply_comment(owner, repo, installation_id, diff_hunk, user_question, in_reply_to_id)
        response = self._invoke_llm([SystemMessage(content=REPLY_SYSTEM_PROMPT)], prompt)
        return response


