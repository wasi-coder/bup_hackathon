import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .llm import Interpreter, ModelError, Settings
from .models import Plan, Scenario
from .optimizer import InfeasibleError, optimize


def create_app(interpreter=None):
    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(trust_env=False) as client:
            app.state.interpreter = interpreter or Interpreter(Settings.from_env(), client)
            yield

    app = FastAPI(title="GridWise LLM Energy Optimizer", version="1.0.0", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def bad_request(request, error):
        return JSONResponse(status_code=400, content={"error": "Invalid JSON or request schema"})

    @app.get("/health")
    async def health(request: Request):
        if await request.app.state.interpreter.ready():
            return {"status": "ok"}
        return JSONResponse(status_code=503, content={"status": "not_ready"})

    @app.post("/optimize-energy", response_model=Plan)
    async def optimize_energy(scenario: Scenario, request: Request):
        try:
            directives = await request.app.state.interpreter.interpret(scenario)
            return await run_in_threadpool(optimize, scenario, directives)
        except ModelError:
            return JSONResponse(status_code=500, content={"error": "Language model unavailable or invalid output"})
        except InfeasibleError:
            return JSONResponse(status_code=422, content={"error": "Interpreted constraints are infeasible"})
        except Exception as error:
            logging.getLogger("gridwise").error("Optimization failed: %s", type(error).__name__)
            return JSONResponse(status_code=500, content={"error": "Unable to produce a verified schedule"})

    return app


app = create_app()
