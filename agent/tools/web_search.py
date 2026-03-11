from ddgs import DDGS


def web_search(query: str) -> str:
    """
    Searching  the web using DuckDuckGo 
    Returns top 5 results formatted as readable text.
    """
    try:
        results = DDGS().text(query, max_results=5)

        if not results:
            return f"No results found for: {query}"

       
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"[{i}] {r.get('title', 'No title')}\n"
                f"    URL: {r.get('href', '')}\n"
                f"    {r.get('body', 'No description')}"
            )

        return "\n\n".join(formatted)

    except Exception as e:
        raise RuntimeError(f"web_search failed: {str(e)}")