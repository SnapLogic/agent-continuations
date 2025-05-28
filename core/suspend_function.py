import functools

class suspend_function:
    """
    A decorator class for storing state variables for boolean functions.
    The state variables are stored as attributes of the decorated function itself.
    """
    def __init__(self, **kwargs):
        """
        Initializes the decorator with the initial state variables.
        Example: @suspend_function(n=5)
        """
        self.initial_state = kwargs

    def __call__(self, func):
        """
        This method is called when the decorator is applied to a function.
        It returns a wrapper function that manages the state.
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # The original function `func` is expected to access and modify
            # the state variables directly as attributes of the `wrapper` function.
            # For example, if 'n' is a state variable, the function should use `wrapper.n`.
            # The user's example `n -= 1` would become `wrapper.n -= 1`.

            # Call the original function. The function's logic will use the state
            # attached to the wrapper.
            result = func(*args, **kwargs)
            return result

        # Attach the initial state variables as attributes to the wrapper function.
        # This makes them accessible and mutable by the decorated function.
        for key, value in self.initial_state.items():
            setattr(wrapper, key, value)

        return wrapper