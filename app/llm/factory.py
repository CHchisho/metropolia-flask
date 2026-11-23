from __future__ import annotations

from ..config import Config
from .base import LLMProvider
from .demo import DemoProvider
from .openai_compatible import OpenAICompatibleProvider


def build_llm(config: Config) -> LLMProvider:
    if config.llm_provider == "demo":
        return DemoProvider()
    if config.llm_provider == "openai":
        return OpenAICompatibleProvider(
            base_url=config.llm_base_url,
            api_key=config.llm_api_key,
            model=config.llm_model,
            timeout=config.llm_timeout,
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {config.llm_provider!r} (use 'demo' or 'openai')")
