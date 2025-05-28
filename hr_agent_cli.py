from core.continuation_agent import ContinuationAgent
from core.agent import Agent
from core.tool import tool
from core.suspend_function import suspend_function
from account_agent import account_agent
import json

HR_AGENT_SYSTEM_PROMPT = """
You are **HR Agent**, responsible for handling HR-related tasks, including onboarding new colleagues. You have access to the following tools:  

1. **`send_email`** – Sends emails to specified recipients.  
2. **`account_agent`** – Manages user accounts, including creation and security level assignment.  

### **Key Responsibilities:**  
- **Onboarding New Employees:**  
  * Send a welcome email to the new colleague.  
  * Meanwhile, call `account_agent` to create their account and assign a security level.  

- **Other HR Tasks:**  
  - Use `account_agent` for any account-related tasks, such as updating security levels or future account modifications.  
  - Use `send_email` for any HR-related communications as needed.  

### **Execution Rules:**  
- Always send the welcome email **before** initiating account creation.  
- Ensure sequential execution—**wait for email confirmation** before calling `account_agent`.  
- If any additional instructions are provided in a request, follow them accordingly while maintaining logical execution order.  

### **Example Workflow:**  
- **Input:** *"Onboard our new colleague stzhang, their email is stzhang@example.com."*  
    Using Parallel tool call to:
  - Call `send_email(recipient="stzhang@example.com", subject="Welcome!", message="Welcome to the team, stzhang! We're excited to have you.")`  
  - Call `account_agent("Help me open an account for our new colleague with username: stzhang.")`  

Your role is to ensure smooth HR operations, with a focus on structured and efficient task execution.
"""

@tool()
def send_email_tool(recipient: str, subject: str, message: str):
    """Send an email to the specified recipient."""
    return f"Email sent to {recipient} with subject '{subject}' and message '{message}'."

# To create a tool that is an agent.
# account_agent_tool = account_agent.as_tool(name="account_agent_tool", description="This tool handles all account-related tasks based on natural language instructions. It can create accounts, assign security levels, and manage user access as needed. Input example: \"Help me open an account for our new colleague with username: tfan.\"")

# This is a different way to create a tool that is an agent.
@tool(is_agent=True)
def account_agent_tool(*args, **kwargs):
    """This tool handles all account-related tasks based on natural language instructions. It can create accounts, assign security levels, and manage user access as needed. Input example: \"Help me open an account for our new colleague with username: tfan.\""""
    return account_agent.request(*args, **kwargs)

@suspend_function(n=2)
def pause_per_n() -> bool:
    """
    This function demonstrates the usage of the suspend_function decorator.
    It pauses for 'n' calls and then returns False.
    """
    # Access the state variable 'n' directly from the function object
    # The decorator attaches 'n' as an attribute to the decorated function (pause_per_n)
    res = pause_per_n.n > 0
    if res:
        pause_per_n.n -= 1
    return not res

hr_agent = ContinuationAgent(instruction=HR_AGENT_SYSTEM_PROMPT, tools=[send_email_tool, account_agent_tool], suspension_list=[pause_per_n])
# hr_agent = Agent(instruction=HR_AGENT_SYSTEM_PROMPT, tools=[send_email_tool, account_agent_tool])

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HR Agent CLI for handling HR-related tasks.")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--json", help="Path to a JSON file containing the prompt dictionary.")
    group.add_argument("--prompt", help="A string prompt to be used as input.")

    args = parser.parse_args()

    input_data = {}
    if args.json:
        try:
            with open(args.json, 'r') as f:
                input_data = json.load(f)
        except FileNotFoundError:
            print(f"Error: JSON file not found at {args.json}")
            exit(1)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON format in {args.json}")
            exit(1)
    elif args.prompt:
        input_data = {"prompt": args.prompt}

    hr_response1 = hr_agent.request(input_data)
    print(json.dumps(hr_response1, indent=4))