from typing import List, Dict, Any
from langchain_core.tools import BaseTool

# Import all tools from their respective modules
from momobot.tools.basic_tools import read, edit, search, web_fetch, listDir
from momobot.tools.shell import shell
from momobot.tools.write import write
from momobot.tools.taskState import task_init, task_update, task_replan, task_clear
from momobot.tools.subagent_tools import delegate_to_subagent

class ToolRegistry:
    """
    Centralized registry for Momobot tools.
    Allows grouping tools into 'toolsets' based on capability.
    """
    
    # Define tool categories
    CATEGORIES = {
        "core": [read, edit, listDir, shell, write],
        "web": [search, web_fetch],
        "harness": [task_init, task_update, task_replan, task_clear],
        "delegation": [delegate_to_subagent],
    }

    @classmethod
    def get_tools(cls, tool_requests: List[str]) -> List[BaseTool]:
        """
        Retrieve a list of tools based on the requested categories or specific tool names.
        
        Args:
            tool_requests: List of category names (e.g. ['core', 'web']) 
                           or specific tool function names.
        """
        final_tools = []
        seen_tools = set()

        # Flatten all available tools for name-based lookup
        all_available_tools = []
        for category_tools in cls.CATEGORIES.values():
            all_available_tools.extend(category_tools)

        for request in tool_requests:
            # 1. Check if it's a category
            if request in cls.CATEGORIES:
                for tool in cls.CATEGORIES[request]:
                    if tool not in final_tools:
                        final_tools.append(tool)
            else:
                # 2. Check if it's a specific tool name
                found = False
                for tool in all_available_tools:
                    if tool.__name__ == request:
                        if tool not in final_tools:
                            final_tools.append(tool)
                        found = True
                        break
                if not found:
                    # We use a print here because we are in a registry, 
                    # but in production this should be a logged warning.
                    print(f"Warning: Tool or category '{request}' not found in registry.")

        return final_tools

# Instance for easy access
registry = ToolRegistry()
