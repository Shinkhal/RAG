import time
import uuid
from typing import Callable, Awaitable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.logger import logger

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Log incoming request
        logger.info(f"Incoming request: {request.method} {request.url.path} (ID: {request_id})")
        
        try:
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000
            
            # Log successful response
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"- Status: {response.status_code} "
                f"- Duration: {process_time:.2f}ms (ID: {request_id})"
            )
            
            # Add process time header
            response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
            response.headers["X-Request-ID"] = request_id
            return response
            
        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"- Duration: {process_time:.2f}ms - Error: {str(e)} (ID: {request_id})",
                exc_info=True
            )
            raise
