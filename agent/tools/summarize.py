from openai import OpenAI
from core.config import settings


client = OpenAI(
    api_key=settings.groq_api_key,
    base_url="https://api.groq.com/openai/v1"
)


def summarize(text: str) -> str:
    """
    Summarize long text using Groq LLM.
    """
    try:
        if not text or not text.strip():
            return "Nothing to summarize — input was empty."

        response = client.chat.completions.create(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            messages=[
                {
                    "role": "system",
                    "content": "You are a concise summarizer. Summarize the given text clearly and briefly."
                },
                {
                    "role": "user",
                    "content": f"Summarize this:\n\n{text}"
                }
            ]
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        raise RuntimeError(f"summarize failed: {str(e)}")