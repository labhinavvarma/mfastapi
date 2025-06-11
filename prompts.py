from typing import List
from mcp.server.fastmcp import prompt
from mcp.server.fastmcp.prompts.base import Message

@prompt(
    name="milliman-prompt",
    description="Prompt to initiate Anthem API flow via milliman-api-tool"
)
async def milliman_prompt(query: str) -> List[Message]:
    return [
        Message(role="user", content=(
            f"Use the `milliman-api-tool` to retrieve identity, token, and claims data for the patient. Query: {query}"
        ))
    ]
