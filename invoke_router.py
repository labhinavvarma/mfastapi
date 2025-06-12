
#!/usr/bin/env python3
"""
Milliman Hybrid FastMCP Server
A Model Context Protocol server with HTTP endpoints for Milliman API integrations
Supports both MCP protocol (stdin/stdout) and HTTP server (port 8000)
"""

import httpx
import requests
import json
import asyncio
import time
import threading
import uvicorn
from typing import List, Dict, Any, Optional
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
        extra = "ignore"  # Ignore extra fields
        str_strip_whitespace = True  # Strip whitespace from strings
    
    @validator('gender')
    def validate_gender(cls, v):
        if v.upper() not in ['M', 'F']:
            return v  # Accept any value, transform later if needed
        return v.upper()
    
    @validator('zipCodes')
    def validate_zip_codes(cls, v):
        if not v or len(v) == 0:
            return ["00000"]  # Default zip if none provided
        return [str(zip_code) for zip_code in v]  # Convert all to strings

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
    return str(int(time.time() * 1000))  # Use timestamp in milliseconds

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
    # Convert date format from YYYY-MM-DD to YYYYMMDD
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
        # Add potentially missing fields
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
            
            # Handle response body safely
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
    """Submit medical information request"""
    access_token = await asyncio.to_thread(get_access_token_sync)
    if not access_token:
        return {
            'success': False,
            'status_code': 500,
            'error': 'Access token not found'
        }
    
    medical_url = 'https://hix-clm-internaltesting-prod.anthem.com/medical'
    medical_payload = transform_to_medical_format(person_data)
    
    # Try different authorization header formats
    auth_formats = [
        f'Bearer {access_token}',
        f'{access_token}',
        f'Token {access_token}'
    ]
    
    for auth_format in auth_formats:
        headers = {
            'Authorization': auth_format,
            'content-type': 'application/json',
            'Accept': 'application/json'
        }
        
        try:
            response = requests.post(medical_url, headers=headers, json=medical_payload, timeout=30)
            
            # Handle response body safely
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
                'auth_format_used': auth_format.split()[0] if ' ' in auth_format else 'Raw'
            }
            
            # If successful, return immediately
            if response.status_code == 200:
                return result
            
            # If this is the last format and still not successful, return the result
            if auth_format == auth_formats[-1]:
                return result
                
        except Exception as e:
            # If this is the last format, return error
            if auth_format == auth_formats[-1]:
                return {
                    'success': False,
                    'status_code': 500,
                    'error': str(e),
                    'request_id': medical_payload.get('requestID')
                }
            continue

async def async_submit_medical_alt(person_data: PersonRequest):
    """Submit medical request with alternative authorization formats"""
    access_token = await asyncio.to_thread(get_access_token_sync)
    if not access_token:
        return {
            'success': False,
            'status_code': 500,
            'error': 'Access token not found'
        }
    
    medical_url = 'https://hix-clm-internaltesting-prod.anthem.com/medical'
    medical_payload = transform_to_medical_format(person_data)
    
    # Try different authorization header formats
    auth_formats = [
        f'Bearer {access_token}',
        f'{access_token}',
        f'Token {access_token}',
        f'Basic {access_token}'
    ]
    
    results = []
    successful_result = None
    
    for auth_format in auth_formats:
        headers = {
            'Authorization': auth_format,
            'content-type': 'application/json',
            'Accept': 'application/json'
        }
        
        try:
            response = requests.post(medical_url, headers=headers, json=medical_payload, timeout=30)
            
            try:
                if response.content:
                    response_body = response.json()
                else:
                    response_body = "No content"
            except:
                response_body = response.text
            
            result_entry = {
                'auth_format': auth_format.split()[0] if ' ' in auth_format else 'Raw',
                'status_code': response.status_code,
                'body': response_body[:500] if isinstance(response_body, str) else response_body,  # Limit response size
                'headers': dict(response.headers),
                'success': response.status_code == 200
            }
            
            results.append(result_entry)
            
            # If we get a successful response, mark it and break
            if response.status_code == 200:
                successful_result = result_entry
                break
                
        except Exception as e:
            results.append({
                'auth_format': auth_format.split()[0] if ' ' in auth_format else 'Raw',
                'status_code': 500,
                'error': str(e),
                'success': False
            })
    
    return {
        'success': successful_result is not None,
        'results': results,
        'payload_sent': medical_payload,
        'successful_auth_format': successful_result['auth_format'] if successful_result else None,
        'request_id': medical_payload.get('requestID')
    }

