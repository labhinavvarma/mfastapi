from fastapi import APIRouter, Request, HTTPException
from milliman_mcp_server import mcp

route = APIRouter()

@route.post("/invoke")
async def invoke_tool(request: Request):
    payload = await request.json()
    tool_name = payload.get("tool")
    tool_input = payload.get("input", {})

    tool = next((t for t in mcp.tools if t.name == tool_name), None)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    result = await tool.invoke(tool_input)
    return {"type": result.type, "content": result.text or result.json()}
