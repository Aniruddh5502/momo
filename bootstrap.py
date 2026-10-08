from pathlib import Path
import platform
import os
import sys
import subprocess
import json
from typing import Dict, Any
from rich.console import Console

console = Console()

# ===========================================================================
# ENVIRONMENT CONFIGURATION
# ===========================================================================

# Root of the momobot package
ROOT = Path(__file__).parent

# Workspace is where the user runs the bot
WORKSPACE_DIR = Path.cwd()

# Directories
STATE_DIR = ROOT / "states"
SESSIONS_DIR = ROOT / "sessions"

# Files
SESSIONS_DB = SESSIONS_DIR / "sessions.db"
sessions_db = SESSIONS_DB
SOUL_FILE = ROOT / "prompts" / "soul.md"
USER_FILE = ROOT / "prompts" / "user.md"

def initialize_environment():
    """Ensures necessary directories exist."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# Initialize immediately on import
initialize_environment()

# Load configuration from config.py
try:
    from momobot import config as config_module
    config = config_module.config
except Exception:
    config = {}

# ===========================================================================
# PROMPT CONSTRUCTION LOGIC
# ===========================================================================

class PromptBuilder:
    """
    Handles the structured construction of system prompts.
    Separates data collection from prompt formatting:
    """

    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """Collects deterministic environment data."""
        try:
            result = subprocess.run("echo %COMSPEC%", shell=True, capture_output=True, text=True)
            shell_info = result.stdout.strip()
        except Exception:
            shell_info = "Unknown"

        return {
            "OS": platform.system(),
            "OS Version": platform.version(),
            "Node": platform.node(),
            "Architecture": platform.machine(),
            "Python Version": sys.version,
            "Python Executable": sys.executable,
            "shell info": shell_info
        }

    @staticmethod
    def load_file_content(path: Path, default: str = "") -> str:
        """Safely reads a file or returns a default."""
        try:
            if path.exists():
                return path.read_text(encoding='utf-8')
        except Exception:
            pass
        return default

    @classmethod
    def build_system_prompt(cls, state: Dict[str, Any], persona_prompt: str = "", persona_path: str = "") -> str:
        """
        Constructs the full system prompt using a structured layered approach:
        1. Base Identity (Soul) - Loaded from persona_path or global SOUL_FILE
        2. Persona Specifics (from config) - The specific goal/instructions
        3. User Context (User Memory)
        4. Environment (System Info)
        5. Project Context (momo.md)
        6. Session State (Summary)
        """
        # 1. Base Identity (The Soul)
        # Use the path from the persona config if provided, otherwise fallback to the global soul.md
        try:
            soul = cls.load_file_content(persona_path, " ")
        except Exception as e:
            console.print(f"[dim]Soul File loading error: {e}[/]")
            
        # 2. Persona Layer (Specialization)
        persona = f"\n\n# Persona Instructions\n{persona_prompt}" if persona_prompt else ""
        
        # 3. User Context
        user = cls.load_file_content(USER_FILE)
        user_section = f"\n\n# User Details and Memory\n{user}" if user else ""
        
        # 4. Environment
        sys_info = cls.get_system_info()
        sys_section = f"\n\n# System Information:\n{json.dumps(sys_info, indent=2)}"
        
        # 5. Project Context (External momo.md in workspace)
        momo_path = WORKSPACE_DIR / "momo.md"
        momo = cls.load_file_content(momo_path)
        momo_section = f"\n\n# Project Specific Instructions\n{momo}" if momo else ""
        
        # 6. Session State
        summary = state.get("summary", "No summary available.")
        state_section = f"\n\n# Task State Summary:\n{summary}"

        # Combine in order of priority/hierarchy
        return f"{soul}{persona}{user_section}{sys_section}{momo_section}{state_section}"

# Singleton instance for easy access
prompt_builder = PromptBuilder()
