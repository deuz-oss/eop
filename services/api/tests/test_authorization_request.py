import dataclasses
import uuid
from datetime import date

import pytest

from eop_api.models.hr_employee import HrEmployee
from eop_api.models.user import User
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


def test_request_carries_the_request_context():
    context = _request_context()

    request = AuthorizationRequest(context=context)

    assert request.context is context


def test_request_is_immutable():
    request = AuthorizationRequest(context=_request_context())

    with pytest.raises(dataclasses.FrozenInstanceError):
        request.context = _request_context()  # type: ignore[misc]


def test_request_resource_defaults_to_none():
    request = AuthorizationRequest(context=_request_context())

    assert request.resource is None


def test_request_carries_an_opaque_resource():
    resource = object()

    request = AuthorizationRequest(context=_request_context(), resource=resource)

    assert request.resource is resource
