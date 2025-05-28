import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from core.continuation_agent import ContinuationAgent
from core.agent import Agent
from core.tool import tool
import json

ACCOUNT_AGENT_SYSTEM_PROMPT = """
You are **Account Agent**, responsible for managing user accounts and assigning security levels. You have access to the following tools:  

1. **`create_account`** – Creates a user account using a provided username.  
2. **`authorize_user`** – Assigns a security level to a user.  

- If a request involves creating a new account, first call `create_account` with the provided username.  
- **Wait for confirmation** that the account has been successfully created **before proceeding** to assign a security level.  
- If no security level is specified, assign a default security level of **0**.  
- If a request only involves updating security levels, call `authorize_user` directly.  
- Execute tool calls **sequentially**, never in parallel.  

- **Input:** *"Help me open an account for our new colleague with username: stzhang."*  
  - **Step 1:** Call `create_account("stzhang")`  
  - **Step 2 (only after success):** Call `authorize_user("stzhang", 0)`  

- **Input:** *"Set security level 2 for user alice123."*  
  - Call `authorize_user("alice123", 2)` immediately.  

**Important:** Always ensure that `authorize_user` is only called **after** `create_account` completes successfully.
"""

# Simulate the account creation process
@tool()
def create_account(username: str):
    """Create a new user account."""
    return f"Account created for {username}."

# Simulate the authorization process
@tool(need_approval=True)
def authorize_account(username: str, security_level: int):
    """Authorize a user account by taking a username and a security level."""
    return f"Account {username} authorized with security level {security_level}."

account_agent = ContinuationAgent(instruction=ACCOUNT_AGENT_SYSTEM_PROMPT, tools=[create_account, authorize_account])

def regular_agent():
    account_agent = Agent(instruction=ACCOUNT_AGENT_SYSTEM_PROMPT, tools=[create_account, authorize_account])

    response1 = account_agent.request({"prompt": "Help me open an account for our new colleague with username: tfan."})
    print(f"Response:{json.dumps(response1, indent=4)}")


def continuation_agent():
    account_agent = ContinuationAgent(instruction=ACCOUNT_AGENT_SYSTEM_PROMPT, tools=[create_account, authorize_account])

    response1 = account_agent.request({"prompt": "Help me open an account for our new colleague with username: tfan."})
    print(f"Response:{json.dumps(response1, indent=4)}")

    """
    # Approve all the tool calls
    for to_be_approved in response1["approval_info"]:
        to_be_approved["approved"] = True

    # Call the account agent to process the approved tool calls
    response2 = account_agent.request(response1)
    print(f"Response:{json.dumps(response2, indent=4)}")
    """
    
if __name__ == "__main__":
    # regular_agent()
    continuation_agent()
