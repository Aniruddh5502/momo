import unittest
from momobot.core.factory import AgentFactory
from pathlib import Path
import yaml

class TestAgentFactory(unittest.TestCase):
    def setUp(self):
        self.factory = AgentFactory()
        self.config_path = Path("momobot/config/agents_config.yaml")

    def test_config_priority_chain(self):
        """
        Test the priority chain: 
        YAML Value > Factory Fallback > Global Default
        """
        # 1. Verify YAML value is loaded for a specific persona
        with open(self.config_path, 'r', encoding='utf-8') as f:
            yaml_data = yaml.safe_load(f)
            planner_model = yaml_data['agents']['planner']['model']
        
        config = self.factory.get_persona_config("planner")
        self.assertEqual(config.get("model"), planner_model, "Factory failed to load the specific model from YAML for 'planner'")

        # 2. Verify fallback to 'default' persona when persona doesn't exist
        # We use a random string to ensure it's not in the YAML
        ghost_config = self.factory.get_persona_config("non_existent_persona_12345")
        default_model = self.factory.get_persona_config("default").get("model")
        self.assertEqual(ghost_config.get("model"), default_model, "Factory failed to fall back to 'default' persona config")

    def test_hardcoded_fallback_integrity(self):
        """
        Verify that if the YAML is missing or corrupted, the hardcoded 
        fallback in factory.py is actually 'gemma4:31b-cloud'
        """
        # Create a temporary factory with a non-existent config path
        temp_factory = AgentFactory(config_path="non_existent_file.yaml")
        
        # This should trigger the _load_configs() fallback dictionary
        config = temp_factory.get_persona_config("default")
        self.assertEqual(config.get("model"), "gemma4:31b-cloud", "Hardcoded fallback in factory.py is not gemma4:31b-cloud")

    def test_llm_creation_model_resolution(self):
        """
        Verify that create_llm actually uses the resolved model name
        """
        # We don't need to actually call the Ollama API, we just check the 
        # logic that determines the model_name before passing it to ChatOllama
        
        # Test case: Persona exists in YAML
        # We'll mock the config to be sure
        persona_id = "planner"
        config = self.factory.get_persona_config(persona_id)
        expected_model = config.get("model")
        
        # Since create_llm returns a ChatOllama object, we check its .model attribute
        llm = self.factory.create_llm(persona_id=persona_id, base_url="http://localhost:11434")
        self.assertEqual(llm.model, expected_model, f"LLM created with wrong model. Expected {expected_model}, got {llm.model}")

if __name__ == "__main__":
    unittest.main()
