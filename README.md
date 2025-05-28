# agent-continuations
The SnapLogic Agent Continuations Prototype Framework
## Topics
* Introduction
* Core components
* Installation
* Classes
* Creating Agents using the framework
    * Create agents
    * Create tools
    * Create suspension functions
* Types of Agent output
* FAQ

### Introduction
The target of this framework is to demonstrate the capability of an Agent to resume from suspension, which can be used in scenarios like human-in-the-loop control, or suspend every N turns.

### Core components
There are three core components in the Agent continuation framework, **Agents**, **Tools**, and **Suspension functions**. 

The definition of an **Agent** in the scope of this project is an LLM + tools combination that carries out actions based on the instruction from the developer and the request from the user to generate a result. The Agent execution is a looped-based process. The LLM within the Agent can be called multiple times, in order to determine the tools to be called and collect results from the function. We will refer to this loop-based process the "Agent loop". There are two types of Agents in this framework, **Agents** and **Continuation Agents**. Continuation Agents are Agents that can be suspended and resumed from tool calls and suspensions.

The definition of a **Tool** is a set of actions that can be described, determined to be used by the LLM within the Agent and called by the framework. A typical tool has a name, a description, parameters, and a function that is binded to the tool that can be executed. A tool can be set to "require approval", which will suspend the Agent execution before the function binded with the tool is executed if a tool is determined to be used by the LLM, so that for example the user can approve or reject the tool call. 

The definition of a **Suspension function** is a boolean function that will be executed at the beginning of every Agent loop. If the result of the suspenstion function is true, the Agent will suspend and exit the Agent loop before the current conversation is sent to the LLM, otherwise it would continue.

### Installation:
#### Recommended but not required
Create a virtual environment (Using Pyenv as an example)
```bash
pyenv virtualenv ac
```
#### Install dependencies
```bash
pip install openai 
```
#### Export OpenAI API key in the current terminal session (optional)
```bash
export OPENAI_API_KEY="your_key_here"
```

### Classes

* agent-continuations
    * core
        * agent.py
        * continuation_agent.py
        * tool.py 
        * suspend_function.py


### Creating Agents using the framework

#### Defining agents
Developers can create an agent by using the `Agent` class or the `ContinuationAgent` class. The `Agent` and `ContinuationAgent` can be used interchangeably, as they share the same constructor, but the behavior might be different based on the user's tool configurations.

The user will send requests to a created agent with the `request` method
```python
helpful_assistant = Agent(instruction="You are a helpful assistant")
helpful_assistant.request({"prompt": "hello!"})
```

To create an agent with tools, pass in the defined tools following the Create tools section
```python
tool_agent = ContinuationAgent(instruction="You are an agent with tools, you can do things.", tools=[hammer, wrench])
tool_agent.request("prompt": "fix my car")
```

Agent can be exposed as tools to create multi-layered agents, here's how you can do it
```python
dev_agent = Agent(instruction="You are a developer", tools=[write_code, attend_meetings])
dev_agent_tool = dev_agent.as_tool("dev_agent_tool", "This tool is an agent that can do work")

dev_manager_agent = ContinuationAgent(instruction="You are a manager with a team of several devs.", tools=[dev_agent_tool, attend_meetings])
```

#### Create tools
Developers can create a tool by using the `@tools() decorator` with a python function, the docstring in the function will be the description of this function. 

```python
@tools()
get_weather(city: str) -> str:
    """Get the weather of a given city"""
    return f"The weather in {city} is nice!"
```

##### Parameters available in the tools decorator
* name: str
* description: str
* need_approval: bool
* is_agent: bool

The `name` and `description` field are used to create tool definitions, if they are not provided the name of the function will be used for `name`, and the docstring of the function will be used for `description`

The `need_approval` and `is_agent` field is used by the framework. The framework will work without these, but there will be no multi-layer or continuation capability

