from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from eop_api.api.assignments import router as assignments_router
from eop_api.api.attendance_events import router as attendance_events_router
from eop_api.api.audit_logs import router as audit_logs_router
from eop_api.api.auth import router as auth_router
from eop_api.api.compensation import router as compensation_router
from eop_api.api.dashboard import router as dashboard_router
from eop_api.api.departments import router as departments_router
from eop_api.api.employees import router as employees_router
from eop_api.api.employment_statuses import router as employment_statuses_router
from eop_api.api.employment_types import router as employment_types_router
from eop_api.api.files import router as files_router
from eop_api.api.health import router as health_router
from eop_api.api.holidays import router as holidays_router
from eop_api.api.hr_employees import router as hr_employees_router
from eop_api.api.job_grades import router as job_grades_router
from eop_api.api.leave_balances import router as leave_balances_router
from eop_api.api.leave_requests import router as leave_requests_router
from eop_api.api.location_types import router as location_types_router
from eop_api.api.locations import router as locations_router
from eop_api.api.organizations import router as organizations_router
from eop_api.api.overtime_requests import router as overtime_requests_router
from eop_api.api.payroll_calculation import router as payroll_calculation_router
from eop_api.api.payroll_runs import router as payroll_runs_router
from eop_api.api.payslips import router as payslips_router
from eop_api.api.positions import router as positions_router
from eop_api.api.projects import router as projects_router
from eop_api.api.reconciliation import router as reconciliation_router
from eop_api.api.roles import router as roles_router
from eop_api.api.shifts import router as shifts_router
from eop_api.api.tasks import router as tasks_router
from eop_api.api.teams import router as teams_router
from eop_api.api.timesheets import router as timesheets_router
from eop_api.core.config import settings
from eop_api.core.logging import configure_logging
from eop_api.db.engine import engine
from eop_api.exceptions.handlers import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from eop_api.middleware.request_id import RequestIDMiddleware
from eop_api.middleware.request_logging import RequestLoggingMiddleware
from eop_api.schemas.problem import Problem, ValidationProblem

PROBLEM_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": Problem, "description": "Unauthorized"},
    403: {"model": Problem, "description": "Forbidden"},
    404: {"model": Problem, "description": "Not Found"},
    422: {"model": ValidationProblem, "description": "Validation Error"},
}

configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    logger.info("Database initialized")
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(health_router)
app.include_router(auth_router, responses=PROBLEM_RESPONSES)
app.include_router(organizations_router, responses=PROBLEM_RESPONSES)
app.include_router(projects_router, responses=PROBLEM_RESPONSES)
app.include_router(employees_router, responses=PROBLEM_RESPONSES)
# TODO: Locations (and location types) are authenticated-only for now. Once the
# platform defines administrative roles for master data, gate these routes with
# RequireRole(...) the way roles.py does.
app.include_router(locations_router, responses=PROBLEM_RESPONSES)
app.include_router(location_types_router, responses=PROBLEM_RESPONSES)
app.include_router(departments_router, responses=PROBLEM_RESPONSES)
app.include_router(positions_router, responses=PROBLEM_RESPONSES)
app.include_router(teams_router, responses=PROBLEM_RESPONSES)
app.include_router(hr_employees_router, responses=PROBLEM_RESPONSES)
app.include_router(job_grades_router, responses=PROBLEM_RESPONSES)
app.include_router(employment_types_router, responses=PROBLEM_RESPONSES)
app.include_router(employment_statuses_router, responses=PROBLEM_RESPONSES)
app.include_router(shifts_router, responses=PROBLEM_RESPONSES)
app.include_router(holidays_router, responses=PROBLEM_RESPONSES)
app.include_router(compensation_router, responses=PROBLEM_RESPONSES)
app.include_router(attendance_events_router, responses=PROBLEM_RESPONSES)
app.include_router(leave_requests_router, responses=PROBLEM_RESPONSES)
app.include_router(leave_balances_router, responses=PROBLEM_RESPONSES)
app.include_router(overtime_requests_router, responses=PROBLEM_RESPONSES)
app.include_router(payroll_runs_router, responses=PROBLEM_RESPONSES)
app.include_router(payslips_router, responses=PROBLEM_RESPONSES)
app.include_router(payroll_calculation_router, responses=PROBLEM_RESPONSES)
app.include_router(timesheets_router, responses=PROBLEM_RESPONSES)
app.include_router(reconciliation_router, responses=PROBLEM_RESPONSES)
app.include_router(assignments_router, responses=PROBLEM_RESPONSES)
app.include_router(tasks_router, responses=PROBLEM_RESPONSES)
app.include_router(roles_router, responses=PROBLEM_RESPONSES)
app.include_router(dashboard_router, responses=PROBLEM_RESPONSES)
app.include_router(audit_logs_router, responses=PROBLEM_RESPONSES)
app.include_router(files_router, responses=PROBLEM_RESPONSES)


@app.get("/", tags=["Root"])
async def root():
    return {
        "application": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "running",
    }
