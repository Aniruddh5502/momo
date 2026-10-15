from momo.core.settings import Settings
from pathlib import Path
import frontmatter

settings = Settings()

from rich.console import Console
from pathlib import Path
import frontmatter


def get_agents(agents_path:Path)->list[dict]:
    agents = sorted(agents_path.rglob("*.md"))
    
    # Now for each agent file we get its contents as a dict
    agents_descriptions = []
    for agent in agents:
        with open(agent, 'r', encoding='utf-8') as file:
            post = frontmatter.load(file)
        agent_content = {
            "name"  : post.get("name"),
            "model" : post.get("model"),
            "tool_catagories":post.get("tool_catagories"),
            "description":post.get("description"),
            "color":post.get("color"),
            "sessions":post.get("sessions"),
            "type":post.get("type"),
            "path":agent,
            "content":post.content,
        }
        agents_descriptions.append(agent_content)
    return agents_descriptions

def get_skills(skills_path:Path)->list[dict]:
    skills = sorted(skills_path.rglob("SKILL.md"))
    
    skills_contents = []
    # now for each skill file we shall extract the fields
    for skill in skills:
        with open(skill, 'r', encoding='utf-8') as file:
            post = frontmatter.load(file)
        skill_content = {
            "name":post.get("name"),
            "description":post.get("description"),
            "metadata":post.get("metadata"),
            "path":skill,
            "content":post.content,
        }
        skills_contents.append(skill_content)
    return skills_contents


# Now here I plan to only include the name, and when_to_use field for 
# subagent and name and description filed for skills section and send it 
# as a part of the system prompt to the prompt builder. And the working 
# directory path will be taken from settings

def agent_and_skill(root:Path)->str:
    """this file reads the .momo/ contents and sends them to be added
    to the main agents system prompt"""
    # root is the .momo/ location. from where we make agents/ and skills/
    agents_dir = root / "agents"
    skills_dir = root / "skills"
    
    # now we run the get_agents function to get the list[dict] list of details
    # of each agent
    agents = get_agents(agents_dir)
    
    # similarly we get the get_skills function to get the list[dict] list 
    # of skills and its frontmatter and content data
    skills = get_skills(skills_dir)
    
    # Now for all the agents we iterate and get the "name", "when_to_use"
    # parameters and concatanate them in this "agents_prompt"
    agents_prompt = ""
    for agent in agents:
        name = agent["name"]
        description = agent["description"]
        agents_prompt += f"\nName: {name}\nDescription: {description}\n"
    agents_prompt_ = f"\n<agents>{agents_prompt}</agents>\n"
    
    # Now same thing for skills
    skills_prompt = ""
    for skill in skills:
        name = skill["name"]
        description = skill["description"]
        skills_prompt += f"\nName: {name}\nDescription: {description}\n"
    skills_prompt_ = f"\n<skills>{skills_prompt}</skills>"
    
    # I think we should also load the .momo/momo.md file if its available
    momo_md = root / "momo.md"
    try:
        with open(momo_md, 'r', encoding='utf-8') as file:
            momo = file.read()
        momo_ = f".momo/momo.md\nThis is the root of working directory\n{momo}"
    except Exception as e:
        momo_ = f".momo/momo.md\n This files doesn't exist"
    agent_and_skills = f"{agents_prompt_}{skills_prompt_}{momo_}"
    return agent_and_skills

if __name__ == "__main__":
    from rich.console import Console
    from rich.pretty import Pretty
    console = Console()
    
    
    from momo.core.settings import Settings
    settings = Settings()
    root = settings.project_root / ".momo"
    print(agent_and_skill(root))