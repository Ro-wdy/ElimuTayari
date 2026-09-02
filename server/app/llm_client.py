"""Claude API access, behind a seam so tests never call the network.

Every live-LLM feature (test generation, question clustering) goes through
LlmClient. The app wires the real Anthropic client at startup; tests inject
StubLlmClient via create_app(llm_client=...) and assert on the recorded
prompts. The anthropic SDK is imported lazily so the app can run (and the
whole suite can pass) without the package configured or a key present.

Model choice: claude-opus-5, thinking left at its default (adaptive). Keep
model selection here, not at call sites, so it changes in one place.
"""

from typing import Protocol

MODEL = "claude-opus-5"


class LlmClient(Protocol):
    def complete(self, system: str, prompt: str, max_tokens: int = 16000) -> str:
        """One system+user request; returns the response's text content."""


class AnthropicLlmClient:
    def __init__(self, api_key: str, workspace_id: str = "") -> None:
        self._api_key = api_key
        self._workspace_id = workspace_id
        self._client = None

    def complete(self, system: str, prompt: str, max_tokens: int = 16000) -> str:
        if self._client is None:
            import anthropic

            # Identity-linked keys must name the workspace they act in.
            headers = (
                {"anthropic-workspace-id": self._workspace_id}
                if self._workspace_id
                else None
            )
            self._client = anthropic.Anthropic(
                api_key=self._api_key, default_headers=headers
            )
        response = self._client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        )


class StubLlmClient:
    """Test double: records (system, prompt) pairs and replays canned replies.

    Replies are consumed in order; when the queue runs dry the last reply (or
    the default) repeats, so a test can enqueue exactly what it asserts on.
    """

    def __init__(self, replies: list[str] | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self._replies = list(replies or [])
        self._default = self._replies[-1] if self._replies else "stub reply"

    def complete(self, system: str, prompt: str, max_tokens: int = 16000) -> str:
        self.calls.append((system, prompt))
        if self._replies:
            reply = self._replies.pop(0)
            self._default = reply
            return reply
        return self._default
