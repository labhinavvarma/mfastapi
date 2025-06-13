#!/usr/bin/env python3
"""
Streamlined Milliman Hybrid FastMCP Server
4 Core Functions: search_mcid, submit_medical, get_auth_token, test_connection
Both MCP protocol (stdin/stdout) and HTTP server (port 8000)
"""

import httpx
import requests
import json
import asyncio
import time
import threading
import uvicorn
from typing import List, Dict, Any
from pydantic import BaseModel, validator
from fastmcp import FastMCP
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# --- Pydantic Models ---
class PersonRequest(BaseModel):
    firstName: str
    lastName: str
    ssn: str
    dateOfBirth: str  # Format: YYYY-MM-DD
    gender: str  # M or F
    zipCodes: List[str]
    
    class Config:
        extra = "ignore"
        str_strip_whitespace = True
    
    @validator('gender')
    def validate_gender(cls, v):
        return v.upper()
    
    @validator('zipCodes')
    def validate_zip_codes(cls, v):
        if not v or len(v) == 0:
            return ["00000"]
        return [str(zip_code) for zip_code in v]

# --- Configuration ---
TOKEN_URL = "https://securefed.antheminc.com/as/token.oauth2"
TOKEN_PAYLOAD = {
    'grant_type': 'client_credentials',
    'client_id': 'MILLIMAN',
    'client_secret': 'qCZpW9ixf7KTQh5Ws5YmUUqcO6JRfz0GsITmFS87RHLOls8fh0pv8TcyVEVmWRQa'
}
TOKEN_HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}

# --- Helper Functions ---
def generate_request_id():
    """Generate a unique request ID"""
    return str(int(time.time() * 1000))

def get_access_token_sync():
    """Get access token synchronously"""
    try:
        response = requests.post(TOKEN_URL, data=TOKEN_PAYLOAD, headers=TOKEN_HEADERS)
        response.raise_for_status()
        return response.json().get("access_token")
    except Exception:
        return None

def transform_to_mcid_format(person_data: PersonRequest):
    """Transform person data to MCID API format"""
    dob_formatted = person_data.dateOfBirth.replace("-", "")
    
    return {
        "requestID": generate_request_id(),
        "processStatus": {
            "completed": "false",
            "isMemput": "false",
            "errorCode": None,
            "errorText": None
        },
        "consumer": [
            {
                "firstName": person_data.firstName,
                "lastName": person_data.lastName,
                "middleName": None,
                "sex": person_data.gender,
                "dob": dob_formatted,
                "addressList": [
                    {
                        "type": "P",
                        "zip": person_data.zipCodes[0] if person_data.zipCodes else None
                    }
                ],
                "id": {
                    "ssn": person_data.ssn
                }
            }
        ],
        "searchSetting": {
            "minScore": "100",
            "maxResult": "1"
        }
    }

def transform_to_medical_format(person_data: PersonRequest):
    """Transform person data to Medical API format"""
    return {
        "requestID": generate_request_id(),
        "firstName": person_data.firstName,
        "lastName": person_data.lastName,
        "ssn": person_data.ssn,
        "dateOfBirth": person_data.dateOfBirth,
        "gender": person_data.gender,
        "zipCodes": person_data.zipCodes,
        "callerId": "Milliman-Test16",
        "middleName": "",
        "addressLine1": "",
        "addressLine2": "",
        "city": "",
        "state": "",
        "country": "US",
        "phoneNumber": "",
        "email": ""
    }

