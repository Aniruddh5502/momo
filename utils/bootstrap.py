"""
This tool handles building the system prompt and the compaction prompt
"""

# normal imports 
import platform, os, sys, subprocess, json
from typing import Annotated, Sequence, TypedDict, Dict, Any
from pathlib                    import Path

# Building the system prompt
root = Path(__file__).parent.parent

# Paths used across the system
STATE_DIR = root / "states"
WORKSPACE_DIR = Path.cwd()
soul_file = root / "prompts" / "soul.md"

def get_system_info() -> Dict[str, Any]:
    # Using a safer way to get shell info on Windows
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

def build_system_prompt(state: Dict[str, Any]) -> str:
    """
    Constructs the full system prompt by combining the soul.md,
    system information, and the current agent state summary.
    """
    # 1. Load Soul (Base Identity)
    try:
        with open(soul_file, 'r', encoding='utf-8') as f:
            soul_content = f.read()
    except Exception as e:
        soul_content = "You are Momobot, a high-performance AI agent."

    # get user info
    user_file = root / "prompts" / "user.md"
    user_content = ""
    try:
        with open(user_file, 'r',encoding='utf-8') as file:
            user_content = file.read()
    except:
        user_content = ""

    user_content_sys = f"\n\n# User Details and Memory\n{user_content}"

    # 2. Get System Info
    sys_info = get_system_info()
    sys_info_str = "\n\n# System Information:\n" + json.dumps(sys_info, indent=2)

    # 3. Get State Summary
    summary = state.get("summary", "No summary available.")
    state_str = f"\n\n# Task State Summary:\n{summary}"

    # 4. Project Config
    momo_file = WORKSPACE_DIR / "momo.md"
    try:
        with open(momo_file, 'r', encoding='utf-8') as file:
            momo_ = momo_file.read()
        momo_content = f"\n\n# Project Specific tools and files locations\n{momo_}"
    except:
        momo_content = ""
        
        
    # Combine all parts
    full_prompt = f"{soul_content} {user_content_sys} {sys_info_str}{state_str}{momo_content}"
    
    return full_prompt
