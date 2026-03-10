"""LLM Client wrapper for OpenAI API."""

from openai import OpenAI
from app.tasks.node_agent.aiassistant.function_calling.react_system.config import CONFIG


class OpenAIClient:
    """Client for OpenAI API."""

    def __init__(self, config=None):
        """
        Initialize OpenAI client.

        Args:
            config: Configuration dict (defaults to CONFIG from config.py)
        """
        self.config = config or CONFIG

        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=self.config["api_key"],
            base_url=self.config.get("base_url")  # Optional for custom endpoints
        )

        self.model_name = self.config["model_name"]
        self.temperature = self.config["temperature"]
        self.max_tokens = self.config["max_tokens"]

    def chat_completion(self, messages, tools=None, system_instruction=None):
        """
        Call OpenAI for chat completion.

        Args:
            messages: List of message dicts (OpenAI format)
            tools: List of tool definitions (OpenAI format)
            system_instruction: System instruction string

        Returns:
            Response object with OpenAI structure
        """
        # Add system instruction as first message if provided
        if system_instruction:
            # Check if system message already exists
            has_system = any(msg.get("role") == "system" for msg in messages)
            if not has_system:
                messages = [{"role": "system", "content": system_instruction}] + messages

        # Build API call parameters
        kwargs = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        # Add tools if provided
        if tools:
            kwargs["tools"] = tools

        try:
            response = self.client.chat.completions.create(**kwargs)
            return response

        except Exception as e:
            # Return error in a compatible format
            return self._create_error_response(str(e))

    def _create_error_response(self, error_msg):
        """Create error response in OpenAI format."""
        model_name = self.model_name  # Capture model_name in local variable

        class Message:
            def __init__(self):
                self.role = "assistant"
                self.content = f"Error: {error_msg}"
                self.tool_calls = None

        class Choice:
            def __init__(self, msg):
                self.message = msg
                self.finish_reason = "error"

        class Response:
            def __init__(self, msg):
                self.choices = [Choice(msg)]
                self.model = model_name  # Use captured model_name

        return Response(Message())
