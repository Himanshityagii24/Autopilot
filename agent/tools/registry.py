from agent.tools.web_search import web_search
from agent.tools.summarize import summarize
from agent.tools.write_file import write_file
from agent.tools.read_file import read_file
from agent.tools.http_get import http_get



TOOL_REGISTRY = {
    "web_search": web_search,
    "summarize":  summarize,
    "write_file": write_file,
    "read_file":  read_file,
    "http_get":   http_get,
}


def get_tool(name: str):
    """
    Look up a tool by name.
    Returns None if tool doesn't exist — agent loop handles this gracefully.
    """
    return TOOL_REGISTRY.get(name)


def list_tools() -> list[str]:
    """Returns all available tool names — used in planner prompt."""
    return list(TOOL_REGISTRY.keys())