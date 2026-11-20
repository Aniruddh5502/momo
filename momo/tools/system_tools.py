"""Momo's bash tool. On Windows it runs commands in PowerShell; elsewhere it uses /bin/sh."""

import base64
import html
import platform
import re
import shutil
import subprocess

from langchain_core.tools import tool
from momo.tools.registry import ToolContext

IS_WINDOWS = platform.system() == "Windows"

# Whole words only, case-insensitive so PowerShell aliases and cmdlets match.
# "python -c" and "py -c" are gated too.
NEEDS_APPROVAL = re.compile(
    r"\b(rm|rmdir|rd|del|erase|ri|unlink|remove-item)\b|\bpy(?:thon3?)?\s+-c\b",
    re.IGNORECASE,
)

PROTECTED_PROMPTS = ("soul.md", "tool.md", "user.md")

# Absolute-path detector.
# - Drive paths (C:\x, C:/x) and UNC paths (\\server\share) are always absolute.
# - Rooted paths (/etc, \foo) need exactly one leading separator, so URLs like https://x are ignored,
#   and at least two characters after it, so switches like /s are ignored.
_DRIVE_OR_UNC = r"""[A-Za-z]:[\\/][^\s'"]*|\\\\[^\s'"]+"""
_ROOTED = r"""[/\\](?![/\\])[^\s'"]{2,}"""
ABSOLUTE_PATH = re.compile(
    r"(?:^|(?<=[\s'\"=:(]))(?:" + _DRIVE_OR_UNC + "|" + _ROOTED + ")"
)

# Runs before every command. Keeps output as UTF-8 so non-ASCII file names survive.
PS_PREAMBLE = (
    "try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}\n"
    "$ProgressPreference = 'SilentlyContinue'\n"
)

# Windows caps a process command line at 32,767 characters. -EncodedCommand is base64 of
# UTF-16, which grows text by about 2.67x, so the raw command has a much smaller limit.
MAX_ENCODED_CHARS = 30000

_CLIXML_ERRORS = re.compile(r'<S S="Error">(.*?)</S>', re.DOTALL)
_CLIXML_BLOCK = re.compile(r"#< CLIXML\r?\n?<Objs.*?</Objs>", re.DOTALL)
_XML_CHAR = re.compile(r"_x([0-9A-Fa-f]{4})_")


def _clean_stderr(text: str) -> str:
    """Windows PowerShell can write errors to stderr as CLIXML. Return only the readable messages."""
    if "#< CLIXML" not in text:
        return text.strip()
    errors = [
        _XML_CHAR.sub(lambda m: chr(int(m.group(1), 16)), html.unescape(e)).strip()
        for e in _CLIXML_ERRORS.findall(text)
    ]
    if errors:
        return "\n".join(e for e in errors if e)
    return _CLIXML_BLOCK.sub("", text).strip()


def _ps_executable() -> str:
    # PowerShell 7 (pwsh) if installed, otherwise the built-in Windows PowerShell 5.1.
    return shutil.which("pwsh") or shutil.which("powershell") or "powershell.exe"


