from pathlib import Path
import sys
import os

# Add the project root to sys.path to import from momo.core
sys.path.append(os.getcwd())
from momo.core.discovery import discover_momo_resources

def test_discovery():
    test_root = Path("test_momo_env")
    resources = discover_momo_resources(test_root)
    
    print(f"Discovered {len(resources)} resources.")
    
    # Expected outcomes
    # 1. agent1.md
    # 2. agent_nested.md
    # 3. skill1/SKILL.md
    # 4. skill2/SKILL.md
    
    expected_names = {"agent1", "agent_nested", "skill1", "skill2"}
    found_names = {r.name for r in resources}
    
    print(f"Expected names: {expected_names}")
    print(f"Found names: {found_names}")
    
    # Check for frontmatter
    for r in resources:
        print(f"Resource: {r.name} | Type: {r.type} | Metadata: {r.metadata}")
        if not r.metadata:
            print(f"FAILED: No metadata for {r.name}")
            sys.exit(1)

    if found_names != expected_names:
        print("FAILED: Mismatch in discovered resources")
        sys.exit(1)
        
    print("SUCCESS: All resources discovered and frontmatter parsed correctly.")
    sys.exit(0)

if __name__ == "__main__":
    test_discovery()
