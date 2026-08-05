import uuid
from datetime import date

from eop_api.models.hr_employee import HrEmployee
from eop_api.models.user import User
from eop_api.services.authorization_decision import AuthorizationDecision
from eop_api.services.authorization_evaluator import AuthorizationEvaluator
from eop_api.services.authorization_request import AuthorizationRequest
from eop_api.services.employee_context import EmployeeContext, RequestContext


def _request_context() -> RequestContext:
    """A `RequestContext` built entirely in memory -- no database involved.

    Foundation-layer authorization has no persistence dependency (`ADR-007`),
    so its tests do not need one either.
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


def test_default_evaluator_allows_every_request():
    evaluator = AuthorizationEvaluator()
    request = AuthorizationRequest(context=_request_context())

    decision = evaluator.evaluate(request)

    assert decision == AuthorizationDecision(allowed=True)


def test_evaluator_is_replaceable_via_subclassing():
    """`ADR-007`: future authorization models replace/subclass the evaluator
    rather than being injected as a per-call predicate. This confirms the
    extension point works and can produce a denied decision."""

    class DenyAllEvaluator(AuthorizationEvaluator):
        def evaluate(self, request: AuthorizationRequest) -> AuthorizationDecision:
            return AuthorizationDecision(allowed=False, reason="denied by policy")

    evaluator = DenyAllEvaluator()
    request = AuthorizationRequest(context=_request_context())

    decision = evaluator.evaluate(request)

    assert decision == AuthorizationDecision(allowed=False, reason="denied by policy")
