# Keep Qoder behind the DSH LLM boundary

DSH owns the agent loop, workspace operations, tools, conversation history, cancellation, and permission surfaces. The plugin will therefore port only Qoder authentication and model transport behavior instead of embedding the official Qoder Agent SDK: although the SDK is supported by Qoder, its agent and tool responsibilities overlap DSH and would create nested execution with ambiguous ownership.
