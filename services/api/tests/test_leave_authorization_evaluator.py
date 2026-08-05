import uuid
from datetime import date

from eop_api.models.hr_employee import HrEmployee
from eop_api.models.leave_request import LeaveRequest
from eop_api.models.user import User
from eop_api.services.authorization_decision import AuthorizationDecision
from eop_api.services.authorization_request import AuthorizationRequest
from eop_api.services.employee_context import EmployeeContext, RequestContext
from eop_api.services.leave_authorization import LeaveAuthorizationEvaluator


def _request_context() -> RequestContext:
    """A `RequestContext` built entirely in memory -- no database involved.

    Mirrors `test_approval_authorization_evaluator.py`'s helper: the Leave
    Authorization Policy (Owner Only) is evaluated purely from
    `AuthorizationRequest`/its `resource`, with no persistence dependency
    of its own.
    """
    user = User(
        id=uuid.uuid4(),
        email="ada@example.com",
        password_hash="hash",
        full_name="Ada Lovelace",
        is_active=True,
    )
    employee = HrEmployee(
        id=uuid.uuid4(),
        employee_number="E-001",
        first_name="Ada",
        last_name="Lovelace",
        full_name="Ada Lovelace",
        email="ada@example.com",
        organization_id=uuid.uuid4(),
        department_id=uuid.uuid4(),
        position_id=uuid.uuid4(),
        team_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        job_grade_id=uuid.uuid4(),
        employment_type_id=uuid.uuid4(),
        employment_status_id=uuid.uuid4(),
        shift_id=uuid.uuid4(),
        hire_date=date(2020, 1, 1),
        employment_status="active",
        user_id=user.id,
    )
    return RequestContext(user=user, employee_context=EmployeeContext(user=user, employee=employee))


def _leave_request(employee_id: uuid.UUID) -> LeaveRequest:
    return LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        start_date=date(2026, 2, 10),
        end_date=date(2026, 2, 12),
        status="pending",
    )


def test_owner_is_allowed():
    context = _request_context()
    current_employee_id = context.employee_context.employee.id
    evaluator = LeaveAuthorizationEvaluator()

    decision = evaluator.evaluate(
        AuthorizationRequest(context=context, resource=_leave_request(current_employee_id))
    )

    assert decision == AuthorizationDecision(allowed=True)


def test_non_owner_is_denied():
    context = _request_context()
    evaluator = LeaveAuthorizationEvaluator()

    decision = evaluator.evaluate(
        AuthorizationRequest(context=context, resource=_leave_request(uuid.uuid4()))
    )

    assert decision.allowed is False
    assert decision.reason is not None


def test_missing_resource_is_denied():
    """`resource=None` (the `AuthorizationRequest` default) is denied rather
    than raising -- the evaluator never assumes `resource` was populated."""
    context = _request_context()
    evaluator = LeaveAuthorizationEvaluator()

    decision = evaluator.evaluate(AuthorizationRequest(context=context))

    assert decision.allowed is False
