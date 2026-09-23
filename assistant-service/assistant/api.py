import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from .models import Message
from .service import AssistantService
from .storage import MemorySessions
from .catalog_client import CatalogClient
from .llm import LLM

def create_app(service=None):
    service=service or AssistantService(CatalogClient(os.getenv("CATALOG_SERVICE_URL","http://localhost:8001"),os.getenv("INTERNAL_API_TOKEN","")),LLM(),MemorySessions())
    app=FastAPI(title="HackAlem Assistant")
    app.state.service=service
    app.add_middleware(CORSMiddleware,allow_origins=os.getenv("CORS_ORIGINS","http://localhost:3000,http://127.0.0.1:3000").split(","),allow_methods=["POST"],allow_headers=["Content-Type"])
    def error(status,code,text): return JSONResponse(status_code=status,content={"error":{"code":code,"message":text}})
    @app.exception_handler(RequestValidationError)
    async def invalid(request,exc): return error(400,"invalid_request","Проверьте session_id, text и history.")
    @app.exception_handler(HTTPException)
    async def http_error(request,exc): return error(exc.status_code,"http_error",str(exc.detail))
    @app.exception_handler(Exception)
    async def unexpected(request,exc):
        logging.getLogger("assistant").error('{"event":"request_failed"}')
        return error(503,"unavailable","Сервис временно недоступен. Попробуйте позже.")
    @app.get("/health")
    async def health(): return {"status":"ok","catalog_service_reachable":await service.catalog.health()}
    @app.post("/assistant/message")
    async def message(body:Message): return await service.message(body)
    return app
app=create_app()
