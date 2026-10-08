import unittest
from unittest.mock import MagicMock, patch
from momobot.core.engine import MomobotAgent
from momobot.core.factory import AgentFactory
from momobot.core.state import AgentState
from langchain_core.messages import HumanMessage, AIMessage
from momobot.tools.subagent_tools import delegate_to_subagent

class TestSubagentSystem(unittest.TestCase):
    def setUp(self):
        self.config = {
            "base_url": "http://localhost:11434",
            "context": 50000,
            "recent_window": 6,
            "active_persona": "planner"
        }

    def test_tool_registration(self):
        """Verify the tool is correctly registered in the registry."""
        from momobot.tools.registry import registry
        self.assertIn("delegation", registry.CATEGORIES)
        self.assertIn(delegate_to_subagent, registry.CATEGORIES["delegation"])

    def test_persona_access_control(self):
        """Verify only the planner has access to the delegation tool."""
        factory = AgentFactory()
        
        planner_cfg = factory.get_persona_config("planner")
        executor_cfg = factory.get_persona_config("executor")
        
        from momobot.tools.registry import registry
        planner_tools = registry.get_tools(planner_cfg.get("tools", []))
        executor_tools = registry.get_tools(executor_cfg.get("tools", []))
        
        self.assertIn(delegate_to_subagent, planner_tools, "Planner should have delegation tool")
        self.assertNotIn(delegate_to_subagent, executor_tools, "Executor should NOT have delegation tool")

    @patch('momobot.core.engine.ChatOllama.invoke')
    def test_delegation_execution_flow(self, mock_invoke):
        """Test the full flow of delegate_to_subagent tool."""
        # Mock the LLM response for the sub-agent
        # We must use an actual AIMessage because LangGraph/LangChain validates message types
        from langchain_core.messages import AIMessage
        mock_response = AIMessage(
            content="The sub-agent has completed the task successfully.",
            response_metadata={"prompt_eval_count": 100}
        )
        mock_invoke.return_value = mock_response

        # Invoke the tool
        result = delegate_to_subagent.invoke({
            "agent_type": "researcher",
            "prompt": "Research the latest trends in Agentic AI."
        })

        # Verify the result contains the mocked response
        self.assertIn("Sub-agent (researcher) response:", result)
        self.assertIn("The sub-agent has completed the task successfully.", result)
        
        # Verify that the LLM was actually called
        self.assertTrue(mock_invoke.called)

    def test_invalid_agent_type(self):
        """Verify the tool handles invalid agent types gracefully."""
        # Since the tool uses Literal, Pydantic will raise a ValidationError before the function is even called.
        # We test that this validation actually happens.
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            delegate_to_subagent.invoke({
                "agent_type": "non_existent_agent", 
                "prompt": "Hello"
            })

if __name__ == "__main__":
    unittest.main()
