import uuid
from datetime import date

from eop_api.models.hr_employee import HrEmployee
from eop_api.models.user import User
from eop_api.services.authorization import AuthorizationService
from eop_api.services.authorization_decision import AuthorizationDecision
from eop_api.services.authorization_evaluator import AuthorizationEvaluator
from eop_api.services.authorization_request import AuthorizationRequest
from eop_api.services.employee_context import EmployeeContext, RequestContext


def _request_context() -> RequestContext:
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


def test_authorize_delegates_to_the_evaluator_and_returns_its_decision():
    request = AuthorizationRequest(context=_request_context())
    expected = AuthorizationDecision(allowed=True)

    class StubEvaluator(AuthorizationEvaluator):
        def evaluate(self, request: AuthorizationRequest) -> AuthorizationDecision:
            self.received = request
            return expected

    evaluator = StubEvaluator()
    service = AuthorizationService(evaluator=evaluator)

    decision = service.authorize(request)

    assert decision is expected
    assert evaluator.received is request


def test_authorize_defaults_to_a_real_evaluator_when_none_is_supplied():
    service = AuthorizationService()
    request = AuthorizationRequest(context=_request_context())

    decision = service.authorize(request)

    assert decision == AuthorizationDecision(allowed=True)


def test_authorize_returns_denied_decision_from_a_replaced_evaluator():
    class DenyAllEvaluator(AuthorizationEvaluator):
        def evaluate(self, request: AuthorizationRequest) -> AuthorizationDecision:
            return AuthorizationDecision(allowed=False, reason="denied by policy")

    service = AuthorizationService(evaluator=DenyAllEvaluator())
    request = AuthorizationRequest(context=_request_context())

    decision = service.authorize(request)

    assert decision.allowed is False
