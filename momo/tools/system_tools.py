import os, platform
from pathlib import Path
from typing import Any
from langchain_core.tools import tool
import subprocess
from momo.tools.registry import ToolContext

def create_system_tools(ctx: ToolContext):
    def _shell_blurb() -> str:
        if platform.system() == "Windows":
            comspec = os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
            return f"cmd.exe (shell=True → {comspec})"
        return "/bin/sh (shell=True, ignores $SHELL)"
    
    @tool
    def bash(command: str) -> str:
        """Executes a shell command in the project root.
        Args:
            command: The bash/cmd command to execute.
        """
        try:
            # Run command in the project root directory
            result = subprocess.run(
                command,
                shell=True,
                cwd=ctx.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stdout if result.stdout else ""
            error = result.stderr if result.stderr else ""
            
            if error and not output:
                return f"Error: {error}"
            return f"Output:\n{output}\n\nErrors:\n{error}" if error else output
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 30 seconds."
        except Exception as e:
            return f"Error executing command: {str(e)}"

    bash.description = bash.description + f"\n\nShell: {_shell_blurb()}"
    
    @tool
    def write(filePath: str, content: str) -> str:
        """Writes content to a file in the project root. Overwrites if exists.
        
        Args:
            filePath: Path to the file relative to project root.
            content: The text content to write.
        """
        # check if its writing the system prompt files
        if filePath.endswith(".momo/prompts/soul.md" or ".momo/prompts/tool.md" or ".momo/prompts/user.md") :
            return """
You are not allowed to fully write/overwrite this file. 
You should only use the edit tool to edit small sections at a time."""
        try:
            full_path = (ctx.project_root / filePath).resolve()
            
            # Security check: prevent writing outside project root
            if not full_path.is_relative_to(ctx.project_root.resolve()):
                return "Error: Access denied. Cannot write outside project root."
            
            # Create parent directories if they don't exist
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            full_path.write_text(content, encoding="utf-8")
            return f"Successfully wrote to {filePath}"
        except Exception as e:
            return f"Error writing file: {str(e)}"
        
    @tool
    def read(filePath: str) -> str:
        """Reads the content of a file from the filesystem.
            
        Args:
            filePath: Path to the file to read, relative to the project root.
        """
        try:
            # Use project_root from context to ensure it reads from the project 
            # the agent is actually operating on, regardless of launch directory.
            full_path = (ctx.project_root / filePath).resolve()
                
            # Security check: Ensure the file is actually inside the project root
            if not full_path.is_relative_to(ctx.project_root.resolve()):
                return f"Error: Access denied. Path {filePath} is outside the project root."
    
            if not full_path.exists():
                return f"Error: File {filePath} not found."
            if not full_path.is_file():
                return f"Error: {filePath} is not a file."
            if full_path.suffix.lower() not in [".md", ".txt", ".py", ".cpp", ".c", ".html", ".css"]:
                return f"""Error: You are not allowed to read {full_path.suffixes} file(file). 
            You should use python scripts to analyze the metadata of these files\n"""
            return full_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading file: {str(e)}"

    @tool
    def edit(path: str, old_str: str, new_str: str) -> str:
            """
            Edit a specific string in a file without rewriting the whole file.
            The old_str must appear EXACTLY once in the file.
            
            Args:
                path: File path relative to workspace (e.g. 'src/main.py')
                old_str: Exact text to find — must appear exactly once, whitespace and indentation must match
                new_str: Replacement text
            """
            import os
            from pathlib import Path
    
            try:
                # Resolve path relative to project root
                full_path = Path(ctx.project_root) / path
                if not full_path.exists():
                    return f"Error: File not found at {full_path}"
    
                content = full_path.read_text(encoding="utf-8")
                
                # Count occurrences
                count = content.count(old_str)
                if count == 0:
                    return f"Error: old_str not found in {path}."
                if count > 1:
                    return f"Error: old_str found {count} times in {path}. Please provide more context to make it unique."
    
                # Perform replacement
                new_content = content.replace(old_str, new_str)
                full_path.write_text(new_content, encoding="utf-8")
                
                return f"Successfully updated {path}."
            except Exception as e:
                return f"Error during edit: {str(e)}"

    return [bash, write, read, edit]
