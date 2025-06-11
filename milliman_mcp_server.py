
# milliman_mcp_server.py
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.fastmcp.prompts.base import Message
import mcp.types as types

from typing import Dict, List
import httpx
import logging

# Initialize MCP and internal FastAPI app
mcp = FastMCP(name="Milliman MCP Server")
mcp_app = mcp._mcp_server  # Use the internal FastAPI app

# Logging setup
logger = logging.getLogger("milliman")
logging.basicConfig(level=logging.INFO)

# Constants
TOKEN_URL = "https://securefed.antheminc.com/as/token.oauth2"
MCID_URL = "https://mcid-app-prod.anthem.com:443/MCIDExternalService/V2/extSearchService/json"
MEDICAL_URL = "https://hix-clm-internaltesting-prod.anthem.com/medical"
CLIENT_ID = "MILLIMAN"
CLIENT_SECRET = "qCZpW9ixf7KTQh5Ws5YmUUqcO6JRfz0GsITmFS87RHLOls8fh0pv8TcyVEVmWRQa"

# Health state tracker
HEALTH_STATE = {"token": False, "mcid": False, "medical": False}

# FastAPI startup event for health checks
@mcp_app.on_event("startup")
async def check_api_connectivity():
    logger.info("🔍 Checking external API connectivity...")
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            token_resp = await client.post(
                TOKEN_URL,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            HEALTH_STATE["token"] = token_resp.status_code == 200

            mcid_resp = await client.post(MCID_URL, headers={'Apiuser': 'MillimanUser'}, json={})
            HEALTH_STATE["mcid"] = mcid_resp.status_code in [200, 400]

            medical_resp = await client.post(MEDICAL_URL, headers={'Authorization': 'dummy'}, json={})
            HEALTH_STATE["medical"] = medical_resp.status_code in [200, 400]

        except Exception as e:
            logger.error(f"❌ Startup check failed: {e}")

# Tool: Fetch token
@mcp.tool(name="get_token", description="Fetch OAuth2 token from Anthem")
async def get_token(_: dict, ctx: Context) -> types.ToolOutput:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(TOKEN_URL, data={
                'grant_type': 'client_credentials',
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET
            }, headers={'Content-Type': 'application/x-www-form-urlencoded'})
            return types.ToolOutput.json(resp.json())
        except Exception as e:
            return types.ToolOutput.text(str(e))

# Tool: Submit MCID + Medical
@mcp.tool(name="submit_requests", description="Submit MCID + Medical payloads")
async def submit_requests(data: Dict, ctx: Context) -> types.ToolOutput:
    try:
        mcid_payload = data.get("mcid_payload", {})
        medical_payload = data.get("medical_payload", {})

        async with httpx.AsyncClient() as client:
            token_resp = await client.post(TOKEN_URL, data={
                'grant_type': 'client_credentials',
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET
            }, headers={'Content-Type': 'application/x-www-form-urlencoded'})
            token = token_resp.json().get("access_token")

            if not token:
                return types.ToolOutput.text("❌ Failed to get token")

            mcid_resp = await client.post(MCID_URL, headers={'Apiuser': 'MillimanUser'}, json=mcid_payload)
            medical_resp = await client.post(MEDICAL_URL, headers={
                'Authorization': f'{token}',
                'Content-Type': 'application/json'
            }, json=medical_payload)

            return types.ToolOutput.json({
                "mcid_response": mcid_resp.json(),
                "medical_response": medical_resp.json()
            })
    except Exception as e:
        return types.ToolOutput.text(str(e))

# Prompt: Milliman submission
@mcp.prompt(
    name="milliman-full-prompt",
    description="Prompt to run full MCID and Medical claim submission"
)
async def milliman_prompt(query: str, ctx: Context) -> List[Message]:
    return [{"role": "user", "content": f"Run Milliman submission:\n{query}"}]

# Export these for use in app.py
__all__ = ["mcp", "mcp_app", "HEALTH_STATE"]
