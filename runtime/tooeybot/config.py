"""
Configuration loading and validation.
"""

import os
import re
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class OllamaConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    timeout: int = 120


class OpenAIConfig(BaseModel):
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    timeout: int = 60


class AnthropicConfig(BaseModel):
    base_url: str = "https://api.anthropic.com"
    api_key: str = ""
    timeout: int = 60


class LLMConfig(BaseModel):
    provider: str = "ollama"
    model: str = "llama3.2"
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)


class ContextConfig(BaseModel):
    max_tokens: int = 8000
    response_reserve: int = 2000


class ExecutionConfig(BaseModel):
    command_timeout: int = 300
    max_retries: int = 3


class BudgetConfig(BaseModel):
    """Hard limits on agent behavior."""
    max_iterations_per_task: int = 20
    max_consecutive_failures: int = 3
    max_actions_without_progress: int = 5
    max_active_tasks: int = 10
    max_pending_tasks: int = 50
    max_task_duration_minutes: int = 30


class CuriosityConfig(BaseModel):
    """Curiosity system settings."""
    enabled: bool = True
    max_proposals_per_cycle: int = 2
    min_value_threshold: float = 0.6
    max_tasks_per_day: int = 5
    max_depth: int = 2  # How deep curiosity chains can go


class LoggingConfig(BaseModel):
    level: str = "INFO"
    console: bool = True


class Config(BaseModel):
    agent_home: Path = Path("/agent")
    llm: LLMConfig = Field(default_factory=LLMConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    budgets: BudgetConfig = Field(default_factory=BudgetConfig)
    curiosity: CuriosityConfig = Field(default_factory=CuriosityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def expand_env_vars(value: str) -> str:
    """Expand ${VAR} patterns in strings."""
    pattern = re.compile(r'\$\{([^}]+)\}')
    
    def replacer(match):
        var_name = match.group(1)
        return os.environ.get(var_name, "")
    
    return pattern.sub(replacer, value)


def process_config_values(obj):
    """Recursively expand environment variables in config."""
    if isinstance(obj, dict):
        return {k: process_config_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [process_config_values(v) for v in obj]
    elif isinstance(obj, str):
        return expand_env_vars(obj)
    return obj


def load_config(path: Path) -> Config:
    """Load configuration from YAML file."""
    with open(path, 'r') as f:
        raw_config = yaml.safe_load(f)
    
    # Expand environment variables
    processed = process_config_values(raw_config)
    
    return Config(**processed)
