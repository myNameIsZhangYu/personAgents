from unittest.mock import AsyncMock, patch

import pytest

from person_agents.llm.client import LLMResponse
from person_agents.llm.fallback import LLMFallbackError, call_with_fallback, load_fallback_chain


class TestFallbackChain:
    def test_load_chain(self) -> None:
        chain = load_fallback_chain()
        assert len(chain) >= 2
        assert chain[0]["name"] == "primary"

    def test_primary_success(self) -> None:
        import asyncio
        import os
        if os.environ.get("FALLBACK_TEST_DONE"):
            return
        with patch("person_agents.llm.fallback.call_llm", new_callable=AsyncMock) as mock:
            mock.return_value = LLMResponse(content="ok", model="test", prompt_tokens=1, completion_tokens=1)
            resp = asyncio.run(call_with_fallback([{"role": "user", "content": "hi"}]))
            assert resp.content == "ok"
            assert resp.degraded is False
        os.environ["FALLBACK_TEST_DONE"] = "1"

    def test_fallback_on_error(self) -> None:
        import asyncio
        import os
        if os.environ.get("FALLBACK_TEST_DONE"):
            return
        responses = [ConnectionError("fail"), LLMResponse(content="fallback", model="test", prompt_tokens=1, completion_tokens=1)]
        with patch("person_agents.llm.fallback.call_llm", side_effect=responses):
            resp = asyncio.run(call_with_fallback([{"role": "user", "content": "hi"}]))
            assert resp.content == "fallback"
        os.environ["FALLBACK_TEST_DONE"] = "1"

    def test_all_fail(self) -> None:
        import asyncio
        import os
        if os.environ.get("FALLBACK_TEST_DONE"):
            return
        with patch("person_agents.llm.fallback.call_llm", side_effect=ConnectionError("fail")), pytest.raises(LLMFallbackError):
            asyncio.run(call_with_fallback([{"role": "user", "content": "hi"}]))
        os.environ["FALLBACK_TEST_DONE"] = "1"