##### Examples
```python
@tools(need_approval=True)
transfer_a_lot_of_money(sender_account_id: str, receiver_account_id: str, amount: int) -> str:
"""Transfer a lot of money from the sender's account to the receiver's account"""
    transaction_id = transfer(sender_account_id, receiver_account_id, 1e7)
return f"transaction_id: {transaction_id}. You lost a lot of money."

# Here's a different way to create an agent tool
@tools(is_agent=True)
ac_dev_agent2(*args, **kwargs):
    """This tool is also an agent that can do work"""
    return ac_dev_agent.reqeust(*args, **kwargs)
```

#### Create suspension functions
Developers can use the `@suspend_function()` with a function to create a suspension function. Note that the function itself cannot have any parameters, the variables used in the suspension function should be defined in the arguments of the `suspend_function` decorator.
##### Examples
```python
@suspend_function(n=2)
def pause_per_n() -> bool:
    res = pause_per_n.n > 0
    if res:
        pause_per_n.n -= 1
    return not res

@suspend_function(start_time=None, duration_minutes=3)
def check_running_time() -> bool:
    if check_running_time.start_time is None:
        check_running_time.start_time = time.time()

    elapsed_time = time.time() - check_running_time.start_time
    should_stop = elapsed_time > (check_running_time.duration_minutes * 60)
    return should_stop
```

The suspension functions can be then added to an agent
```python
helpful_assistant = ContinuationAgent(instruction="You are a helpful assistant.", tools=[get_weather, long_tool], suspension_list=[pause_per_n, check_running_time])
```

### The output of an agent
There are four types of agent output, here are some examples of the possible scenarios.
#### 1. Completed
```json
{
    "result": "I have successfully finished the task...",
    "messages": [
        {
            "role": "user",
            "content": "Please help me fix this ..."
        },
        {...},
    ],
    "end_reason": "completed"
}
```
#### 2. Approval required
The continuation object stores the current conversation, and the tool calls to be approved. The `approval_info` field is a flattened version of `resume_requests`, which are a list of tool calls determined by the LLM. 
```json
{
    "continuation": {
        "messages": {
            "role": "user",
            "content": "Transfer 1 million dollars to my account."
        },
        "resume_request": [
            {
                "id": "call_cYb8yQTRFR3zaWzLMwiBgc10",
                "function": {
                    "arguments": "{\"amount\":\"1,000,000\", ...}",
                    "name": "transfer_funds"
                },
                "type": "function",
                ...
            }
        ],
        "processed": [
            "id": "call_cYb8yQTRFR3zaWzLMwiBgc10", 
            "approved": false
        ] 
    },
    "approval_info": [
        {
            "paths": ["transfer_funds"],
            "path_ids": ["call_cYb8yQTRFR3zaWzLMwiBgc10"],
            "approved": false
        }
    ],
    "end_reason": "approval_required"
}
```
#### 3. Suspended
The suspended output also contains a continuation object, but inside the object there's no resume_request, just the messages array of the current conversation. The `suspend_list` field is a list of suspension functions that lead to the current suspension. 
```json
{
    "continuation": {
        "messages": {
            "role": "user",
            "content": "Help me write 1000 lines of code and push to main."
        }, ...
    },
    "suspend_list": ["pause_per_n"],
    "end_reason": "suspended"
}
```
#### 4. Rejected
The rejected output will contain the conversation history, and the tool call(s) that are rejected
```json
{
    "messages": [
        {
            "role": "user",
            "content": "What's the weather in San Francisco?"
        },
        {...},
    ],
    "rejeted_tool_calls": [
         {
            "id": "call_cYb8yQTRFR3zaWzLMwiBgc10",
            "function": {
                "arguments": "{\"city\":\"San Francisco.\"}",
                "name": "get_weather"
            },
            "type": "function",
            ...
        }
    ],
    "end_reason": "rejected_tool_calls"
}
```

### Sample code
Single layer agent: `account_agent.py` \
Multi layer agent: `hr_agent_cli.py`
