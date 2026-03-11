import os
from datetime import datetime, timezone
from core.config import settings


def write_file(filename: str, content: str) -> str:
    """
    Writing content to a file inside the artifacts directory.
    Returns the file path on success.

    """
    try:
        
        filename = os.path.basename(filename)

        if not filename:
            raise ValueError("Filename cannot be empty")

        
        os.makedirs(settings.artifacts_dir, exist_ok=True)

        file_path = os.path.join(settings.artifacts_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return file_path

    except Exception as e:
        raise RuntimeError(f"write_file failed: {str(e)}")