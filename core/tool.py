from typing import List, Callable, Dict, Any, Optional, Union
from inspect import signature, getdoc, Parameter
from functools import wraps
import json

class Tool:
    def __init__(self, 
                 func: Callable, 
                 name: Optional[str] = None, 
                 description: Optional[str] = None,
                 need_approval: bool = False,
                 is_agent: bool = False):
        self.func = func
        self.name = name or func.__name__
        self.description = description or getdoc(func) or ""
        self.need_approval = need_approval
        self.is_agent = is_agent
        self.signature = signature(func)
        self.parameters = {
            "prompt": {"type": "string"}
        } if self.is_agent else {
            param_name: _annotation_to_json_schema_type(param.annotation)
            for param_name, param in self.signature.parameters.items()
            if param.annotation is not Parameter.empty
        }
        self.return_type = self.signature.return_annotation

    
    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)
    
    def __repr__(self):
        return f"Tool(name='{self.name}', parameters={self.parameters}, require_approval={self.need_approval}, is_agent={self.is_agent})"
    
    def to_openai_function(self) -> Dict[str, Any]:
        """Convert the Tool to a format suitable for OpenAI API."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        param_name: param_type
                        for param_name, param_type in self.parameters.items()
                    },
                    "required": list(self.parameters.keys())
                }
            }
        }
    
def _annotation_to_json_schema_type(annotation):
    """Convert Python type annotations to JSON Schema types."""
    # Basic type mappings
    type_mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        None: "null"
    }
    
    # Handle typing module types
    if hasattr(annotation, "__origin__"):
        origin = annotation.__origin__
        if origin is list or origin is set:
            # For List[int], etc.
            return {
                "type": "array",
                "items": _annotation_to_json_schema_type(annotation.__args__[0]) if hasattr(annotation, "__args__") else {}
            }
        elif origin is dict:
            # For Dict[str, int], etc.
            if hasattr(annotation, "__args__"):
                key_type, value_type = annotation.__args__
                if key_type is str:  # JSON only supports string keys
                    return {
                        "type": "object",
                        "additionalProperties": _annotation_to_json_schema_type(value_type)
                    }
            return {"type": "object"}
        elif origin is Union:
            # For Union[str, int], Optional[str], etc.
            types = [_annotation_to_json_schema_type(arg) for arg in annotation.__args__]
            return {"anyOf": types}
    
    # For basic types
    if annotation in type_mapping:
        return {"type": type_mapping[annotation]}
    
    # For class annotations (custom classes)
    if isinstance(annotation, type):
        return {"type": "object"}
    
    # Default fallback
    return {}

def tool(**kwargs):
    """Decorator to register a function as a tool/capability."""
    def decorator(func):
        # Create a Tool instance with the function and metadata
        tool_instance = Tool(func, **kwargs)
        
        # Preserve the tool instance on the function for later access
        func._tool = tool_instance
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return tool_instance(*args, **kwargs)
        
        # Attach the tool instance to the wrapper as well
        wrapper._tool = tool_instance
        
        return wrapper
    return decorator


# if __name__ == "__main__":
#     @tool()
#     def example_tool(x: int, y: int) -> int:
#         """Adds two numbers."""
#         return x + y
    
#     @tool()
#     def test() -> str:
#         """This is a test function."""
#         return "Test function"
    
    # print(example_tool._tool)  # Tool(name='example_tool', parameters={'x': <class 'int'>, 'y': <class 'int'>}, require_approval=False)
    # print(example_tool._tool.require_approval)  # False
    # print(example_tool._tool.description)  # Adds two numbers.
    # print(example_tool._tool.signature) 
    # print(test._tool.to_openai_function())  # <class 'str'>
    
