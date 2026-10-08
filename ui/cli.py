import sys
import shutil, json
import logging
import uuid
from typing import Optional, Dict, Any
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.markup import escape
from langchain_core.messages import (
    HumanMessage, AIMessage, AIMessageChunk, BaseMessage, ToolMessage
)
from bootstrap import config
from ui.animation import ThinkingAnimation
from core.engine import MomobotAgent
from core.state import AgentState
from cmd.registry import CommandRegistry, CommandResult
from cmd.session_cmds import register_session_commands, register_session_name

anim = ThinkingAnimation()

# Set up professional logging for the UI layer
logger = logging.getLogger("momobot.ui.cli")

theme_char      =   "✽"
book_cloth      =   "#CC785C"
error           =   "#BF4D43"
focus           =   "#61AAF2"
white           =   "#FFFFFF"
black           =   "#000000"
cloud_light     =   "#BFBFBA"


class MomobotInterface:
    """
    Production-grade CLI Interface for Momobot.
    Handles user input, session state management, and formatted output.
    """
    def __init__(self, agent: MomobotAgent, config: Dict[str, Any]):
        self.agent = agent
        self.config = config
        self.console = Console()
        self.registry = CommandRegistry()
        self._last_printed_index = 0

        # Streaming flags
        self._stream_open = False       # mid-way through an answer block?
        self._reasoning_open = False    # mid-way through a reasoning block?
        self._streamed_any = False      # did anything visible stream this turn?

        register_session_commands(self.registry)

        self.theme_char = config.get("theme_char", "✽")
        self.ai_response = "⬤"
        self.session = self._make_session()

        # The thread_id is the key for LangGraph persistence
        self.current_thread_id = str(uuid.uuid4())[:8]

        # State is partially managed by the checkpointer,
        # but we keep a local mirror for UI responsiveness
        self.state: AgentState = self._initialize_state()

    def _initialize_state(self) -> AgentState:
        """Creates a clean starting state for the agent."""
        return {
            "messages": [],
            "summary": "",
            "end": "",
            "systemInfo": {},
            "reasoning": False,
            "token_usages": 0,
            "last_action": "init"
        }

    def _make_session(self) -> PromptSession:
        """Configures the prompt toolkit session with production keybindings."""
        bindings = KeyBindings()

        @bindings.add("escape", "enter")
        def _submit(event):
            event.current_buffer.validate_and_handle()

        @bindings.add("enter")
        def _newline(event):
            event.current_buffer.insert_text("\n")

        return PromptSession(key_bindings=bindings, multiline=True)

    # ------------------------------------------------------------------
    # Rendering (used for replay and as a fallback when nothing streamed)
    # ------------------------------------------------------------------
    def _render_message(self, message: BaseMessage):
        if isinstance(message, HumanMessage):
            self.console.print(" ")
            self.console.rule(style="dim")
            self.console.print(
                f"[bold {book_cloth}]❯[/bold {book_cloth}] "
                f"[bold]{escape(message.content)}[/bold]"
            )
            self.console.rule(style="dim")

        elif isinstance(message, AIMessage):
            
            reasoning = message.additional_kwargs.get("reasoning_content")
            if reasoning:
                self.console.print(f"[dim]{self.theme_char} {escape(str(reasoning))}[/dim]")

            if message.content:
                self.console.print("")
                self.console.print(f"[{book_cloth}]{self.theme_char}[/] ", end="")
                self.console.print(Markdown(message.content))
                self.console.print("")

        elif isinstance(message, ToolMessage):
            self._render_tool_result(message)

    def _render_tool_result(self, message):
        """Render a ToolMessage using the standardized create_tool_response shape."""
        name = getattr(message, "name", None) or "tool"

        # Sub-agent progress and result are printed live by the tool itself
        # (momobot/tools/subagent_tools.py); nothing to render here.
        if name == "delegate_to_subagent":
            return

        # --- Normalize content (str, list of content blocks, or other) ---
        content = message.content
        if isinstance(content, list):
            content = "\n".join(
                b.get("text", "") if isinstance(b, dict) else str(b)
                for b in content
            )
        elif not isinstance(content, str):
            content = str(content)

        # --- Parse the create_tool_response payload ---
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = None

        if not isinstance(parsed, dict) or "status" not in parsed:
            # Fallback for unstructured results: one-line preview.
            preview = content.replace("\n", " ").strip()
            if len(preview) > 100:
                preview = preview[:100].rstrip() + "…"
            self.console.print(
                f"{theme_char} [dim]{name}[/dim]  [dim]{escape(preview)}[/dim]"
            )
            return

        # --- Extract the fields we care about ---
        status     = parsed.get("status", "success")
        error_code = parsed.get("error_code")
        error_msg  = parsed.get("error_message")
        hint       = parsed.get("recovery_hint")
        meta       = parsed.get("metadata") or {}

        marker = {"success": "✓", "warning": "!", "error": "✗"}.get(status, "·")
        color  = {"success": f"{focus}", "warning": "yellow", "error": f"{error}"}.get(status, "dim")

        # --- One-line summary ---
        # Priority: state_delta (what the tool did) > error_message > nothing
        summary = meta.get("state_delta") or error_msg
        if summary:
            summary = str(summary).replace("\n", " ").strip()
            if len(summary) > 120:
                summary = summary[:120].rstrip() + "…"

        header = f"{theme_char} [dim]{name}[/dim]  [{color}]{marker}[/{color}]"
        if summary:
            header += f"  [dim]{escape(summary)}[/dim]"
        self.console.print(header)

        # --- Extra detail on failure ---
        if status in ("error", "warning"):
            if error_code and str(error_code) not in (summary or ""):
                self.console.print(
                    f"     [dim]code:[/dim] [{color}]{escape(str(error_code))}[/{color}]"
                )
            if error_msg and str(error_msg) not in (summary or ""):
                self.console.print(f"     [dim]msg:[/dim]  {escape(str(error_msg))}")
            if hint:
                self.console.print(
                    f"     [dim]hint:[/dim] [yellow]{escape(str(hint))}[/yellow]"
                )

    def display_updates(self, state: AgentState, show_footer: bool = False):
        """
        Prints only the messages generated since the last update.
        """
        messages = state.get("messages", [])

        for i in range(self._last_printed_index, len(messages)):
            self._render_message(messages[i])
            self._last_printed_index = i + 1

        if not show_footer:
            return

        usages = state.get("token_usages", 0)
        cols, _ = shutil.get_terminal_size(fallback=(80, 24))
        plain = f"Token Usages: {usages}"          # measure without markup
        pad = max(0, cols - len(plain))
        self.console.print(f"\n{' ' * pad}[dim]{plain}[/dim]")

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------
    def _close_open_blocks(self):
        """Terminate any in-progress reasoning/answer block with a newline."""
        if self._reasoning_open:
            self.console.print("\n")
            self._reasoning_open = False
        if self._stream_open:
            self.console.print("")
            self._stream_open = False

    def handle_input(self, user_input: str) -> Optional[bool]:
        user_input = user_input.strip()
        if not user_input:
            return True

        if user_input.lower() in {"x", "c", "exit", "quit", "end"}:
            try:
                self.agent.app.update_state(
                    {"configurable": {"thread_id": self.current_thread_id}},
                    self.state,
                )
                register_session_name(self.current_thread_id, user_input)
                self.console.print(
                    f"{self.theme_char} [dim]Session {self.current_thread_id} saved.[/dim]"
                )
            except Exception as e:
                self.console.print(f"[dim red]Could not save session: {e}[/dim red]")

            self.console.print(f"{self.theme_char} [bold]Shutting down...[/bold]")
            return False

        # --- Slash commands ---
        cmd_result: Optional[CommandResult] = self.registry.execute(
            user_input, self.state, {"ui": self}
        )
        if cmd_result is not None:
            if cmd_result.state is not None:
                self.state = cmd_result.state
            if cmd_result.render:
                self._last_printed_index = 0
                self.display_updates(self.state)          # no footer on replay
            else:
                self._last_printed_index = len(self.state.get("messages", []))
            return True

        # --- Regular chat: hand off to the agent ---
        register_session_name(self.current_thread_id, user_input)

        reasoning_mode = False
        if "/think" in user_input:
            user_input = user_input.replace("/think", "").strip()
            reasoning_mode = True

        self.state["messages"] = self.state.get("messages", [])
        self.state["messages"].append(HumanMessage(content=user_input))
        self.state["reasoning"] = reasoning_mode
        self.state["last_action"] = "input"

        start_idx = len(self.state["messages"])

        self._stream_open = False
        self._reasoning_open = False
        self._streamed_any = False

        anim.start()

        try:
            for mode, payload in self.agent.run(
                self.state, thread_id=self.current_thread_id
            ):
                if mode == "messages":
                    chunk, metadata = payload
                    self._handle_stream_chunk(chunk, metadata)
                elif mode == "values":
                    self.state = payload

            anim.stop()
            self._close_open_blocks()

            messages = self.state.get("messages", [])
            if self._streamed_any:
                self._last_printed_index = len(messages)
            else:
                self._last_printed_index = min(start_idx, len(messages))
            self.display_updates(self.state, show_footer=True)

        except Exception as e:
            anim.stop()
            self._close_open_blocks()
            logger.exception("Error during agent execution")
            self.console.print(f"[bold red]Critical Error:[/bold red] {escape(str(e))}")
            self.console.print("[dim]Please check logs for details.[/dim]")
        finally:
            anim.stop()

        return True

    def _handle_stream_chunk(self, chunk, metadata):
        """Print AI tokens as they arrive; print tool results whole."""
        node = (metadata or {}).get("langgraph_node", "")
        if node == "compaction":
            return

        if isinstance(chunk, AIMessageChunk):
            reasoning = (chunk.additional_kwargs or {}).get("reasoning_content")
            content = chunk.content

            if isinstance(content, list):
                content = "".join(
                    b.get("text", "") if isinstance(b, dict) else str(b)
                    for b in content
                )

            if content and not self._stream_open:
                content = content.lstrip("\n")

            if reasoning or content:
                anim.stop()

            if reasoning:
                if not self._reasoning_open:
                    self.console.print(f"[dim]{self.theme_char} thinking[/dim]")
                    self._reasoning_open = True
                self._streamed_any = True
                self.console.print(
                    str(reasoning),
                    end="", markup=False, highlight=False, soft_wrap=True,
                    style="dim",
                )

            if content:
                if self._reasoning_open:
                    self.console.print("\n")
                    self._reasoning_open = False
                if not self._stream_open:
                    self.console.print(f"[{book_cloth}]{self.theme_char}[/] ", end="")
                    self._stream_open = True
                self._streamed_any = True
                self.console.print(
                    content,
                    end="", markup=False, highlight=False, soft_wrap=True,
                )

        elif isinstance(chunk, ToolMessage):
            anim.stop()
            self._close_open_blocks()
            self._streamed_any = True
            self._render_tool_result(chunk)
            anim.start()

    def run(self):
        """Main execution loop for the CLI."""
        print("\n" * 10)
        from config import config
        self.console.print(Panel(
            f"""\n            {self.theme_char} \\  [dim]Type 'exit' or 'quit' to leave.[/dim]\n            \n\n                Model: {config['model']} """,
            title="Momobot",
            title_align="left",
            border_style=f"{book_cloth}",
            height=8,
        ))
        print("\n" * 5)

        while True:
            try:
                self.console.rule(style="dim")
                user_input = self.session.prompt("❯  ").strip()
                self.console.rule(style="dim")
            except KeyboardInterrupt:
                self.console.rule(style="dim")
                self.console.print(f"\n{theme_char} Exiting..\n")
                break

            if not self.handle_input(user_input):
                self.console.rule(style="dim")
                break

        return True

def main():
    import bootstrap
    from core.engine import MomobotAgent

    config = bootstrap.config
    agent = MomobotAgent(config)
    interface = MomobotInterface(agent=agent, config=config)
    interface.run()

if __name__ == "__main__":
    main()