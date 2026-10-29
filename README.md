# Momo

Proactive, high-agency AI agent framework combining PhD-level research rigor with senior engineering efficiency.

## Architecture

### Agent DNA (AgentSpec)
Agents are instances of a unified Agent class configured via AgentSpec.
- Agents: .momo/agents/<name>/agent.md (YAML config + system prompt).
- Skills: .momo/skills/<name>/SKILL.md (Logic + description).

### Prompt Pipeline
PromptBuilder optimizes for Ollama's prompt-prefix caching:
1. Static: Reads prompt_sections from .md files (e.g., identity, soul, tools).
2. Dynamic: Appends context-specific tags (Project instructions, Memory, Environment).

### Subagent System
Subagents operate as Child Sessions managed by SubagentManager.
- Isolated Config: Independent AgentSpec for specific models and tool subsets.
- Nested Execution: Specialized identities (e.g., Researcher, Coder) with unique UI rendering.

### Execution Loop
Deterministic state machine powered by LangGraph:
`START` -> `Compact` -> `Reasoning` -> `Tool Node` -> `Repeat`
- Compaction: Summarizes history when token thresholds are met.
- Resilience: Self-corrects malformed tool calls via feedback loops.

## Getting Started

### Prerequisites
- Ollama: Local instance running.
- Python: 3.10+

### Installation
```bash
pip install -e .
```

### Usage
```bash
momo
```
- --resume: Load latest session.
- --model <tag>: Override default model.
- --project <dir>: Specify project root.

### Project Setup
Run /init in your directory to create the .momo configuration and momo.md state file.

## Commands
- /init: Initialize project metadata.
- /compact: Force context compaction.
- /clear: Reset session.
- /resume [ID]: Restore specific session.
- /btw: Side-query (non-contextual).