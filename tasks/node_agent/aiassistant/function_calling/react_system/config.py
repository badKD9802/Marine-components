"""Configuration settings for ReAct system."""

import os
from pathlib import Path

# Load .env file from app.tasks.node_agent.aiassistant.function_calling.react_system directory
try:
    from dotenv import load_dotenv

    # Get the directory where this config.py file is located
    current_dir = Path(__file__).parent
    env_path = current_dir / '.env'

    # Load .env file
    load_dotenv(dotenv_path=env_path)

except ImportError:
    pass  # dotenv not installed, use environment variables or defaults

CONFIG = {
    # LLM API settings
    "api_key": os.getenv("OPENAI_API_KEY", "dummy-key"),
    "base_url": os.getenv("OPENAI_BASE_URL"),  # Optional: for custom endpoints
    "model_name": os.getenv("OPENAI_MODEL", "gpt-4o"),

    # ReAct loop settings
    "max_iterations": int(os.getenv("MAX_ITERATIONS", "10")),

    # LLM generation settings
    "temperature": float(os.getenv("TEMPERATURE", "0.7")),
    "max_tokens": int(os.getenv("MAX_TOKENS", "2048")),
}
