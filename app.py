from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.routing import Mount

from tools.milliman_tools import milliman_tool
from prompts.milliman_prompts import milliman_prompt

# FastMCP instance
mcp = FastMCP("Milliman MCP Server")
mcp.add_tool(milliman_tool)
mcp.add_prompt(milliman_prompt)

# Wrap in FastAPI
app = FastAPI(title="Milliman FastMCP API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# Mount MCP and SSE
app.mount("/", mcp.app)
app.router.routes.append(Mount("/messages", app=SseServerTransport("/messages")))

# FastAPI route to call tool directly
@app.post("/invoke")
async def invoke_tool(request: Request):
    try:
        payload = await request.json()
        tool_input = payload.get("input", {})
        result = await milliman_tool.invoke(tool_input)
        return {"result": result.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
