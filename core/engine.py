import sys
import os
import json
import subprocess
import time
import shutil
import sqlite3
from pathlib import Path
from typing import Annotated, Sequence, TypedDict, Dict, Optional, Callable

from langchain_core.messages    import BaseMessage, SystemMessage
from langchain_core.messages    import HumanMessage, AIMessage
from langgraph.graph.message    import add_messages, RemoveMessage
from langgraph.graph            import StateGraph, START, END
from langgraph.prebuilt         import ToolNode
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_ollama           import ChatOllama
from prompt_toolkit import PromptSession
from rich.console import Console

# Modular Imports
from momobot.bootstrap import SESSIONS_DB as sessions_db, prompt_builder
from momobot.tools.taskState            import load, Task
from momobot.core.state                 import AgentState
from momobot.core.factory               import AgentFactory
from momobot.cmd.registry               import CommandRegistry
from momobot.cmd.session_cmds           import register_session_commands

console = Console()

theme_char      =   "✽"
book_cloth      =   "#CC785C"
error           =   "#BF4D43"
focus           =   "#61AAF2"
white           =   "#FFFFFF"
black           =   "#000000"
cloud_light     =   "#BFBFBA"
cloud_dark      =   "#666663"


class MomobotAgent:
    def __init__(self, config: dict):
        self.config = config
        self.factory = AgentFactory()
        
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.context = config.get("context", 50000)
        self.recent_window = config.get("recent_window", 6)
        
        # Persona Management
        self.active_persona = config.get("active_persona", "default")
        self._setup_persona()
        
        # Persistence Setup
        self.conn = sqlite3.connect(sessions_db, check_same_thread=False)
        self.checkpointer = SqliteSaver(self.conn)
        
        self.graph = self._build_graph()
        self.app = self.graph.compile(checkpointer=self.checkpointer)

    def _setup_persona(self):
        """Configures the LLMs based on the active persona."""
        persona_cfg = self.factory.get_persona_config(self.active_persona)
        
        # Standard LLM
        self.llm = self.factory.create_llm(
            persona_id=self.active_persona,
            base_url=self.base_url,
            use_reasoning_model=False
        )
        
        # Reasoning LLM
        self.llm_think = self.factory.create_llm(
            persona_id=self.active_persona,
            base_url=self.base_url,
            use_reasoning_model=True
        )
        
        # Local import to avoid circular dependency with registry
        from momobot.tools.registry import registry
        self.current_tools = registry.get_tools(persona_cfg.get("tools", ["core"]))

    def switch_persona(self, persona_id: str):
        """Switches the active persona and re-configures LLMs and tools."""
        console.print(f"[{focus} on {cloud_dark}] Switching to persona: [/] [bold {book_cloth}] {theme_char} {persona_id}[/]")
        self.active_persona = persona_id
        self._setup_persona()
        
        # Re-build and re-compile the graph to update the ToolNode with new tools
        self.graph = self._build_graph()
        self.app = self.graph.compile(checkpointer=self.checkpointer)
        
    def _build_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("reasoning", self.reasoning_node)
        workflow.add_node("tools", ToolNode(tools=self.current_tools))
        workflow.add_node("compaction", self.compaction_node)

        workflow.add_edge(START, "reasoning")
        workflow.add_conditional_edges(
            "reasoning",
            self.should_continue,
            {
                "tools": "tools",
                "compaction": "compaction",
                "end": END,
            }
        )
        workflow.add_edge("tools", "reasoning")
        workflow.add_edge("compaction", "reasoning")

        return workflow
    def should_continue(self, state: AgentState):
        messages = state.get("messages", [])
        if not messages:
            return "end"
        last_msg = state["messages"][-1]
        if getattr(last_msg, "tool_calls", None):
            return "tools"
        
        usages = state.get("token_usages", 0)
        if usages > self.context:
            return "compaction"
            
        return "end"

    def reasoning_node(self, state: AgentState) -> AgentState:
        from ollama._types import ResponseError
        summary = state.get("summary", "")
        
        try:
            # Use the structured PromptBuilder and pass the active persona prompt
            persona_cfg = self.factory.get_persona_config(self.active_persona)
            persona_prompt = persona_cfg.get("system_prompt", "")
            persona_path = persona_cfg.get("system_prompt_path", "")
            
            system_prompt_text = prompt_builder.build_system_prompt(
                state=state, 
                persona_prompt=persona_prompt,
                persona_path=persona_path
            )
        except Exception:
            system_prompt_text = "You are Momobot, a high-performance AI agent."
            
        system_prompt_message = SystemMessage(content=system_prompt_text + summary)

        for attempt in range(5):
            try:
                use_reasoning = self.config.get("reasoning", False) or state.get("reasoning", False)
                
                if use_reasoning:
                    response = self.llm_think.invoke([system_prompt_message] + state["messages"])
                else:
                    response = self.llm.invoke([system_prompt_message] + state["messages"])
                
                token_usages = response.response_metadata.get("prompt_eval_count", 0)
                
                return {"messages": [response], "token_usages": token_usages}
            
            except ResponseError as e:

                if e.status_code in (500, 502, 503, 504) and attempt < 4:
                    time.sleep(3 * (attempt + 1))
                else:
                    raise
            except Exception as e:

                console.print(f"{theme_char} [dim]Error: {e}[/dim]")
                err_msg = AIMessage(content=f"{theme_char} LLM call failed. Check Ollama. Error: {e}")
                return {"messages":[err_msg],'token_usages':0}

    def compaction_node(self, state: AgentState) -> AgentState:
        messages = list(state.get("messages", []))
        split = max(0, len(messages) - self.recent_window)
        to_compress = messages[:split]
        
        if not to_compress:
            return state


        existing_summary = state.get("summary", "")
        
        root = Path(__file__).parent.parent
        compaction_prompt_file = root / "prompts" / "compaction.md"
        with open(compaction_prompt_file, 'r', encoding='utf-8') as f:
            compaction_prompt = f.read()
            
        if existing_summary:
            compaction_prompt += f"\n\nPrevious summarization:\n{existing_summary}"

        response = self.llm_think.invoke([SystemMessage(content=compaction_prompt)] + to_compress)
        new_summary = response.content
        
        removal_list = [RemoveMessage(id=m.id) for m in to_compress if m.id]

        return {
            "messages": removal_list,
            "summary": new_summary,
            "token_usages": 0
        }

    def run(self, state: AgentState, thread_id: str = "default"):
        """
        Yields (mode, payload) tuples:
        - ("messages", (chunk, metadata))  -> token-level chunk
        - ("values",   state)              -> accumulated state snapshot
        """
        config = {"configurable": {"thread_id": thread_id}}
        for mode, payload in self.app.stream(
            state, config=config, stream_mode=["messages", "values"]
        ):
            yield mode, payload