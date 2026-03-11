import os
from core.config import settings


def read_file(filename: str) -> str:
    """
    Reading a file from the artifacts directory.
    Prevents reading files outside the sandbox.
    """
    try:
        
        filename = os.path.basename(filename)

        file_path = os.path.join(settings.artifacts_dir, filename)

        if not os.path.exists(file_path):
            return f"File not found: {filename}"

        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    except Exception as e:
        raise RuntimeError(f"read_file failed: {str(e)}")