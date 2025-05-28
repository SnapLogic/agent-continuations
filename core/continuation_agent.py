from core.agent import Agent, AgentExecutionStatus, TERMINAL_STATUSES
from typing import List, Dict, Any, Tuple, Callable
import json

class ContinuationAgent(Agent):
    def __init__(self, instruction: str, tools: List[Callable], suspension_list: List[Callable]=[]):
        super().__init__(instruction, tools)
        self.suspension_list = suspension_list
        
    def request(self, input: Dict[str, Any]) -> Dict[str, Any]:
        tool_statuses = {
            "_approved_tool_calls": [],
            "_uncategorized_tool_calls": [],
            "_unapproved_tool_calls": [],
            "_rejected_tool_calls": []
        }
        messages = self._form_input(input, tool_statuses)
        while True:
            # Check if any suspension conditions are met
            suspend_list = [suspend.__name__ for suspend in self.suspension_list if suspend()]
            if suspend_list:
                # If any suspension conditions are met, exit the agent
                break

            if not tool_statuses["_approved_tool_calls"] and not tool_statuses["_rejected_tool_calls"]:
                status, raw_tool_calls = self._call_model_and_check_status(messages)
                if status in TERMINAL_STATUSES:
                    break
                self._prepare_tools(raw_tool_calls, tool_statuses)
            self._call_all_tools(tool_statuses, messages)
            
            if tool_statuses["_unapproved_tool_calls"] or tool_statuses["_rejected_tool_calls"]:
                break
            
        return self._create_response(messages, tool_statuses, suspend_list)
    
    def _create_response(self, messages: List[Dict[str, Any]], tool_statuses: Dict[str, Any], suspend_list: List[str]) -> Dict[str, Any]:
        if suspend_list:
            return {
                "continuation": {
                    "messages": messages
                },
                "suspend_list": suspend_list,
                "end_reason": "suspended"
            }
        if tool_statuses["_unapproved_tool_calls"]:
            continuation = {
                "messages": messages,
                "resume_request": tool_statuses["_unapproved_tool_calls"],
                "processed": [{"id": tc['id'], "approved": False} for tc in tool_statuses["_unapproved_tool_calls"]]
            }
            return {
                "continuation": continuation,
                "approval_info": ContinuationAgent.__flatten_continuation_obj(continuation),
                "end_reason": "approval_required"
            }
            
        elif tool_statuses["_rejected_tool_calls"]:
            return {
                "messages": messages,
                "rejected_tool_calls": tool_statuses["_rejected_tool_calls"],
                "end_reason": "rejected_tool_calls"
            }
        else:
            return {
                "result": messages[-1]['content'],
                "messages": messages,
                "end_reason": "completed"
            }
    
    def _prepare_tools(self, uncategorized_tool_calls: List[Dict[str, Any]], tool_statuses: Dict[str, Any]):
        # Filter out tools that require approval
        tool_statuses["_approved_tool_calls"] = [tool for tool in uncategorized_tool_calls if not self._check_tool_requires_approval(tool['function']['name'])]
        tool_statuses["_unapproved_tool_calls"] = [tool for tool in uncategorized_tool_calls if self._check_tool_requires_approval(tool['function']['name'])]
        tool_statuses["_uncategorized_tool_calls"] = []
    
    def _call_all_tools(self, tool_statuses, messages):
        for tool_call in tool_statuses["_approved_tool_calls"]:
            result, is_agent = self._call_tool(tool_call)
            # If tool call is not from an agent, append the result to messages
            if not is_agent:
                messages.append({"role": "tool", "tool_call_id": tool_call['id'], "content": result})
            # If the tool call contains continuation
            elif result.get('continuation'):
                tool_call['continuation'] = result['continuation']
                tool_statuses["_unapproved_tool_calls"].append(tool_call)
            # If the tool call is rejected, append it to rejected_tool_calls
            elif result.get('rejected_tool_calls'):
                tool_statuses["_rejected_tool_calls"].append(tool_call)
            # If the tool call does not contain continuation, append the result to messages
            else: 
                messages.append({"role": "tool", "tool_call_id": tool_call['id'], "content": result['result']})
        tool_statuses["_approved_tool_calls"] = []
            
    def _call_tool(self, tool_call: Dict[str, Any]) -> Tuple[Any, bool]:
        function_params = tool_call['function']
        if self.tool_map.get(function_params['name']):
            func = self.tool_map[function_params['name']]
            if func._tool.is_agent:
                if "continuation" in tool_call:
                    return func(tool_call), True
                return func(json.loads(function_params['arguments'])), True
            else:
                return func(**json.loads(function_params['arguments'])), False
        raise ValueError(f"Tool {function_params['name']} not found in the list of tools.")
    
    def _form_input(self, input, tools_statuses: Dict[str, Any]):
        messages = []
        if "continuation" in input:
            messages = input["continuation"]["messages"]
            approval_info = input.get("approval_info", [])
            continuation = input["continuation"]
            continuation = ContinuationAgent.__reconstruct_continuation_obj(approval_info, continuation)
            ContinuationAgent.__prepare_tools_from_resume_request(continuation.get('resume_request', []), continuation.get("processed", []), tools_statuses)
                
        else:
            messages = super()._form_input(input)   
        return messages
    
    @staticmethod
    def __flatten_helper(continuation_obj: Dict[str, Any], current_path: List[str], current_id_path: List[str], flattened_list: List[Dict[str, Any]]):
        if not continuation_obj.get("resume_request") and continuation_obj.get("messages"):
            flattened_list.append({
                "paths": list(current_path),
                "path_ids": list(current_id_path),
                "approved": True,
            })
            return
        if not continuation_obj.get("resume_request"):
            return
        for req in continuation_obj["resume_request"]:
            current_path.append(req["function"]["name"])
            current_id_path.append(req["id"])
            if req.get("continuation"):
                ContinuationAgent.__flatten_helper(req["continuation"], current_path, current_id_path, flattened_list)
            else:
                flattened_list.append({
                    "paths": list(current_path),
                    "path_ids": list(current_id_path),
                    "tool_call": req,
                    "approved": False
                })
            current_path.pop()
            current_id_path.pop()
    
    @staticmethod
    def __flatten_continuation_obj(continuation_obj: Dict[str, Any]) -> List[Dict[str, Any]]:
        flattened_result = []
        ContinuationAgent.__flatten_helper(continuation_obj, [], [], flattened_result)
        return flattened_result
    
    @staticmethod
    def __prepare_tools_from_resume_request(resume_requests: List[Dict[str, Any]], processed_list: List[Dict[str, Any]], tool_statuses: Dict[str, Any]):
        approved_list = set(item['id'] for item in processed_list if item.get("approved"))
        tool_statuses['_approved_tool_calls'] = [req for req in resume_requests if req['id'] in approved_list]
        rejected_list = set(item['id'] for item in processed_list if not item.get("approved"))
        tool_statuses['_rejected_tool_calls'] = [req for req in resume_requests if req['id'] in rejected_list]
        if len(tool_statuses['_approved_tool_calls']) + len(tool_statuses['_rejected_tool_calls']) != len(resume_requests):
            raise ValueError("Some requests are neither approved nor rejected")
    
    @staticmethod
    def __reconstruct_continuation_obj(approval_info: List[Dict[str, Any]], continuation: Dict[str, Any]) -> Dict[str, Any]:
        if not approval_info:
            return continuation
        for item in approval_info:
            ContinuationAgent.__reconstruct_helper(item, continuation)
        return continuation    
            
    @staticmethod
    def __reconstruct_helper(approval_obj: Dict[str, Any], continuation: Dict[str, Any]) -> Dict[str, Any]:
       path_ids = approval_obj["path_ids"]
       ContinuationAgent.__reconstruct_nested_helper(0, approval_obj, path_ids, continuation) 
        
    @staticmethod
    def __reconstruct_nested_helper(index: int, approval_obj: Dict[str, Any], path_ids: List[str], continuation: Dict[str, Any]):
        processed_list = continuation.get("processed", [])
        if not processed_list:
            processed_list.append(
                {
                    "id": path_ids[index],
                    "approved": True if index == len(path_ids) - 1 else approval_obj["approved"]
                }
            )
        else:
            for item in processed_list:
                if item["id"] == path_ids[index]:
                    item["approved"] = True if index == len(path_ids) - 1 else approval_obj["approved"]
                    break
        continuation["processed"] = processed_list
        if (index == len(path_ids) - 1):
            return
        if not continuation.get("resume_request") :
            raise ValueError("Number of path IDs is greater than nested levels")
        
        for req in continuation["resume_request"]:
            if req["id"] == path_ids[index]:
                ContinuationAgent.__reconstruct_nested_helper(index + 1, approval_obj, path_ids, req["continuation"])
    