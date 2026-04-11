# Yuki Plugin Guide

This guide explains how to extend Yuki by adding new plugins to the modular registry.

## Creating a Plugin

1.  **Create a file** in `backend/plugins/` (e.g., `my_special_tool.py`).
2.  **Define a subclass** of `Plugin` (or use the decorator system if applicable).
3.  **Specify the schema**: Include a JSON-serializable definition for the LLM to understand when to call the tool.
4.  **Implement `execute()`**: This method receives the arguments parsed from the LLM.

### Example: Simple Plugin

```python
from . import Plugin

class MyPlugin(Plugin):
    @property
    def schema(self):
        return {
            "name": "say_hello",
            "description": "Greeting the user",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}
                }
            }
        }

    def execute(self, name="User"):
        return f"Hello, {name}! I am Yuki."
```

## Registering the Plugin

The `backend/plugins/__init__.py` file handles auto-discovery. To ensure your plugin is recognized:

1.  Place the file inside the `backend/plugins/` directory.
2.  The `PluginRegistry` will scan the module at import time and collect all `Plugin` subclasses.
3.  No manual registration in `executor.py` is required.

## Standard Tools

*   **Computer Interaction**: Use `backend/plugins/computer_hands.py` for keyboard/mouse/media controls.
*   **Vision/Screenshots**: Use `backend/plugins/vision.py`.
*   **Information/Memory**: Use `backend/plugins/user_info.py`.

## Best Practices

*   **Error Handling**: Wrap platform-specific imports (like `pywinauto` or `pycaw`) in try-except blocks to ensure the backend starts even if a certain driver is missing.
*   **Response Format**: Always return a string or a JSON-serializable dictionary for the Brain to process.
*   **Async/Sync**: The plugin executor currently supports synchronous calls; use `asyncio.run()` if you must invoke async libraries like Playwright inside a plugin.
