import shutil
import os
from pathlib import Path
import importlib.resources

def ensure_momo_dir(project_root: Path):
    """
    Ensures the .momo directory exists in the project root.
    Uses importlib.resources to locate the bundled .momo data.
    """
    target_momo = project_root / ".momo"

    if not target_momo.exists():
        try:
            # Use momo_data (non-hidden) to avoid importlib.resources issues with dot-folders
            with importlib.resources.path("momo", "momo_data") as source_momo:
                shutil.copytree(source_momo, target_momo)
        except (ImportError, FileNotFoundError, Exception):
            # Fallback: Create basic structure if bundled data isn't found
            target_momo.mkdir(parents=True, exist_ok=True)
            (target_momo / "agents").mkdir(parents=True, exist_ok=True)
            
    return target_momo
