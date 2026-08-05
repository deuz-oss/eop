import uuid
from datetime import date

from eop_api.models.hr_employee import HrEmployee
from eop_api.models.user import User
from eop_api.services.approval_authorization import ApprovalAuthorizationEvaluator
from eop_api.services.authorization_decision import AuthorizationDecision
from eop_api.services.authorization_request import AuthorizationRequest
from eop_api.services.employee_context import EmployeeContext, RequestContext


def _request_context(*, employee_id: uuid.UUID | None = None) -> RequestContext:
    """A `RequestContext` built entirely in memory -- no database involved.

    Mirrors `test_authorization_evaluator.py`'s `_request_context` helper:
    the Approval Authorization Policy (`ADR-008`) is evaluated purely from
    `AuthorizationRequest`/its resolved `manager_id`, with no persistence
    dependency of its own.
    """
    user = User(
        id=uuid.uuid4(),
        email="ada@example.com",
        password_hash="hash",
        full_name="Ada Lovelace",
        is_active=True,
    )
    employee = HrEmployee(
        id=employee_id or uuid.uuid4(),
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


def test_direct_manager_is_allowed():
    approver_context = _request_context()
    approver_employee_id = approver_context.employee_context.employee.id
    evaluator = ApprovalAuthorizationEvaluator(requester_manager_id=approver_employee_id)

    decision = evaluator.evaluate(AuthorizationRequest(context=approver_context))

    assert decision == AuthorizationDecision(allowed=True)


def test_non_manager_is_denied():
    approver_context = _request_context()
    evaluator = ApprovalAuthorizationEvaluator(requester_manager_id=uuid.uuid4())

    decision = evaluator.evaluate(AuthorizationRequest(context=approver_context))

    assert decision.allowed is False
    assert decision.reason is not None


def test_requester_without_manager_is_denied():
    approver_context = _request_context()
    evaluator = ApprovalAuthorizationEvaluator(requester_manager_id=None)

    decision = evaluator.evaluate(AuthorizationRequest(context=approver_context))

    assert decision.allowed is False


def test_self_approval_is_denied():
    """A requester attempting to approve their own request: the evaluator only
    ever sees `requester_manager_id` and the approver's own employee id, so
    self-approval is denied by the same equality check as any other
    non-manager -- no separate self-approval branch exists
    (`decision.md`: "No explicit self-approval rule exists beyond the
    approval policy itself")."""
    requester_employee_id = uuid.uuid4()
    approver_context = _request_context(employee_id=requester_employee_id)
    # The requester's own manager is someone else -- self-management is
    # already rejected at the data layer (`SelfManagerError`), so
    # `manager_id` can never legitimately equal the requester's own id.
    evaluator = ApprovalAuthorizationEvaluator(requester_manager_id=uuid.uuid4())

    decision = evaluator.evaluate(AuthorizationRequest(context=approver_context))

    assert decision.allowed is False
