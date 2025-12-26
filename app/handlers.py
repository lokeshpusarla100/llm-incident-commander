"""
Exception handlers for LLM Incident Commander.
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse


async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom exception handler to ensure consistent error responses"""
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail if isinstance(exc.detail, dict) else {
            "error": "http_error",
            "message": str(exc.detail),
            "request_id": request_id
        }
    )