# --- Core API Functions ---
async def async_get_token():
    """Get authentication token"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(TOKEN_URL, data=TOKEN_PAYLOAD, headers=TOKEN_HEADERS)
            try:
                response_body = response.json() if response.content else {}
            except:
                response_body = response.text if response.content else "No content"
            return {
                'success': response.status_code == 200,
                'status_code': response.status_code, 
                'data': response_body
            }
        except Exception as e:
            return {
                'success': False,
                'status_code': 500, 
                'error': str(e)
            }

async def async_mcid_search(person_data: PersonRequest):
    """Search MCID database"""
    url = "https://mcid-app-prod.anthem.com:443/MCIDExternalService/V2/extSearchService/json"
    headers = {
        'Content-Type': 'application/json',
        'Apiuser': 'MillimanUser'
    }
    
    mcid_payload = transform_to_mcid_format(person_data)
    
    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.post(url, headers=headers, json=mcid_payload, timeout=30)
            
            try:
                if response.content:
                    response_body = response.json()
                else:
                    response_body = "No content"
            except json.JSONDecodeError:
                response_body = response.text
            except Exception:
                response_body = "Unable to parse response"
            
            return {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'data': response_body,
                'request_id': mcid_payload.get('requestID')
            }
        except Exception as e:
            return {
                'success': False,
                'status_code': 500,
                'error': str(e),
                'request_id': mcid_payload.get('requestID')
            }

async def async_submit_medical_request(person_data: PersonRequest):
    """Submit medical information request with enhanced authorization"""
    access_token = await asyncio.to_thread(get_access_token_sync)
    if not access_token:
        return {
            'success': False,
            'status_code': 500,
            'error': 'Access token not found'
        }
    
    medical_url = 'https://hix-clm-internaltesting-prod.anthem.com/medical'
    medical_payload = transform_to_medical_format(person_data)
    
    # Try multiple authorization formats
    auth_attempts = [
        {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-API-Version': '1.0',
            'User-Agent': 'Milliman-Client/1.0'
        },
        {
            'Authorization': f'{access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        },
        {
            'Authorization': f'Token {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    ]
    
    for i, headers in enumerate(auth_attempts):
        try:
            response = requests.post(medical_url, headers=headers, json=medical_payload, timeout=30)
            
            try:
                if response.content:
                    response_body = response.json()
                else:
                    response_body = "No content"
            except json.JSONDecodeError:
                response_body = response.text
            except Exception:
                response_body = "Unable to parse response"
            
            result = {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'data': response_body,
                'request_id': medical_payload.get('requestID'),
                'auth_attempt': i + 1
            }
            
            # Return first successful result or last attempt
            if response.status_code == 200 or i == len(auth_attempts) - 1:
                return result
                
        except Exception as e:
            if i == len(auth_attempts) - 1:
                return {
                    'success': False,
                    'status_code': 500,
                    'error': str(e),
                    'request_id': medical_payload.get('requestID')
                }
            continue

# --- Initialize Servers ---
mcp = FastMCP("Milliman MCP Server")

app = FastAPI(
    title="Streamlined Milliman MCP Server",
    description="4 Core Functions: search_mcid, submit_medical, get_auth_token, test_connection",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MCP Tools ---

@mcp.tool()
async def search_mcid(
    firstName: str,
    lastName: str,  
    ssn: str,
    dateOfBirth: str,
    gender: str,
    zipCodes: List[str]
) -> Dict[str, Any]:
    """
    Search the MCID (Member Consumer ID) database for a person.
    
    Args:
        firstName: Person's first name
        lastName: Person's last name  
        ssn: Social Security Number
        dateOfBirth: Date in YYYY-MM-DD format
        gender: "M" or "F"
        zipCodes: Array of zip code strings
        
    Returns:
        MCID search results including status and member information
    """
    try:
        person_data = PersonRequest(
            firstName=firstName,
            lastName=lastName,
            ssn=ssn,
            dateOfBirth=dateOfBirth,
            gender=gender,
            zipCodes=zipCodes
        )
        result = await async_mcid_search(person_data)
        return result
    except Exception as e:
        return {
            'success': False,
            'status_code': 500,
            'error': str(e)
        }

@mcp.tool()
async def submit_medical(
    firstName: str,
    lastName: str,
    ssn: str,
    dateOfBirth: str,
    gender: str,
    zipCodes: List[str]
) -> Dict[str, Any]:
    """
    Submit a medical information request for a person.
    
    Args:
        firstName: Person's first name
        lastName: Person's last name
        ssn: Social Security Number  
        dateOfBirth: Date in YYYY-MM-DD format
        gender: "M" or "F"
        zipCodes: Array of zip code strings
        
    Returns:
        Medical submission results including status and response data
    """
    try:
        person_data = PersonRequest(
            firstName=firstName,
            lastName=lastName,
            ssn=ssn,
            dateOfBirth=dateOfBirth,
            gender=gender,
            zipCodes=zipCodes
        )
        result = await async_submit_medical_request(person_data)
        return result
    except Exception as e:
        return {
            'success': False,
            'status_code': 500,
            'error': str(e)
        }

@mcp.tool()
async def get_auth_token() -> Dict[str, Any]:
    """
    Get an authentication token for Milliman services.
    
    Returns:
        Token information and status
    """
    try:
        result = await async_get_token()
        return result
    except Exception as e:
        return {
            'success': False,
            'status_code': 500,
            'error': str(e)
        }

@mcp.tool()
async def test_connection(
    firstName: str,
    lastName: str,
    ssn: str,
    dateOfBirth: str,
    gender: str,
    zipCodes: List[str]
) -> Dict[str, Any]:
    """
    Test connectivity to Milliman APIs.
    
    Args:
        firstName: Person's first name (used for test requests)
        lastName: Person's last name (used for test requests)
        ssn: Social Security Number (used for test requests)
        dateOfBirth: Date in YYYY-MM-DD format (used for test requests)
        gender: "M" or "F" (used for test requests)
        zipCodes: Array of zip code strings (used for test requests)
        
    Returns:
        Connection status for each API endpoint
    """
    try:
        person_data = PersonRequest(
            firstName=firstName,
            lastName=lastName,
            ssn=ssn,
            dateOfBirth=dateOfBirth,
            gender=gender,
            zipCodes=zipCodes
        )
        
        # Test all APIs
        token_result = await async_get_token()
        mcid_test = await async_mcid_search(person_data)
        medical_test = await async_submit_medical_request(person_data)
        
        return {
            "success": True,
            "token_api": {
                "reachable": token_result.get('success', False),
                "status": token_result.get('status_code', 'unknown')
            },
            "mcid_api": {
                "reachable": mcid_test.get('status_code', 0) != 500,
                "status": mcid_test.get('status_code', 'unknown')
            },
            "medical_api": {
                "reachable": medical_test.get('status_code', 0) != 500,  
                "status": medical_test.get('status_code', 'unknown')
            },
            "timestamp": int(time.time())
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": int(time.time())
        }

# --- HTTP Endpoints ---

@app.post("/search_mcid")
async def search_mcid_http(person_data: PersonRequest):
    """HTTP endpoint for MCID search"""
    try:
        result = await async_mcid_search(person_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/submit_medical")
async def submit_medical_http(person_data: PersonRequest):
    """HTTP endpoint for medical submission"""
    try:
        result = await async_submit_medical_request(person_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_auth_token")
async def get_auth_token_http():
    """HTTP endpoint for getting auth token"""
    try:
        result = await async_get_token()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test_connection")
async def test_connection_http(person_data: PersonRequest):
    """HTTP endpoint for testing connections"""
    try:
        # Test all APIs
        token_result = await async_get_token()
        mcid_test = await async_mcid_search(person_data)
        medical_test = await async_submit_medical_request(person_data)
        
        return {
            "success": True,
            "token_api": {
                "reachable": token_result.get('success', False),
                "status": token_result.get('status_code', 'unknown')
            },
            "mcid_api": {
                "reachable": mcid_test.get('status_code', 0) != 500,
                "status": mcid_test.get('status_code', 'unknown')
            },
            "medical_api": {
                "reachable": medical_test.get('status_code', 0) != 500,
                "status": medical_test.get('status_code', 'unknown')
            },
            "timestamp": int(time.time())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Server status"""
    return {
        "message": "Streamlined Milliman MCP Server",
        "status": "running",
        "functions": 4,
        "available": [
            "search_mcid - Search MCID database",
            "submit_medical - Submit medical request",
            "get_auth_token - Get authentication token",
            "test_connection - Test API connectivity"
        ],
        "docs": "/docs",
        "port": 8000
    }

