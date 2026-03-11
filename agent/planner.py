import json
from openai import OpenAI
from core.config import settings


client = OpenAI(
    api_key=settings.groq_api_key,
    base_url="https://api.groq.com/openai/v1"
)


def build_planning_prompt(goal: str) -> str:
    tools_description = """
- web_search(query)             : Search the web using DuckDuckGo
- summarize(text)               : Summarize long text using LLM
- write_file(filename, content) : Write content to a file in sandbox
- read_file(filename)           : Read a file from sandbox
- http_get(url)                 : Fetch raw content of a URL
"""
    prompt = f"""You are an autonomous task planning agent.

Your job is to break down the following goal into a sequence of steps.
Each step must use exactly one of the available tools.

Available tools:
{tools_description}

Rules:
- Maximum {settings.max_steps} steps
- Each step must have a clear tool and input
- Steps must be in logical execution order
- If a step uses output from a previous step, write "output_of_step_N" as input
- Return ONLY valid JSON — no explanation, no markdown, no code blocks

Goal: {goal}

Return this exact JSON format:
{{
    "steps": [
        {{
            "step_number": 1,
            "tool": "tool_name",
            "input": "input string for this tool"
        }}
    ]
}}"""
    return prompt


def plan_task(goal: str) -> tuple[list[dict], str]:
    """
    Calls Groq LLM to decompose goal into steps.

    Returns:
        steps      : list of step dicts [{step_number, tool, input}]
        prompt_used: exact prompt sent — stored in DB for reproducibility
    """
    if not goal or not goal.strip():
        raise ValueError("Goal cannot be empty")

    prompt = build_planning_prompt(goal)

    response = client.chat.completions.create(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        messages=[
            {
                "role": "system",
                "content": "You are a task planning agent. Always respond with valid JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    raw = response.choices[0].message.content.strip()

    # Clean up markdown wrapping if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        parsed = json.loads(raw)
        steps = parsed.get("steps", [])
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM returned invalid JSON: {e}\nRaw: {raw}")

    if not steps:
        raise RuntimeError("LLM returned empty steps list")

    if len(steps) > settings.max_steps:
        steps = steps[:settings.max_steps]

    return steps, prompt