from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.routing import Mount
from mcp.server.sse import SseServerTransport

from milliman_mcp_server import mcp_app, HEALTH_STATE
from invoke_router import route as invoke_router

app = FastAPI(title="Milliman MCP + FastAPI Server")

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Health check endpoint
@app.get("/healthz")
async def healthz():
    return {
        "server": "up",
        "token_api": HEALTH_STATE["token"],
        "mcid_api": HEALTH_STATE["mcid"],
        "medical_api": HEALTH_STATE["medical"]
    }

# Tool invocation route
app.include_router(invoke_router, prefix="/tool")

# Mount MCP app and SSE
app.mount("/", mcp_app)
app.router.routes.append(Mount("/messages", app=SseServerTransport("/messages")))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
