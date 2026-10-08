import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from langchain_ollama import ChatOllama

class AgentFactory:
    """
    Responsible for creating LLM instances and toolsets based on 
    the agents_config.yaml file.
    """
    
    def __init__(self, config_path: str = "momobot/config/agents_config.yaml"):
        self.config_path = Path(config_path)
        self.configs = self._load_configs()

    def _load_configs(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            # Default configuration if file is missing
            return {
                "default": {
                    "model": "gemma4:31b-cloud",
                    "system_prompt": "You are Momobot, a high-performance AI agent.",
                    "tools": ["core", "web", "harness"],
                    "temperature": 0.2,
                    "reasoning": False
                }
            }
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f).get("agents", {})

    def get_persona_config(self, persona_id: str) -> Dict[str, Any]:
        return self.configs.get(persona_id, self.configs.get("default", {}))

    def create_llm(self, persona_id: str, base_url: str, num_ctx: int = 50000, use_reasoning_model: bool = False) -> ChatOllama:
        config = self.get_persona_config(persona_id)
        
        # Local import to avoid circular dependency with registry
        from momobot.tools.registry import registry
        tools = registry.get_tools(config.get("tools", ["core"]))
        
        # Determine model
        model_name = config.get("model", "gemma4:31b-cloud")
        
        # For distilled reasoning models, we often need to be careful with the 'reasoning' flag.
        # If the model is a GGUF distilled version, it might not support the native Ollama reasoning API
        # but instead outputs <thought> tags in the content.
        
        llm = ChatOllama(
            model=model_name,
            reasoning=use_reasoning_model,
            temperature=config.get("temperature", 0.2),
            base_url=base_url,
            num_ctx=num_ctx,
            stream=False,
        ).bind_tools(tools=tools)
        
        return llm
