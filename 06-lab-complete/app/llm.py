"""Groq LLM client — economics-only chatbot via system prompt."""
from groq import Groq

from app.config import settings

_client = Groq(api_key=settings.groq_api_key)

_SYSTEM_PROMPT = """You are an expert economics assistant. You only answer questions related to economics, including but not limited to:
- Microeconomics and macroeconomics
- Supply and demand, market structures
- GDP, inflation, unemployment, monetary and fiscal policy
- International trade and finance
- Economic history and schools of thought
- Personal finance and investment concepts

If the user asks about anything outside of economics, politely decline and remind them that you only discuss economics topics. Keep answers clear, accurate, and educational."""


def chat(question: str, history: list[dict] | None = None) -> tuple[str, int, int]:
    """
    Call Groq LLM with the economics system prompt.

    Args:
        question: The user's current message.
        history:  List of prior {"role": ..., "content": ...} messages for context.

    Returns:
        (answer_text, input_tokens, output_tokens)
    """
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    if history:
        messages.extend(history[-10:])  # keep last 5 turns (10 messages)
    messages.append({"role": "user", "content": question})

    response = _client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=0.7,
        max_tokens=1024,
    )

    answer = response.choices[0].message.content
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    return answer, input_tokens, output_tokens
