#!/usr/bin/env python3
"""
MCP Client for Milliman Dashboard Tools Server
Connects to the FastMCP server via SSE transport
"""

import asyncio
import json
import os
import sys
from typing import Dict, Any, Optional
import httpx
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MillimanMCPClient:
    def __init__(self, server_url: str = "http://localhost:8000"):
        """
        Initialize the MCP client
        
        Args:
            server_url: URL of the MCP server (default: http://localhost:8000)
        """
        self.server_url = server_url.rstrip('/')
        self.session_id = None
        self.tools = {}
        
    async def connect(self) -> bool:
        """Connect to the MCP server and initialize session"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Initialize session with the server
                init_url = f"{self.server_url}/messages"
                
                # Send initialize request
                init_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "clientInfo": {
                            "name": "milliman-mcp-client",
                            "version": "1.0.0"
                        }
                    }
                }
                
                response = await client.post(init_url, json=init_request)
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"Connected to server: {result}")
                
                # Get available tools
                await self._list_tools()
                return True
                
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            return False
    
    async def _list_tools(self):
        """List available tools from the server"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                tools_request = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                    "params": {}
                }
                
                response = await client.post(f"{self.server_url}/messages", json=tools_request)
                response.raise_for_status()
                
                result = response.json()
                if "result" in result and "tools" in result["result"]:
                    self.tools = {tool["name"]: tool for tool in result["result"]["tools"]}
                    logger.info(f"Available tools: {list(self.tools.keys())}")
                else:
                    logger.warning("No tools found in server response")
                    
        except Exception as e:
            logger.error(f"Failed to list tools: {e}")
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Call a tool on the MCP server
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool (optional)
            
        Returns:
            Tool response as dictionary
        """
        if arguments is None:
            arguments = {}
            
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                tool_request = {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    }
                }
                
                # For FastMCP with SSE transport, we can also use direct HTTP POST
                direct_url = f"{self.server_url}/tool/{tool_name}"
                
                try:
                    # Try direct tool endpoint first (FastMCP specific)
                    if arguments:
                        response = await client.post(direct_url, json=arguments)
                    else:
                        response = await client.post(direct_url)
                    
                    response.raise_for_status()
                    return response.json()
                    
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        # Fallback to standard MCP protocol
                        logger.info("Direct endpoint not available, using MCP protocol...")
                        response = await client.post(f"{self.server_url}/messages", json=tool_request)
                        response.raise_for_status()
                        result = response.json()
                        
                        if "result" in result:
                            return result["result"]
                        elif "error" in result:
                            raise Exception(f"Tool error: {result['error']}")
                        else:
                            return result
                    else:
                        raise
                        
        except Exception as e:
            logger.error(f"Failed to call tool '{tool_name}': {e}")
            raise
    
    async def get_token(self) -> str:
        """Get OAuth2 access token"""
        result = await self.call_tool("get_token")
        return result
    
    async def mcid_search(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """Perform MCID external search"""
        result = await self.call_tool("mcid_search", {"request_body": request_body})
        return result
    
    async def submit_medical(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """Submit medical eligibility"""
        result = await self.call_tool("submit_medical", {"request_body": request_body})
        return result
    
    async def run_all(self) -> Dict[str, Any]:
        """Run all tools with default samples"""
        result = await self.call_tool("all")
        return result

async def main():
    """Main function to demonstrate the client"""
    # Get server URL from environment or use default
    server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
    
    client = MillimanMCPClient(server_url)
    
    try:
        # Connect to server
        logger.info(f"Connecting to MCP server at {server_url}...")
        if not await client.connect():
            logger.error("Failed to connect to server")
            return 1
        
        logger.info("Successfully connected to MCP server!")
        
        # Example usage - uncomment the operations you want to test
        
        # 1. Get OAuth token
        print("\n=== Getting OAuth Token ===")
        try:
            token = await client.get_token()
            print(f"Token: {token[:50]}..." if len(str(token)) > 50 else f"Token: {token}")
        except Exception as e:
            print(f"Error getting token: {e}")
        
        # 2. Run MCID search with sample data
        print("\n=== MCID Search ===")
        try:
            mcid_sample = {
                "requestID": "1",
                "processStatus": {"completed": "false", "isMemput": "false", "errorCode": None, "errorText": None},
                "consumer": [{
                    "firstName": "JUNEY",
                    "lastName": "TROR",
                    "middleName": None,
                    "sex": "F",
                    "dob": "19691109",
                    "addressList": [{"type": "P", "zip": None}],
                    "id": {"ssn": None}
                }],
                "searchSetting": {"minScore": "100", "maxResult": "1"}
            }
            
            mcid_result = await client.mcid_search(mcid_sample)
            print(f"MCID Result: {json.dumps(mcid_result, indent=2)}")
        except Exception as e:
            print(f"Error with MCID search: {e}")
        
        # 3. Submit medical eligibility
        print("\n=== Medical Submission ===")
        try:
            medical_sample = {
                "requestID": "77554079",
                "firstName": "JUNEY",
                "lastName": "TROR",
                "ssn": "148681406",
                "dateOfBirth": "1978-01-20",
                "gender": "F",
                "zipCodes": ["23060", "23229", "23242"],
                "callerId": "Milliman-Test16"
            }
            
            medical_result = await client.submit_medical(medical_sample)
            print(f"Medical Result: {json.dumps(medical_result, indent=2)}")
        except Exception as e:
            print(f"Error with medical submission: {e}")
        
        # 4. Run all tools at once
        print("\n=== Running All Tools ===")
        try:
            all_result = await client.run_all()
            print(f"All Tools Result: {json.dumps(all_result, indent=2)}")
        except Exception as e:
            print(f"Error running all tools: {e}")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Client interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
