import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool  # used for sync optimizer

from .llm import ModelError, interpret_notes
from .models import Plan, Scenario
from .optimizer import InfeasibleError, optimize


app = FastAPI(title="GridWise LLM Energy Optimizer", version="1.0.0")


@app.exception_handler(RequestValidationError)
async def bad_request(request, error):
    return JSONResponse(status_code=400, content={"error": "Invalid JSON or request schema"})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/optimize-energy", response_model=Plan)
async def optimize_energy(scenario: Scenario):
    try:
        context = {
            "operator_notes": scenario.operator_notes,
            "battery_capacity_kwh": scenario.battery.capacity_kwh,
        }
        directives = await interpret_notes(context, scenario)
        return await run_in_threadpool(optimize, scenario, directives)
    except ModelError:
        return JSONResponse(status_code=500, content={"error": "Language model unavailable or invalid output"})
    except InfeasibleError:
        return JSONResponse(status_code=422, content={"error": "Interpreted constraints are infeasible"})
    except Exception as error:
        logging.getLogger("gridwise").error("Optimization failed: %s", type(error).__name__)
        return JSONResponse(status_code=500, content={"error": "Unable to produce a verified schedule"})
