import os
import re
from core.config import settings


def write_file(filename: str, content: str) -> str:
    """
    Write content to a file inside the artifacts sandbox directory.
    Returns the file path on success.
    Cleans filename to remove invalid characters.
    """
    try:
        # Strip path traversal
        filename = os.path.basename(filename)

        # Remove Windows-invalid characters
        filename = re.sub(r'[<>:"/\\|?*\n\r]', '', filename).strip()

        # If filename is still empty or too long after cleaning, use default
        if not filename or len(filename) > 100:
            filename = "output.md"

        # Ensure it has an extension
        if "." not in filename:
            filename = filename + ".md"

        os.makedirs(settings.artifacts_dir, exist_ok=True)
        file_path = os.path.join(settings.artifacts_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return file_path

    except Exception as e:
        raise RuntimeError(f"write_file failed: {str(e)}")