from typing import Dict, Any
from rich.console import Console
from cmd.registry import CommandResult

console = Console()

def switch_persona_handler(persona_id: str):
        def handler(args: str, state: Dict[str, Any], context: Dict[str, Any]) -> CommandResult:
            ui = context.get("ui")
            if ui is None or ui.agent is None:
                console.print("[bold red]Error: Agent context not found.[/bold red]")
                return CommandResult()
            
            ui.agent.switch_persona(persona_id)
            return CommandResult()
        return handler