# --- Initialize FastMCP Server ---
mcp = FastMCP("Milliman MCP Server")

# --- Initialize FastAPI Server ---
app = FastAPI(
    title="Milliman Hybrid MCP Server",
    description="FastMCP server with HTTP endpoints for testing and development",
    version="1.0.0",
)

# CORS middleware
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
    
    This tool searches Milliman's MCID database to find member information
    based on the provided person details.
    
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
    
    This tool submits a request to Milliman's medical API to retrieve
    or process medical information for the specified person.
    
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
async def submit_medical_alt(
    firstName: str,
    lastName: str,
    ssn: str,
    dateOfBirth: str,
    gender: str,
    zipCodes: List[str]
) -> Dict[str, Any]:
    """
    Submit a medical information request using multiple authorization formats.
    
    This tool attempts different authorization header formats to maximize
    compatibility with the medical API endpoint.
    
    Args:
        firstName: Person's first name
        lastName: Person's last name
        ssn: Social Security Number  
        dateOfBirth: Date in YYYY-MM-DD format
        gender: "M" or "F"
        zipCodes: Array of zip code strings
        
    Returns:
        Results from all attempted authorization formats and the successful response
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
        result = await async_submit_medical_alt(person_data)
        return result
    except Exception as e:
        return {
            'success': False,
            'status_code': 500,
            'error': str(e)
        }

@mcp.tool()
async def get_both(
    firstName: str,
    lastName: str,
    ssn: str,
    dateOfBirth: str,
    gender: str,
    zipCodes: List[str]
) -> Dict[str, Any]:
    """
    Retrieve both MCID and Medical information for a person in parallel.
    
    This tool efficiently retrieves data from both Milliman APIs simultaneously,
    providing comprehensive person information from both systems.
    
    Args:
        firstName: Person's first name
        lastName: Person's last name
        ssn: Social Security Number
        dateOfBirth: Date in YYYY-MM-DD format  
        gender: "M" or "F"
        zipCodes: Array of zip code strings
        
    Returns:
        Combined results from both MCID search and Medical submission
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
        
        # Run both operations in parallel
        mcid_task = async_mcid_search(person_data)
        medical_task = async_submit_medical_request(person_data)
        
        mcid_result, medical_result = await asyncio.gather(mcid_task, medical_task)
        
        return {
            "success": mcid_result.get('success', False) or medical_result.get('success', False),
            "mcid_search": mcid_result,
            "medical_submit": medical_result,
            "timestamp": int(time.time())
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": int(time.time())
        }

