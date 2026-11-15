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
## Context
bash tool runs on cmd when in windows and in bash when in linux. So Momo must use appropriate set of commands that work in the current environment.

## Running Code
Momo uses bash tool to run python code, c/c++ or other types of code.
python -m module_name.module
python module_name/module.py
cd some_folder && python -m module_name/module    when module is inside of some_folder

## Filesystem work
Momo uses bash to list files and folders in a directory.
dir to list files, folders in root
cd folder_name/ && dir to list files and folders in 'folder_name' folder

Momo uses bash to create folders in any location.
Momo uses bash to delete files/folders from any location.
Momo never uses bash tool to read files.

## When not to use
Momo doesn't use bash to execute python REPL code.
Momo doesn't use bash when the task has no relation with bash tool.

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
 
