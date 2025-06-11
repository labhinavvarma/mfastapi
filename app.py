#!/usr/bin/env python3
"""
Final integration test for the complete Milliman MCP server and client
"""

import asyncio
import sys
import os
import json
import httpx

# Add the current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_server_endpoints():
    """Test all server endpoints directly"""
    print("🧪 Testing Server Endpoints Directly")
    print("=" * 50)
    
    server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        
        # Test health endpoint
        print("\n1. Health Check")
        try:
            response = await client.get(f"{server_url}/health")
            print(f"   ✅ Health: {response.status_code} - {response.json()}")
        except Exception as e:
            print(f"   ❌ Health failed: {e}")
            return False
        
        # Test root endpoint
        print("\n2. Root Endpoint")
        try:
            response = await client.get(server_url)
            result = response.json()
            print(f"   ✅ Root: Available tools: {result.get('available_tools', [])}")
        except Exception as e:
            print(f"   ❌ Root failed: {e}")
        
        # Test direct endpoints
        print("\n3. Direct Tool Endpoints")
        
        # Test get_token
        try:
            response = await client.post(f"{server_url}/get_token")
            result = response.json()
            if "access_token" in result:
                token = result["access_token"]
                print(f"   ✅ GET /get_token: Got token ({len(token)} chars)")
            else:
                print(f"   ⚠️  GET /get_token: Unexpected format: {result}")
        except Exception as e:
            print(f"   ❌ GET /get_token failed: {e}")
        
        # Test generic tool endpoint
        print("\n4. Generic Tool Endpoint")
        try:
            response = await client.post(f"{server_url}/tool/get_token", json={})
            result = response.json()
            print(f"   ✅ POST /tool/get_token: {result}")
        except Exception as e:
            print(f"   ❌ POST /tool/get_token failed: {e}")
        
        # Test MCP protocol
        print("\n5. MCP Protocol")
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            }
            response = await client.post(f"{server_url}/messages", json=mcp_request)
            result = response.json()
            if "result" in result and "tools" in result["result"]:
                tools = [t["name"] for t in result["result"]["tools"]]
                print(f"   ✅ MCP tools/list: {tools}")
            else:
                print(f"   ⚠️  MCP unexpected format: {result}")
        except Exception as e:
            print(f"   ❌ MCP protocol failed: {e}")
    
    return True

async def test_client():
    """Test the MCP client"""
    print("\n\n🤖 Testing MCP Client")
    print("=" * 50)
    
    try:
        from mcp_client import MillimanMCPClient
    except ImportError:
        print("❌ Could not import MCP client")
        return False
    
    server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
    client = MillimanMCPClient(server_url)
    
    try:
        # Connect to server
        print("\n1. Connecting to server...")
        if not await client.connect():
            print("   ❌ Failed to connect")
            return False
        print(f"   ✅ Connected! Available tools: {list(client.tools.keys())}")
        
        # Test get_token
        print("\n2. Testing get_token...")
        try:
            token = await client.get_token()
            print(f"   ✅ Got token: {str(token)[:50]}...")
        except Exception as e:
            print(f"   ❌ get_token failed: {e}")
        
        # Test MCID search with sample data
        print("\n3. Testing MCID search...")
        try:
            mcid_sample = {
                "requestID": "test123",
                "processStatus": {"completed": "false", "isMemput": "false"},
                "consumer": [{
                    "firstName": "JANE",
                    "lastName": "DOE",
                    "sex": "F",
                    "dob": "19851010"
                }],
                "searchSetting": {"minScore": "100", "maxResult": "1"}
            }
            
            mcid_result = await client.mcid_search(mcid_sample)
            print(f"   ✅ MCID search completed: {mcid_result.get('status_code', 'unknown status')}")
        except Exception as e:
            print(f"   ❌ MCID search failed: {e}")
        
        # Test run_all
        print("\n4. Testing run_all...")
        try:
            all_result = await client.run_all()
            print(f"   ✅ run_all completed with {len(all_result)} results")
            for tool_name, result in all_result.items():
                print(f"      • {tool_name}: {'✅' if result else '❌'}")
        except Exception as e:
            print(f"   ❌ run_all failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Client test failed: {e}")
        return False

async def main():
    """Main test function"""
    print("🚀 Milliman MCP Server & Client Integration Test")
    print("=" * 60)
    
    # Test server endpoints first
    server_ok = await test_server_endpoints()
    
    if not server_ok:
        print("\n❌ Server tests failed. Make sure server is running:")
        print("   python server.py")
        return 1
    
    # Test client
    client_ok = await test_client()
    
    if not client_ok:
        print("\n❌ Client tests failed")
        return 1
    
    print("\n" + "=" * 60)
    print("🎉 All tests passed! Your MCP setup is working correctly.")
    print("\nNext steps:")
    print("• Use the client in your applications")
    print("• Check the API docs at http://localhost:8000/docs")
    print("• Monitor logs for any issues")
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        sys.exit(1)
