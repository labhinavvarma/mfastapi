from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.routing import Mount
from mcp.server.sse import SseServerTransport
from milliman_mcp_server import mcp, HEALTH_STATE
from invoke_router import route as invoke_router

app = FastAPI(title="Milliman MCP + FastAPI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

@app.get("/healthz")
async def healthz():
    return {
        "server": "up",
        "token_api": HEALTH_STATE["token"],
        "mcid_api": HEALTH_STATE["mcid"],
        "medical_api": HEALTH_STATE["medical"]
    }

# Mount the tool invoke route
app.include_router(invoke_router, prefix="/tool")

# Mount MCP and SSE
app.mount("/", mcp.as_fastapi())
app.router.routes.append(Mount("/messages", app=SseServerTransport("/messages")))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
