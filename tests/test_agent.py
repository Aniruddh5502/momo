import unittest
from momobot.core.engine import MomobotAgent
from momobot.core.state import AgentState
from langchain_core.messages import HumanMessage, AIMessage

class TestMomobotAgent(unittest.TestCase):
    def setUp(self):
        # Minimal config for testing
        self.config = {
            "model": "gemma4:31b-cloud",
            "base_url": "http://localhost:11434",
            "context": 50000,
            "recent_window": 6,
            "reasoning": False
        }
        self.agent = MomobotAgent(self.config)

    def test_initialization(self):
        """Test if the agent initializes without errors."""
        self.assertIsNotNone(self.agent.app)
        self.assertIsNotNone(self.agent.llm)

    def _consume_run(self, state: AgentState) -> AgentState:
        """Helper to consume the run generator and return the final state."""
        final_state = state.copy()
        for mode, payload in self.agent.run(state):
            if mode == "values":
                final_state = payload
        return final_state

    def test_run_loop_execution(self):
        """Test if the agent can process a simple input and return a state."""
        initial_state: AgentState = {
            "messages": [HumanMessage(content="Hi, who are you?")], 
            "summary": "", 
            "end": "", 
            "systemInfo": {}, 
            "reasoning": False, 
            "token_usages": 0, 
            "last_action": "init"
        }
        
        try:
            final_state = self._consume_run(initial_state)
            
            # Verify state is returned
            self.assertIsInstance(final_state, dict)
            # Verify messages were added
            self.assertTrue(len(final_state["messages"]) > 1)
            # Verify the last message is an AIMessage
            self.assertIsInstance(final_state["messages"][-1], AIMessage)
        except Exception as e:
            self.fail(f"Agent run loop failed with error: {e}")

    def test_state_persistence(self):
        """Test if the agent can handle multiple turns by passing the state back."""
        state: AgentState = {
            "messages": [HumanMessage(content="My name is Momo.")], 
            "summary": "", 
            "end": "", 
            "systemInfo": {}, 
            "reasoning": False, 
            "token_usages": 0, 
            "last_action": "init"
        }
        
        # Turn 1
        state = self._consume_run(state)
        
        # Turn 2: Add a new message to the existing state
        state["messages"].append(HumanMessage(content="What is my name?"))
        final_state = self._consume_run(state)
        
        self.assertTrue(len(final_state["messages"]) > 2)
        self.assertIsInstance(final_state["messages"][-1], AIMessage)

if __name__ == "__main__":
    unittest.main()
