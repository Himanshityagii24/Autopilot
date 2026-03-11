import httpx


def http_get(url: str) -> str:
    """
    Fetch raw content of a URL.
    Timeout set to 10s to prevent agent from hanging.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; TaskAutopilot/1.0)"
        }

        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()

            # Return first 3000 chars — enough context without overwhelming LLM
            return response.text[:3000]

    except httpx.TimeoutException:
        raise RuntimeError(f"http_get timed out for URL: {url}")
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"http_get got status {e.response.status_code} for: {url}")
    except Exception as e:
        raise RuntimeError(f"http_get failed: {str(e)}")