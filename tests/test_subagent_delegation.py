import unittest
from momobot.core.engine import MomobotAgent
from momobot.core.factory import AgentFactory
from momobot.core.state import AgentState
from langchain_core.messages import HumanMessage

class TestSubagentDelegation(unittest.TestCase):
    def test_delegation_flow(self):
        # 1. Setup a Planner agent
        config = {
            "base_url": "http://localhost:11434",
            "context": 50000,
            "recent_window": 6,
            "active_persona": "planner"
        }
        planner = MomobotAgent(config)
        
        # 2. Test the delegate_to_subagent tool directly
        from momobot.tools.subagent_tools import delegate_to_subagent
        
        # We mock the prompt to something simple
        prompt = "What is 2+2?"
        result = delegate_to_subagent.invoke({
            "agent_type": "executor", 
            "prompt": prompt
        })
        
        print(f"Delegation Result: {result}")
        self.assertIn("Sub-agent (executor) response:", result)

if __name__ == "__main__":
    unittest.main()