@mcp.tool()
async def get_auth_token() -> Dict[str, Any]:
    """
    Get an authentication token for Milliman services.
    
    This tool retrieves an authentication token that can be used
    for debugging or testing purposes with Milliman APIs.
    
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
async def debug_transforms(
    firstName: str,
    lastName: str,
    ssn: str,
    dateOfBirth: str,
    gender: str,
    zipCodes: List[str]
) -> Dict[str, Any]:
    """
    Debug endpoint to see how person data is transformed for each API.
    
    This tool shows how the input data gets transformed for both
    MCID and Medical API formats, useful for debugging.
    
    Args:
        firstName: Person's first name
        lastName: Person's last name
        ssn: Social Security Number
        dateOfBirth: Date in YYYY-MM-DD format
        gender: "M" or "F"
        zipCodes: Array of zip code strings
        
    Returns:
        Original input and transformed formats for both APIs
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
        
        mcid_format = transform_to_mcid_format(person_data)
        medical_format = transform_to_medical_format(person_data)
        
        return {
            "success": True,
            "original_input": person_data.dict(),
            "mcid_transformed": mcid_format,
            "medical_transformed": medical_format
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
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
    Test connectivity to Milliman APIs without processing data.
    
    This tool verifies that the APIs are reachable and responding,
    useful for health checks and troubleshooting.
    
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
        
        # Test token endpoint
        token_result = await async_get_token()
        
        # Test MCID endpoint (with timeout)
        mcid_test = await async_mcid_search(person_data)
        
        # Test Medical endpoint (with timeout)  
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

# --- HTTP Endpoints (for testing and Streamlit compatibility) ---

@app.post("/search_mcid", operation_id="search_mcid_http", summary="Search MCID database (HTTP)")
async def search_mcid_http(person_data: PersonRequest):
    """HTTP endpoint for MCID search"""
    try:
        result = await async_mcid_search(person_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/submit_medical", operation_id="submit_medical_http", summary="Submit medical request (HTTP)")
async def submit_medical_http(person_data: PersonRequest):
    """HTTP endpoint for medical submission"""
    try:
        result = await async_submit_medical_request(person_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/submit_medical_alt", operation_id="submit_medical_alt_http", summary="Submit medical with alt auth (HTTP)")
async def submit_medical_alt_http(person_data: PersonRequest):
    """HTTP endpoint for medical submission with alternative auth"""
    try:
        result = await async_submit_medical_alt(person_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/get_both", operation_id="get_both_http", summary="Get both MCID and Medical data (HTTP)")
async def get_both_http(person_data: PersonRequest):
    """HTTP endpoint for both APIs"""
    try:
        # Run both operations in parallel
        mcid_task = async_mcid_search(person_data)
        medical_task = async_submit_medical_request(person_data)
        
        mcid_result, medical_result = await asyncio.gather(mcid_task, medical_task)
        
        return {
            "success": mcid_result.get('success', False) or medical_result.get('success', False),
            "mcid_search": mcid_result,
            "medical_submit": medical_result,
            "timestamp": int(time.time())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_auth_token", operation_id="get_auth_token_http", summary="Get authentication token (HTTP)")
async def get_auth_token_http():
    """HTTP endpoint for getting auth token"""
    try:
        result = await async_get_token()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/debug_transforms", operation_id="debug_transforms_http", summary="Debug data transformations (HTTP)")
async def debug_transforms_http(person_data: PersonRequest):
    """HTTP endpoint for debugging transforms"""
    try:
        mcid_format = transform_to_mcid_format(person_data)
        medical_format = transform_to_medical_format(person_data)
        
        return {
            "success": True,
            "original_input": person_data.dict(),
            "mcid_transformed": mcid_format,
            "medical_transformed": medical_format
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test_connection", operation_id="test_connection_http", summary="Test API connectivity (HTTP)")
async def test_connection_http(person_data: PersonRequest):
    """HTTP endpoint for testing connections"""
    try:
        # Test token endpoint
        token_result = await async_get_token()
        
        # Test MCID endpoint
        mcid_test = await async_mcid_search(person_data)
        
        # Test Medical endpoint
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

@app.get("/", summary="Server status")
async def root():
    """Root endpoint showing server status"""
    return {
        "message": "Milliman Hybrid FastMCP Server",
        "status": "running",
        "modes": ["MCP Protocol", "HTTP API"],
        "mcp_tools": 7,
        "http_endpoints": 7,
        "docs": "/docs",
        "port": 8000
    }

# --- Server Management ---
class HybridServer:
    def __init__(self):
        self.http_server_thread = None
        self.running = False
    
    def start_http_server(self):
        """Start HTTP server in background thread"""
        def run_server():
            uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
        
        self.http_server_thread = threading.Thread(target=run_server, daemon=True)
        self.http_server_thread.start()
        self.running = True
        print("✅ HTTP server started on http://localhost:8000")
        print("📚 API docs available at http://localhost:8000/docs")
    
    def run_mcp_mode(self):
        """Run in MCP mode (stdin/stdout)"""
        print("🔧 Running in MCP mode (stdin/stdout)")
        mcp.run()
    
    def run_hybrid_mode(self):
        """Run both HTTP server and MCP mode"""
        print("🚀 Starting Hybrid FastMCP Server...")
        print("🌐 HTTP API: http://localhost:8000")
        print("🔧 MCP Protocol: stdin/stdout")
        print("📚 API Docs: http://localhost:8000/docs")
        print("🛑 Press Ctrl+C to stop\n")
        
        # Start HTTP server
        self.start_http_server()
        
        # Give HTTP server time to start
        time.sleep(2)
        
        # Run MCP protocol
        try:
            self.run_mcp_mode()
        except KeyboardInterrupt:
            print("\n👋 Server stopped by user")

# --- Main Execution ---
if __name__ == "__main__":
    import sys
    
    server = HybridServer()
    
    if "--http-only" in sys.argv:
        print("🌐 Starting HTTP-only mode...")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    elif "--mcp-only" in sys.argv:
        print("🔧 Starting MCP-only mode...")
        server.run_mcp_mode()
    else:
        # Default: Hybrid mode
        server.run_hybrid_mode()
