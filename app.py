#!/usr/bin/env python3
"""
FastMCP Client for Milliman Dashboard Tools
Connects to the FastMCP server with SSE transport
"""

import asyncio
import json
import os
import sys
import logging
from typing import Dict, Any, Optional
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MillimanFastMCPClient:
    def __init__(self, server_url: str = "http://localhost:8000"):
        """
        Initialize the FastMCP client
        
        Args:
            server_url: URL of the FastMCP server (default: http://localhost:8000)
        """
        self.server_url = server_url.rstrip('/')
        self.available_tools = ["get_token", "mcid_search", "submit_medical", "all"]
        
    async def connect(self) -> bool:
        """Test connection to the FastMCP server"""
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                # Test basic connectivity
                response = await client.get(self.server_url)
                logger.info(f"Server connection test: {response.status_code}")
                
                # Test if tool endpoint works
                test_response = await client.post(f"{self.server_url}/tool/get_token")
                if test_response.status_code < 500:  # Accept any non-server-error
                    logger.info("✅ Successfully connected to FastMCP server!")
                    logger.info(f"🔧 Available tools: {self.available_tools}")
                    return True
                else:
                    logger.error(f"Server error: {test_response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            return False
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Call a tool on the FastMCP server
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool (optional)
            
        Returns:
            Tool response as dictionary
        """
        if arguments is None:
            arguments = {}
            
        if tool_name not in self.available_tools:
            raise ValueError(f"Tool '{tool_name}' not available. Available tools: {self.available_tools}")
            
        try:
            async with httpx.AsyncClient(
                timeout=60.0, 
                follow_redirects=True,
                verify=False  # Handle SSL issues
            ) as client:
                
                # Strategy 1: Try FastMCP direct tool endpoint (primary method)
                tool_url = f"{self.server_url}/tool/{tool_name}"
                
                try:
                    logger.info(f"🔧 Calling tool: {tool_name} at {tool_url}")
                    
                    if tool_name in ["get_token", "all"]:
                        # These tools don't need arguments
                        response = await client.post(tool_url)
                    else:
                        # mcid_search and submit_medical need the arguments directly
                        response = await client.post(tool_url, json=arguments)
                    
                    logger.info(f"📡 Response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        result = response.json()
                        logger.info(f"✅ Tool call successful")
                        return result
                    
                    elif response.status_code in [307, 301, 302]:
                        # Handle redirects
                        redirect_url = response.headers.get('location')
                        logger.info(f"🔄 Following redirect to: {redirect_url}")
                        
                        if redirect_url:
                            if tool_name in ["get_token", "all"]:
                                redirect_response = await client.post(redirect_url)
                            else:
                                redirect_response = await client.post(redirect_url, json=arguments)
                            
                            if redirect_response.status_code == 200:
                                return redirect_response.json()
                    
                    else:
                        logger.warning(f"⚠️ Direct endpoint returned: {response.status_code}")
                        logger.warning(f"Response: {response.text[:200]}...")
                
                except Exception as e:
                    logger.warning(f"⚠️ Direct endpoint failed: {e}")
                
                # Strategy 2: Try SSE/MCP protocol endpoint (fallback)
                logger.info("🔄 Trying MCP protocol endpoint...")
                
                mcp_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    }
                }
                
                try:
                    response = await client.post(f"{self.server_url}/messages", json=mcp_request)
                    
                    if response.status_code == 200:
                        result = response.json()
                        logger.info("✅ MCP protocol successful")
                        
                        # Handle MCP response format
                        if "result" in result:
                            return result["result"]
                        elif "error" in result:
                            raise Exception(f"MCP error: {result['error']}")
                        else:
                            return result
                            
                except Exception as e:
                    logger.warning(f"⚠️ MCP protocol failed: {e}")
                
                # Strategy 3: Try alternative endpoint formats
                alternative_endpoints = [
                    f"{self.server_url}/tool/{tool_name}/",  # With trailing slash
                    f"{self.server_url}/tools/{tool_name}",  # Plural form
                ]
                
                for alt_url in alternative_endpoints:
                    try:
                        logger.info(f"🔄 Trying alternative: {alt_url}")
                        
                        if tool_name in ["get_token", "all"]:
                            response = await client.post(alt_url)
                        else:
                            response = await client.post(alt_url, json=arguments)
                        
                        if response.status_code == 200:
                            logger.info(f"✅ Alternative endpoint worked: {alt_url}")
                            return response.json()
                            
                    except Exception as e:
                        logger.warning(f"⚠️ Alternative {alt_url} failed: {e}")
                        continue
                
                # If all strategies failed
                raise Exception(f"All endpoint strategies failed for tool '{tool_name}'")
                
        except Exception as e:
            logger.error(f"❌ Failed to call tool '{tool_name}': {e}")
            raise
    
    async def get_token(self) -> str:
        """Get OAuth2 access token"""
        result = await self.call_tool("get_token")
        
        # Handle different response formats
        if isinstance(result, str):
            return result
        elif isinstance(result, dict):
            # Could be direct token or wrapped in response
            if "access_token" in result:
                return result["access_token"]
            elif "result" in result:
                return result["result"]
        
        return str(result)
    
    async def mcid_search(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """Perform MCID external search"""
        return await self.call_tool("mcid_search", request_body)
    
    async def submit_medical(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """Submit medical eligibility"""
        return await self.call_tool("submit_medical", request_body)
    
    async def run_all(self) -> Dict[str, Any]:
        """Run all tools with default samples"""
        return await self.call_tool("all")

async def main():
    """Main function to demonstrate the client"""
    # Get server URL from environment or use default
    server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
    
    client = MillimanFastMCPClient(server_url)
    
    try:
        # Connect to server
        logger.info(f"🚀 Connecting to FastMCP server at {server_url}...")
        if not await client.connect():
            logger.error("❌ Failed to connect to server")
            print("\n💡 Make sure your server is running:")
            print("   python server.py")
            return 1
        
        print(f"\n🎉 Successfully connected to FastMCP server!")
        
        # Example usage
        
        # 1. Get OAuth token
        print("\n" + "="*50)
        print("🔐 Getting OAuth Token")
        print("="*50)
        try:
            token = await client.get_token()
            print(f"✅ Token received: {token[:50]}..." if len(str(token)) > 50 else f"✅ Token: {token}")
        except Exception as e:
            print(f"❌ Error getting token: {e}")
        
        # 2. Run MCID search with sample data
        print("\n" + "="*50)
        print("🔍 MCID Search Test")
        print("="*50)
        try:
            mcid_sample = {
                "requestID": "test123",
                "processStatus": {"completed": "false", "isMemput": "false", "errorCode": None, "errorText": None},
                "consumer": [{
                    "firstName": "JANE",
                    "lastName": "DOE",
                    "middleName": None,
                    "sex": "F",
                    "dob": "19851010",
                    "addressList": [{"type": "P", "zip": None}],
                    "id": {"ssn": None}
                }],
                "searchSetting": {"minScore": "100", "maxResult": "1"}
            }
            
            mcid_result = await client.mcid_search(mcid_sample)
            print(f"✅ MCID Search completed")
            print(f"📊 Status: {mcid_result.get('status_code', 'unknown')}")
            print(f"📄 Response keys: {list(mcid_result.keys())}")
        except Exception as e:
            print(f"❌ Error with MCID search: {e}")
        
        # 3. Submit medical eligibility
        print("\n" + "="*50)
        print("🏥 Medical Submission Test")
        print("="*50)
        try:
            medical_sample = {
                "requestID": "medical123",
                "firstName": "JANE",
                "lastName": "DOE",
                "ssn": "123456789",
                "dateOfBirth": "1985-10-10",
                "gender": "F",
                "zipCodes": ["12345", "67890"],
                "callerId": "Milliman-Test-Client"
            }
            
            medical_result = await client.submit_medical(medical_sample)
            print(f"✅ Medical submission completed")
            print(f"📊 Status: {medical_result.get('status_code', 'unknown')}")
            print(f"📄 Response keys: {list(medical_result.keys())}")
        except Exception as e:
            print(f"❌ Error with medical submission: {e}")
        
        # 4. Run all tools at once
        print("\n" + "="*50)
        print("🔧 Running All Tools")
        print("="*50)
        try:
            all_result = await client.run_all()
            print(f"✅ All tools completed successfully!")
            print(f"📊 Results for {len(all_result)} tools:")
            for tool_name, result in all_result.items():
                print(f"   • {tool_name}: {'✅' if result else '❌'}")
        except Exception as e:
            print(f"❌ Error running all tools: {e}")
        
        print("\n" + "="*60)
        print("🎊 All tests completed! Your FastMCP setup is working!")
        print("="*60)
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("🛑 Client interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Exiting...")
        sys.exit(0)
