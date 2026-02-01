"""
LLM Provider abstraction layer.

Supports multiple providers with a unified interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

import httpx

from .config import LLMConfig


@dataclass
class Message:
    """A single message in a conversation."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMResponse:
    """Response from an LLM call."""
    content: str
    model: str
    usage: Dict[str, int]  # prompt_tokens, completion_tokens, total_tokens
    raw: Dict[str, Any]  # Full response for debugging


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def chat(self, messages: List[Message], temperature: float = 0.7) -> LLMResponse:
        """Send messages and get a response."""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check if the provider is reachable."""
        pass


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""
    
    def __init__(self, config: LLMConfig):
        self.base_url = config.ollama.base_url
        self.model = config.model
        self.timeout = config.ollama.timeout
    
    def chat(self, messages: List[Message], temperature: float = 0.7) -> LLMResponse:
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        
        return LLMResponse(
            content=data["message"]["content"],
            model=data.get("model", self.model),
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
            },
            raw=data
        )
    
    def health_check(self) -> bool:
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""
    
    def __init__(self, config: LLMConfig):
        self.base_url = config.openai.base_url
        self.api_key = config.openai.api_key
        self.model = config.model
        self.timeout = config.openai.timeout
    
    def chat(self, messages: List[Message], temperature: float = 0.7) -> LLMResponse:
        url = f"{self.base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature
        }
        
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        
        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model", self.model),
            usage=data.get("usage", {}),
            raw=data
        )
    
    def health_check(self) -> bool:
        try:
            with httpx.Client(timeout=5) as client:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                response = client.get(f"{self.base_url}/models", headers=headers)
                return response.status_code == 200
        except Exception:
            return False


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""
    
    def __init__(self, config: LLMConfig):
        self.base_url = config.anthropic.base_url
        self.api_key = config.anthropic.api_key
        self.model = config.model
        self.timeout = config.anthropic.timeout
    
    def chat(self, messages: List[Message], temperature: float = 0.7) -> LLMResponse:
        url = f"{self.base_url}/v1/messages"
        
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        # Anthropic uses system separately
        system_msg = ""
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_msg = m.content
            else:
                chat_messages.append({"role": m.role, "content": m.content})
        
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": chat_messages,
            "temperature": temperature
        }
        
        if system_msg:
            payload["system"] = system_msg
        
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        
        return LLMResponse(
            content=data["content"][0]["text"],
            model=data.get("model", self.model),
            usage={
                "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
                "total_tokens": (
                    data.get("usage", {}).get("input_tokens", 0) +
                    data.get("usage", {}).get("output_tokens", 0)
                )
            },
            raw=data
        )
    
    def health_check(self) -> bool:
        # Anthropic doesn't have a simple health endpoint
        # We just check if we have an API key configured
        return bool(self.api_key)


def create_provider(config: LLMConfig) -> LLMProvider:
    """Factory function to create the appropriate LLM provider."""
    providers = {
        "ollama": OllamaProvider,
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider
    }
    
    provider_class = providers.get(config.provider)
    if not provider_class:
        raise ValueError(f"Unknown LLM provider: {config.provider}")
    
    return provider_class(config)
