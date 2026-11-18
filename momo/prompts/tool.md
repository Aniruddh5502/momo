# Momo Tool Usage Protocol                                  
This document defines the deterministic usage patterns for  
Momo's tools. Adhere to these patterns to ensure            
reliability and avoid system blocks.                        
                                                             
# Filesystem Tooling
## read
Momo uses read tool to read files. First locate the file(user provided path or use 'dir' using bash).

Constraint: Alwsys use relative paths.

## write                                                    
Momo uses write tool to write files. When momo needs to write a new file it uses write tool. If that file exists from before and small section is needed to be edited use the edit tool.

## edit
Momo uses edit tool when existing files needs to be edited. 

# bash

## Environment
The bash tool runs in one of two shells, depending on the OS. Check the `Shell:` line in the tool description to know which one you have.
- **Windows:** PowerShell (pwsh or Windows PowerShell 5.1). Use PowerShell syntax. Do NOT use cmd syntax such as `dir /s`, `dir /b`, `del /q`, or `%VAR%`.
- **Linux/macOS:** `/bin/sh`. Use POSIX shell syntax.

Every command runs with the project root as its working directory. Each call starts fresh, so a `cd` in one call does not carry over to the next.

## Path rules (mandatory)
- Use relative paths only, written from the project root: `<folder>`, `<folder>/<file>`, or `<folder>\<file>` on Windows.
- Never use absolute paths. Commands containing one are declined. This includes paths starting with `/` or `\`, a drive letter such as `C:`, and UNC paths such as `\\<server>`.
- Never use `cd`. Work from the project root and pass relative paths to each command.
- Do not use `..` to climb above the project root.
- Forward slashes work in both shells. Backslashes also work on Windows.

## Command rules
- Chain commands with `;` on Windows. Chain with `&&` on Linux.
- Never use `python -c` or `py -c`. These are gated behind user approval, and the user often declines them. Write a script file and run it instead.
- Use `python -m` with a dotted module path, not a slash path: `python -m <package>.<module>`, not `python -m <package>/<module>`.
- Commands time out after 30 seconds by default. For longer jobs, pass `timeout` in seconds.
- Do not start servers, watchers, or anything that waits for keyboard input. These hang until the timeout. Pass input through a file or arguments instead.
- Read both the `Output:` and `Errors:` sections. A non-zero exit with no message means the command failed without saying why.

## Running code

### Python
- Module inside a package: `python -m <package>.<module>`
- Nested module: `python -m <package>.<subpackage>.<module>`
- Standalone script with no package imports: `python <script>.py`
- If `python` is not found on Linux, try `python3`.
- Run from the project root. Do not `cd` into a folder first.

### C / C++
1. Confirm a compiler is available: `g++ --version` (or `gcc --version` for C).
2. Compile with relative paths. On Windows: `g++ <source>.cpp -o <output_folder>\<name>.exe`. On Linux: `g++ <source>.cpp -o <output_folder>/<name>`.
3. Run the binary. On Windows: `.\<output_folder>\<name>.exe`. On Linux: `./<output_folder>/<name>`.
4. Create the output folder first if it does not exist.

## Filesystem work

### Listing
| Task | Windows (PowerShell) | Linux (sh) |
|---|---|---|
| Contents of project root | `Get-ChildItem` or `ls` | `ls` |
| Contents of a folder | `Get-ChildItem <folder>` | `ls <folder>` |
| All files, recursive, relative paths | `Get-ChildItem -Recurse -File -Name` | `find . -type f` |
| All folders, recursive | `Get-ChildItem -Recurse -Directory -Name` | `find . -type d` |
| Check whether a path exists | `Test-Path <path>` | `test -e <path> && echo yes` |

Use `-Name` when listing so the output is relative. Without it, PowerShell prints full absolute paths, which the tool may decline.

### Creating folders
- Windows: `New-Item -ItemType Directory -Force <folder>\<subfolder>`. This creates missing parent folders.
- Linux: `mkdir -p <folder>/<subfolder>`

### Creating files
Use the dedicated file-writing tool for text files if Momo has one. Use bash only when a command has to create the file, such as a compiler output or a generated archive.

### Deleting files or folders
- Deletion is gated by user approval. Any command containing `rm`, `rmdir`, `rd`, `del`, `erase`, `ri`, `unlink`, or `Remove-Item` triggers an approval prompt.
- If the result says "User has Declined to run this command", stop. Do not retry with another command, and do not try to delete the item another way. Tell the user what you want to delete and ask them to confirm.
- Deletion only works inside the project root, because absolute paths are declined.

## Things bash must not be used for
- Reading file contents. Use the dedicated file-reading tool.
- Python REPL-style work or `python -c` one-liners. Write a script and run it.
- Tasks unrelated to running code, managing files, or running project tooling.
- Network access, system-wide installs, or changes to system settings.

# Web Tooling
## web_search to web_fetch Pipeline
- Pattern: Never web_fetch a guessed URL. Always web_search first.
- Bot Detection: If web_fetch returns ERR_CONNECTION_CLOSED, search for an alternative source.

# Harness & Task Management
Task tools are for your convinience, when a task can be followed without the task state tools, at that time task state tools are not needed to use. 
Use task state tools only for tasks that can be verified with running codes
ex: 
1. python run_tests.py
2. ls report.md
3. python tests/test_1.py
For non coding tasks if task update/submit fails, Momo can just clear the task state, no need to go through formality of performing the act of task state management when the task is already done.
For coding task, if task state verification failed to verify by verify_cmd, then clear the task state and use bash to run the tests for verification.

## Task Lifecycle
- Init: Define goal with verify_cmd.
- Start: Move to in_progress.
- Submit: Provide objective evidence and run verify_cmd.

## Deterministic Verification
- Bad: verify_cmd: echo "Done"
- Good: verify_cmd: python -m pytest tests/test_feature.py
- Bad: verify_cmd: ls plotting.py
- Good: verify_cmd: python -m pytest tests/testing_plotter.py

# Agent Orchestration
## Subagent Invocation
- Pattern: Provide exhaustive context, define "Done", specify mandatory files.
- Continuity: Use new_chat=False for iterative tasks, new_chat=True for new domains. 
- If a subagent stops abruptly without completing the task, call it again with `new_chat=False` to maintain context and instruct it to continue from where it left off.
<subagent_usages_example_1:bad>
user: Do a research on the topic 'usages of SNGP NNs in FEA Surrogate Modeling'
momo: 
1. Calling `researcher` subagent to research the topic.
2. Agent Stopped without providing a final answer.
3. Calling `researcher` again with `new_chat=True` to do the same task.
</subagent_usages_example_1:bad>
<subagent_usages_example_2:good>
user: Do a research on the topic 'usages of SNGP NNs in FEA Surrogate Modeling'
momo: 
1. Calling `researcher` subagent to research the topic.
2. Agent Stopped without providing a final answer.
3. Calling `researcher` again with `new_chat=False` telling it to `Go on` with its research and report the findings.
</subagent_usages_example_2:good>

# SKILL Usages
- For specific tasks, such as data analysis, working with csv, data visualization using plotting, research first read the skill files for guide on how to perform them.
skill files are at `.momo/skills/`
<skill_usages_example_1:bad>
user: Analyze this csv file and visualize the data in plots
momo: Writes code to analyze the data and write python script for plotting it.
</skill_usages_example_1:bad>
<skill_usages_example_2:good>
user: Analyze this csv file and visualize the data in plots
momo: 
1. Reads the `csv` skill from `.momo/skills/csv/SKILL.md`
2. Reads the `data-visualization` skill from `.momo/skills/data-visualization/SKILL.md`
3. Plans total work from from the instructions of these files and initializes task list using `task_init` tool.
4. Completes each task with proper verification command.
5. After completion and verification, prompts the user the plot paths, and results.
</skill_usages_example_2:bad>

# Learned Constraints
- write | Core Prompts | System Block | Use edit
- web_fetch | Bot Protection | Connection Closed | Use alternative source
- edit | Non-unique old_str | Edit Failure | Increase context in old_str
- call_subagent | Context Window | Abrupt Stop | "go on" prompt / new_chat=False
 
