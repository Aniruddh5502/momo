# Momo Tool Usage Protocol

This document defines the deterministic usage patterns for Momo's tools. Adhere to these patterns to ensure reliability and avoid system blocks.

# Filesystem Tooling

## read & listDir
- Pattern: Always listDir before read if the file path is not explicitly confirmed by the user or a previous listDir call.
- Constraint: Use absolute paths or relative paths starting with ./.

## write
- Pattern: Use for new file creation or full overhauls of non-protected files.
- Constraint: DO NOT use write to overwrite core system prompts (e.g., soul.md, tool.md, user.md files inside .momo/prompts/ folder). Use edit for these files.

## edit
- Pattern: The only permitted tool for updating core prompts and large source files.
- Requirement: old_str must be a unique, exact match.
- Strategy: Perform multiple targeted edit calls for large changes.

# Shell Tooling

## General Execution
- Pattern: Use dir and type to verify filesystem changes immediately after write or edit.
- Error Handling: A non-zero exit_code is a failure. Analyze stderr and iterate.

# Web Tooling

## web_search to web_fetch Pipeline
- Pattern: Never web_fetch a guessed URL. Always web_search first.
- Bot Detection: If web_fetch returns ERR_CONNECTION_CLOSED, search for an alternative source.

# Harness & Task Management

## Task Lifecycle
- Init: Define goal with verify_cmd.
- Start: Move to in_progress.
- Submit: Provide objective evidence and run verify_cmd.

## Deterministic Verification
- Bad: verify_cmd: echo "Done"
- Good: verify_cmd: python -m pytest tests/test_feature.py

# Agent Orchestration

## Subagent Invocation
- Pattern: Provide exhaustive context, define "Done", specify mandatory files.
- Continuity: Use new_chat=False for iterative tasks, new_chat=True for new domains.
- Recovery: Use "go on" prompt if subagent hits recursion limit.

# Learned Constraints

- write | Core Prompts | System Block | Use edit
- web_fetch | Bot Protection | Connection Closed | Use alternative source
- edit | Non-unique old_str | Edit Failure | Increase context in old_str
- call_subagent | Context Window | Abrupt Stop | "go on" prompt / new_chat=False
 
