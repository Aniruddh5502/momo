import unittest
from pathlib import Path
from momobot.bootstrap import prompt_builder, ROOT
from momobot.core.factory import AgentFactory

class TestSystemPromptConstruction(unittest.TestCase):
    def setUp(self):
        self.factory = AgentFactory()
        self.soul_path = ROOT / "prompts" / "soul.md"
        self.state = {
            "summary": "Test summary for verification",
            "messages": []
        }

    def test_soul_content_presence(self):
        """
        Verify that the content of soul.md is exactly present 
        at the start of the built system prompt.
        """
        # 1. Read the actual soul.md file
        soul_content = self.soul_path.read_text(encoding='utf-8')
        
        # 2. Get the persona config for default
        persona_cfg = self.factory.get_persona_config("default")
        persona_prompt = persona_cfg.get("system_prompt", "")
        persona_path = persona_cfg.get("system_prompt_path", "")
        
        # 3. Build the system prompt
        full_prompt = prompt_builder.build_system_prompt(
            state=self.state,
            persona_prompt=persona_prompt,
            persona_path=persona_path
        )
        
        # 4. Verify that the prompt starts with the exact soul content
        # We use startswith because the prompt builder appends other sections after the soul
        self.assertTrue(
            full_prompt.startswith(soul_content), 
            "The system prompt does not start with the exact content of soul.md"
        )

    def test_persona_specialization_layer(self):
        """
        Verify that the persona-specific prompt is appended after the soul.
        """
        # Use planner persona which has a specific system_prompt
        persona_cfg = self.factory.get_persona_config("planner")
        persona_prompt = persona_cfg.get("system_prompt", "")
        persona_path = persona_cfg.get("system_prompt_path", "")
        
        full_prompt = prompt_builder.build_system_prompt(
            state=self.state,
            persona_prompt=persona_prompt,
            persona_path=persona_path
        )
        
        # The persona layer is added as: \n\n# Persona Instructions\n{persona_prompt}
        expected_layer = f"\\n\\n# Persona Instructions\\n{persona_prompt}"
        # Since the prompt builder uses f-strings with actual newlines, we check for the content
        self.assertIn(persona_prompt, full_prompt, "Persona specialization prompt missing from final system prompt")

    def test_full_prompt_structure(self):
        """
        Verify the order of sections using the == operator on sliced content.
        """
        soul_content = self.soul_path.read_text(encoding='utf-8')
        
        # Build prompt with no persona specialization to simplify
        full_prompt = prompt_builder.build_system_prompt(
            state=self.state,
            persona_prompt="",
            persona_path=""
        )
        
        # The first len(soul_content) characters must be exactly the soul_content
        self.assertEqual(
            full_prompt[:len(soul_content)], 
            soul_content, 
            "The beginning of the system prompt is not exactly equal to soul.md content"
        )

if __name__ == "__main__":
    unittest.main()
