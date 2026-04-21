"""
llm_client.py — Real Gemini 2.5 LLM client.

Uses the current `google.genai` SDK (google-genai package).
Reads GEMINI_API_KEY and optionally GEMINI_MODEL from the .env file.
Returns raw text from the model; parsing/validation is handled by validator.py.
"""

import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load .env file on first import
load_dotenv()

_DEFAULT_MODEL = "gemini-2.5-flash"


def _get_client() -> genai.Client:
    """Initialise and return a Gemini Client."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. "
            "Add it to your .env file or set it as an environment variable."
        )
    return genai.Client(api_key=api_key)


def call_llm(prompt: str) -> str:
    """
    Send *prompt* to Gemini and return the raw text response.

    Args:
        prompt: The fully-built prompt string from prompt.py.

    Returns:
        Raw text from the model (may be JSON, may include extra prose).

    Raises:
        EnvironmentError: If GEMINI_API_KEY is missing.
        google.genai.errors.APIError: On API-level failures.
    """
    client = _get_client()
    model_name = os.environ.get("GEMINI_MODEL", _DEFAULT_MODEL)

    config = types.GenerateContentConfig(
        temperature=0.4,
        top_p=0.95,
        max_output_tokens=2048,
    )

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=config,
    )

    return response.text
