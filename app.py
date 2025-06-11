from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.routing import Mount
from tools.milliman_tools import milliman_tool
from prompts.milliman_prompts import milliman_prompt

# Initialize MCP
mcp = FastMCP("Milliman MCP Server")
mcp.add_tool(milliman_tool)
mcp.add_prompt(milliman_prompt)

# FastAPI wrapper
app = FastAPI(title="Milliman API Gateway")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

# Mount MCP App
app.mount("/", mcp.app)
app.router.routes.append(Mount("/messages", app=SseServerTransport("/messages")))

# Optional: Add FastAPI endpoint to invoke the tool manually
from fastapi import Request, HTTPException

@app.post("/invoke")
async def invoke(request: Request):
    data = await request.json()
    input_data = data.get("input", {})
    try:
        result = await milliman_tool.invoke(input_data)
        return {"result": result.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
