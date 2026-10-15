from pathlib import Path

# Paths to the prompts
prompts_directory   =   Path(__file__).parent
workspace_directory =   Path.cwd()

# core
soul        =   prompts_directory / "soul.md"
compaction  =   prompts_directory / "compaction.md"
user        =   prompts_directory / "user.md"
tools       =   prompts_directory / "tools.md"

# persona
critique    =   prompts_directory / "critique.md"
executor    =   prompts_directory / "executor.md"
researcher  =   prompts_directory / "researcher.md"
reviewer    =   prompts_directory / "reviewer.md"

# utilities
memory      =   prompts_directory / "memory.md"

print(workspace_directory)