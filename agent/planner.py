import json
from openai import OpenAI
from core.config import settings


client = OpenAI(
    api_key=settings.groq_api_key,
    base_url="https://api.groq.com/openai/v1"
)


def build_planning_prompt(goal: str) -> str:
    prompt = f"""You are an autonomous task planning agent.

Break down the following goal into clear sequential steps.
Each step uses exactly ONE tool.

AVAILABLE TOOLS:
- web_search   : input is a short search query. Example: "top Python frameworks 2024"
- summarize    : input is output_of_step_N to summarize previous output. Example: "output_of_step_1"
- write_file   : input format is EXACTLY "filename.md, content". Example: "report.md, output_of_step_2"
- read_file    : input is a filename. Example: "report.md"
- http_get     : input is a REAL https:// URL only. Example: "https://reactjs.org"

STRICT RULES:
- Maximum {settings.max_steps} steps
- NEVER pass summarize output to http_get — http_get only accepts real URLs
- NEVER use output_of_step_N as input to http_get
- For http_get only use URLs found directly from web_search results
- For write_file the filename must be short like "report.md" — never use sentence as filename
- Return ONLY valid JSON — no markdown, no code blocks, no explanation

GOAL: {goal}

PREFERRED PATTERN for research goals:
1. web_search for the topic
2. summarize the results
3. write_file to save the summary

Return this exact JSON:
{{
    "steps": [
        {{
            "step_number": 1,
            "tool": "tool_name",
            "input": "exact input"
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