def _run(command: str, cwd, timeout: int) -> subprocess.CompletedProcess:
    if IS_WINDOWS:
        # The script is base64-encoded and passed as an argument. Nothing is re-parsed by cmd.exe
        # and quotes, $ signs and non-ASCII characters reach PowerShell unchanged.
        script = PS_PREAMBLE + command
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        if len(encoded) > MAX_ENCODED_CHARS:
            raise ValueError(
                f"command is too long ({len(command)} characters); split it into smaller commands"
            )
        argv = [_ps_executable(), "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]
        return subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    return subprocess.run(
        command,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def create_system_tools(ctx: ToolContext):
    def _shell_blurb() -> str:
        if IS_WINDOWS:
            return f"PowerShell ({_ps_executable()}, command sent with -EncodedCommand)"
        return "/bin/sh (shell=True, ignores $SHELL)"

    @tool
    def Bash(command: str, timeout: int = 30) -> str:
        """Executes a PowerShell command in the project root.
        Args:
            command: The command to execute.
            timeout: in seconds.
        """
        match = ABSOLUTE_PATH.search(command)
        if match:
            return f"""<WARNING>
        Command contains an absolute path ({match.group(0)!r}) and has been declined.
        Momo must use relative paths. The working directory is already the project root,
        so drop any `cd` and write paths relative to it, e.g. `dir tests\\assisted_nn`.
        </WARNING>"""

        if NEEDS_APPROVAL.search(command):
            if ctx.confirm is None or not ctx.confirm(command):
                return """<WARNING>User has Declined to run this command
            You must stop running commands like this and consult with the user
            </WARNING>"""

        try:
            result = _run(command, ctx.project_root, timeout)
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout} seconds."
        except Exception as e:
            return f"Error executing command: {e}"

        output = (result.stdout or "").lstrip("\ufeff")
        error = _clean_stderr(result.stderr or "")
        if result.returncode != 0 and not error:
            error = f"Exit code {result.returncode}"

        if error and not output:
            return f"Error: {error}"
        return f"Output:\n{output}\n\nErrors:\n{error}" if error else output

    Bash.description = Bash.description + f"\n\nShell: {_shell_blurb()}"

    
    @tool
    def Write(filePath: str, content: str) -> str:
        """Writes content to a file in the project root. Overwrites if exists.
        
        Args:
            filePath: Path to the file relative to project root.
            content: The text content to write.
        """
        try:
            full_path = (ctx.project_root / filePath).resolve()

            # Block whole-file writes to the system prompt files. Compare resolved paths,
            # so forward/back slashes, "..", and symlinks can't get around the check.
            protected = {(ctx.project_root / ".momo" / "prompts" / name).resolve() for name in PROTECTED_PROMPTS}
            if full_path in protected:
                return """
You are not allowed to fully write/overwrite this file.
You should only use the edit tool to edit small sections at a time."""

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
    def Read(filePath: str, start: int = 0, end: int = 200) -> str:
        """Read a range of lines from a text file inside the project.

        Use this to inspect source code or documentation. Returns the requested
        lines prefixed with a header of the form "[Showing lines X-Y of N]", where
        N is the total line count, so you can tell whether more content exists.

        Args:
            filePath: Path to the file, relative to the project root
                (e.g. "src/main.py"). Absolute paths and paths that escape the
                project root are rejected.
            start: 0-based index of the first line to return (inclusive).
                Negative values are treated as 0. Defaults to 0.
            end: 0-based index one past the last line to return (exclusive).
                Defaults to 200, which returns at most 200 lines. Pass -1 to read
                through the end of the file. Values larger than the file length
                are clamped to the end.

        Line range examples:
            - Lines 20 through 50 inclusive: start=20, end=51
            - The first 100 lines: start=0, end=200 (the defaults)
            - Everything from line 300 onward: start=300, end=-1
            - Only the first line: start=0, end=1

        Supported file types: .md, .txt, .py, .cpp, .c, .html, .css.
        Other extensions are rejected. Use a Python script to inspect the
        metadata of other file types instead.

        Errors are returned as strings beginning with "Error:", including
        when the file is missing, is not a regular file, is outside the project
        root, has an unsupported extension, or when end <= start after
        normalization. An empty file returns "File Is Empty".

        Tip: if the header shows the file has more lines than you received,
        call the tool again with a higher start value to continue reading.
        """
        try:
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

            content = full_path.read_text(encoding='utf-8')
            if content == "":
                return "File Is Empty"

            lines = content.splitlines(keepends=True)
            total = len(lines)

            # Normalize
            if start < 0:
                start = 0
            if end == -1 or end > total:
                end = total
            if end <= start:
                return f"Error: end ({end}) must be greater than start ({start})."

            selected = lines[start:end]
            body = "".join(selected)

            # Helpful header so the agent knows whether truncation occurred
            header = f"[Showing lines {start}-{min(end, total) - 1} of {total}]\n"
            return header + body

        except Exception as e:
            return f"Error reading file: {str(e)}"

    @tool
    def Edit(path: str, old_str: str, new_str: str) -> str:
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

    return [Bash, Write, Read, Edit]