from typing import List, Dict, Any, Tuple, Callable
from core.tool import Tool, tool
from enum import Enum, auto
from openai import OpenAI
from functools import wraps
import json

class AgentExecutionStatus(Enum):
    RUNNING = auto()
    COMPLETED = auto()
    SUSPENDED = auto()
    REJECTED = auto()
    ERROR = auto()
    
TERMINAL_STATUSES = [AgentExecutionStatus.COMPLETED, AgentExecutionStatus.SUSPENDED, AgentExecutionStatus.REJECTED, AgentExecutionStatus.ERROR]

class Agent:
    def __init__(self, instruction: str, tools: List[Callable]):
        """
        Initialize a new Agent.
        
        Args:
            instruction: The system prompt for the agent
            tools: List of tools the agent can use
        """
        self.instruction = instruction
        self.tools = tools
        self.tool_map = {}
        for tool in tools:
            if hasattr(tool, '_tool'):
                self.tool_map[tool._tool.name] = tool
            else:
                raise ValueError("Did you forget to use the decorator @tool?")
        self.client = OpenAI()
        
    def request(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Agents processing lives in this scope only, to maintain statelessness.
        """
        messages = self._form_input(input)
        while True:
            status, raw_tool_calls = self._call_model_and_check_status(messages)
            if status in TERMINAL_STATUSES:
                break
            approved_tool_calls = self._prepare_tools(raw_tool_calls)
            self._call_all_tools(approved_tool_calls, messages)
            
        return self._create_response(messages)
    
    def as_tool(self, name: str, description: str, need_approval: bool = False) -> Callable:
        @wraps(self.request)
        def bound_request(input: Dict[str, Any]) -> Dict[str, Any]:
            """
            Bind the request method to the agent instance.
            
            Args:
                input: The input data
                
            Returns:
                Dict: The agent's response
            """
            return self.request(input)
        
        if description is None:
            raise ValueError("description is required for the tool")
        
        decorated_request = tool(
            name=name,
            description=description,
            need_approval=need_approval,
            is_agent=True,
        )(bound_request)

        return decorated_request
        
    def _create_response(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create the final response from the agent.
        
        Returns:
            Dict: The agent's response
        """
        return {
            "result": messages[-1]['content'],
            "messages": messages
        }    
    
    def _prepare_tools(self, uncategorized_tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prepare tools for execution.
        
        This method can be overridden by subclasses to customize tool preparation.
        """
        return [tool for tool in uncategorized_tool_calls]
            
    def _call_all_tools(self, approved_tool_calls: List[Dict[str, Any]], messages: List[Dict[str, Any]]):
        """
        Execute all approved tools.
        
        This method can be overridden by subclasses to customize tool execution.
        """
        for tool_call in approved_tool_calls:
            messages.append({"role": "tool", "tool_call_id": tool_call['id'], "content": self._call_tool(tool_call)})
    
        
    def _form_input(self, input: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Prepare the input for the agent.
        
        Args:
            input: The input data
            
        Returns:
            List[Dict[str, Any]]: The formatted input for the agent
        """
        if "prompt" not in input:
            raise ValueError("prompt key not found in input")
        
        return [{"role": "developer", "content": self.instruction}, 
                {"role": "user", "content": input['prompt']}]
        
    def _call_tool(self, tool_call: Dict[str, Any]) -> Any:
        """
        Execute a tool based on a tool call.
        
        Args:
            tool_call: The tool call dictionary
            
        Returns:
            Any: The result of the tool execution
            
        Raises:
            ValueError: If the tool is not found
        """
        function_params = tool_call['function']
        if self.tool_map.get(function_params['name']):
            func = self.tool_map[function_params['name']]
            if func._tool.is_agent:
                return func(json.loads(function_params['arguments']))['result']
            else:
                return func(**json.loads(function_params['arguments']))
            
        raise ValueError(f"Tool {function_params['name']} not found in the list of tools.")
    
    # Future Version: self, messages, modelConfig -> result, tool_calls
    def _call_model_and_check_status(self, messages: List[Dict[str, Any]], model: str = "gpt-4o-mini") -> Tuple[AgentExecutionStatus, List[Dict[str, Any]]]:
        """
        Call the language model and update the agent's status based on the response and a list of uncategorized tool call requests.
        
        This method can be overridden by subclasses to customize model interaction.
        """
        # Idealy, the model call configurations should be contained its own class
        try:
            chat_completion = self.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=[tool._tool.to_openai_function() for tool in self.tools],
                parallel_tool_calls=True
            )
        except Exception as e:
            raise RuntimeError(f"Messages: {json.dumps(messages, indent=2)}, Error: {str(e)}")
        
        messages.append(chat_completion.choices[0].message.model_dump())
        finish_reason = chat_completion.choices[0].finish_reason
        if finish_reason == "stop":
            return AgentExecutionStatus.COMPLETED, []
        elif finish_reason == "tool_calls":
            return AgentExecutionStatus.RUNNING, [tc.model_dump() for tc in chat_completion.choices[0].message.tool_calls]
        else: 
            return AgentExecutionStatus.ERROR, []
        
    def _check_tool_requires_approval(self, function_name: str) -> bool:
        """
        Check if a tool requires approval before execution.
        
        Args:
            function_name: The name of the tool to check
            
        Returns:
            bool: True if the tool requires approval, False otherwise
            
        Raises:
            ValueError: If the tool is not found
        """
        if not self.tools:
            raise ValueError("No tools have been provided to the agent.")
        
        if self.tool_map.get(function_name):
            return self.tool_map[function_name]._tool.need_approval
        
        raise ValueError(f"Tool {function_name} not found in the list of tools.")