# --- Server Management ---
class StreamlinedServer:
    def __init__(self):
        self.http_server_thread = None
        self.running = False
    
    def start_http_server(self):
        """Start HTTP server"""
        def run_server():
            uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
        
        self.http_server_thread = threading.Thread(target=run_server, daemon=True)
        self.http_server_thread.start()
        self.running = True
        print("✅ HTTP server started on http://localhost:8000")
        print("📚 API docs: http://localhost:8000/docs")
    
    def run_mcp_mode(self):
        """Run MCP mode"""
        print("🔧 Running MCP mode (stdin/stdout)")
        mcp.run()
    
    def run_hybrid_mode(self):
        """Run both HTTP and MCP"""
        print("🚀 Starting Streamlined Milliman MCP Server...")
        print("🌐 HTTP API: http://localhost:8000")
        print("🔧 MCP Protocol: stdin/stdout")
        print("📚 API Docs: http://localhost:8000/docs")
        print("🔧 Functions: search_mcid, submit_medical, get_auth_token, test_connection")
        print("🛑 Press Ctrl+C to stop\n")
        
        self.start_http_server()
        time.sleep(2)
        
        try:
            self.run_mcp_mode()
        except KeyboardInterrupt:
            print("\n👋 Server stopped")

# --- Main Execution ---
if __name__ == "__main__":
    import sys
    
    server = StreamlinedServer()
    
    if "--http-only" in sys.argv:
        print("🌐 Starting HTTP-only mode...")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    elif "--mcp-only" in sys.argv:
        print("🔧 Starting MCP-only mode...")
        server.run_mcp_mode()
    else:
        server.run_hybrid_mode()

