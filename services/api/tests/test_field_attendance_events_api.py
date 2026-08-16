import asyncio
import io
import uuid
from collections.abc import AsyncIterator, Generator
from typing import BinaryIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.api.files import get_file_service
from eop_api.core.config import settings
from eop_api.core.security import hash_password
from eop_api.db.base import Base
from eop_api.main import app
from eop_api.models.user import User
from eop_api.repositories.role import RoleRepository
from eop_api.repositories.user import UserRepository
from eop_api.services.file import FileService
from eop_api.storage.base import StorageProvider
from eop_api.storage.exceptions import StorageObjectNotFoundError

DEFAULT_EVENT_TIME = "2026-01-05T09:00:00Z"


class FakeStorageProvider(StorageProvider):
    """In-memory `StorageProvider` test double -- no real MinIO involved.
    Mirrors `test_files_api.py`'s exact test double, since `_upload_selfie`
    below exercises the same real `POST /files` endpoint to obtain a
    `selfie_file_id`."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    async def upload(
        self, *, bucket: str, key: str, data: BinaryIO, length: int, content_type: str
    ) -> None:
        self.objects[(bucket, key)] = data.read()

    async def download(self, *, bucket: str, key: str) -> AsyncIterator[bytes]:
        if (bucket, key) not in self.objects:
            raise StorageObjectNotFoundError(key)
        content = self.objects[(bucket, key)]

        async def _stream() -> AsyncIterator[bytes]:
            yield content

        return _stream()

    async def delete(self, *, bucket: str, key: str) -> None:
        self.objects.pop((bucket, key), None)

    async def exists(self, *, bucket: str, key: str) -> bool:
        return (bucket, key) in self.objects


@pytest.fixture
def fake_storage() -> FakeStorageProvider:
    return FakeStorageProvider()


@pytest.fixture(autouse=True)
def _override_file_service(fake_storage: FakeStorageProvider) -> Generator[None]:
    """Routes the API through a fake storage provider instead of real MinIO."""
    app.dependency_overrides[get_file_service] = lambda: FileService(storage=fake_storage)
    yield
    app.dependency_overrides.pop(get_file_service, None)


@pytest.fixture(autouse=True)
def _tables() -> Generator[None]:
    async def _create() -> None:
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def _truncate() -> None:
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "TRUNCATE TABLE organizations, locations, location_types, "
                    "job_grades, employment_types, employment_statuses, shifts, "
                    "file_objects, users CASCADE"
                )
            )
        await engine.dispose()

    asyncio.run(_create())
    yield
    asyncio.run(_truncate())


@pytest.fixture
def client() -> Generator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


async def _create_user(*, email: str, password: str) -> User:
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        user = await UserRepository(session).create(
            email=email,
            password_hash=hash_password(password),
            full_name="Test User",
            is_active=True,
        )
        await session.commit()
        session.expunge(user)
    await engine.dispose()
    return user


@pytest.fixture
def user() -> User:
    return asyncio.run(_create_user(email="member@example.com", password="member-pass"))


@pytest.fixture
def user_headers(client: TestClient, user: User) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": "member@example.com", "password": "member-pass"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other() -> User:
    """An authenticated user who does not own the field attendance event
    under test."""
    return asyncio.run(_create_user(email="other@example.com", password="other-pass"))


@pytest.fixture
def other_headers(client: TestClient, other: User) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": "other@example.com", "password": "other-pass"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _seed_location_admin(user_id: uuid.UUID) -> None:
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        repo = RoleRepository(session)
        role = await repo.get_by_name("admin")
        if role is None:
            role = await repo.create(name="admin")
        await repo.assign_user(role.id, user_id)
        await session.commit()
    await engine.dispose()


def _location_admin_headers(client: TestClient) -> dict[str, str]:
    """A throwaway admin session used only to satisfy the admin-only
    Location/LocationType write requirement during master-data bootstrap --
    the employee/user actually under test keeps its own identity."""
    suffix = uuid.uuid4().hex[:8]
    email = f"location-admin-{suffix}@example.com"
    user = asyncio.run(_create_user(email=email, password="admin-pass"))
    asyncio.run(_seed_location_admin(user.id))
    response = client.post("/auth/login", json={"email": email, "password": "admin-pass"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_employee(
    client: TestClient,
    headers: dict[str, str],
    *,
    employee_number: str = "EMP-1",
    email: str = "ada@example.com",
    first_name: str = "Ada",
    last_name: str = "Lovelace",
    full_name: str = "Ada Lovelace",
    user_id: str | None = None,
) -> dict:
    suffix = uuid.uuid4().hex[:8]
    organization = client.post(
        "/organizations", json={"name": f"Acme Corp {suffix}"}, headers=headers
    ).json()
    department = client.post(
        "/departments",
        json={
            "name": "Engineering",
            "code": f"ENG-{suffix}",
            "organization_id": organization["id"],
        },
        headers=headers,
    ).json()
    position = client.post(
        "/positions",
        json={
            "name": "Engineer",
            "code": f"POS-{suffix}",
            "organization_id": organization["id"],
            "department_id": department["id"],
        },
        headers=headers,
    ).json()
    team = client.post(
        "/teams",
        json={
            "name": "Backend",
            "code": f"TEAM-{suffix}",
            "organization_id": organization["id"],
            "department_id": department["id"],
        },
        headers=headers,
    ).json()
    location_admin_headers = _location_admin_headers(client)
    location_type = client.post(
        "/location-types",
        json={"name": "Office", "code": f"OFFICE-{suffix}"},
        headers=location_admin_headers,
    ).json()
    location = client.post(
        "/locations",
        json={"name": "HQ", "code": f"HQ-{suffix}", "location_type_id": location_type["id"]},
        headers=location_admin_headers,
    ).json()
    job_grade = client.post(
        "/hr/job-grades",
        json={"name": "Engineer I", "code": f"L1-{suffix}", "level": int(suffix[:4], 16) + 1},
        headers=headers,
    ).json()
    employment_type = client.post(
        "/hr/employment-types", json={"name": "Full-Time", "code": f"FT-{suffix}"}, headers=headers
    ).json()
    employment_status = client.post(
        "/hr/employment-statuses",
        json={"name": "Active", "code": f"ACTIVE-{suffix}"},
        headers=headers,
    ).json()
    shift = client.post(
        "/hr/shifts",
        json={
            "code": f"DAY-{suffix}",
            "name": "Day Shift",
            "start_time": "09:00:00",
            "end_time": "17:00:00",
        },
        headers=headers,
    ).json()

    payload: dict = {
        "employee_number": employee_number,
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "email": email,
        "organization_id": organization["id"],
        "department_id": department["id"],
        "position_id": position["id"],
        "team_id": team["id"],
        "location_id": location["id"],
        "job_grade_id": job_grade["id"],
        "employment_type_id": employment_type["id"],
        "employment_status_id": employment_status["id"],
        "shift_id": shift["id"],
        "hire_date": "2024-01-15",
        "employment_status": "active",
    }
    if user_id is not None:
        payload["user_id"] = user_id

    response = client.post("/hr/employees", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


def _upload_selfie(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post(
        "/files",
        headers=headers,
        files={"file": ("selfie.jpg", io.BytesIO(b"fake-image-bytes"), "image/jpeg")},
    )
    assert response.status_code == 201
    return response.json()


def _event_payload(employee_id: str, selfie_file_id: str, **overrides) -> dict:
    payload = {
        "employee_id": employee_id,
        "event_type": "CHECK_IN",
        "event_time": DEFAULT_EVENT_TIME,
        "latitude": "-6.200000",
        "longitude": "106.816666",
        "gps_accuracy_meters": "12.50",
        "selfie_file_id": selfie_file_id,
    }
    payload.update(overrides)
    return payload


def _create_event(
    client: TestClient, headers: dict[str, str], employee_id: str, selfie_file_id: str, **overrides
) -> dict:
    response = client.post(
        "/field-attendance",
        json=_event_payload(employee_id, selfie_file_id, **overrides),
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_create_event_requires_authentication(client: TestClient):
    response = client.post(
        "/field-attendance", json=_event_payload(str(uuid.uuid4()), str(uuid.uuid4()))
    )
    assert response.status_code == 401


def test_list_events_requires_authentication(client: TestClient):
    assert client.get("/field-attendance").status_code == 401


def test_get_event_requires_authentication(client: TestClient):
    assert client.get(f"/field-attendance/{uuid.uuid4()}").status_code == 401


def test_update_event_requires_authentication(client: TestClient):
    response = client.put(f"/field-attendance/{uuid.uuid4()}", json={"event_type": "CHECK_OUT"})
    assert response.status_code == 401


def test_delete_event_requires_authentication(client: TestClient):
    assert client.delete(f"/field-attendance/{uuid.uuid4()}").status_code == 401


def test_create_event(client: TestClient, user: User, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    selfie = _upload_selfie(client, user_headers)

    body = _create_event(client, user_headers, employee["id"], selfie["id"])

    assert body["employee_id"] == employee["id"]
    assert body["event_type"] == "CHECK_IN"
    assert body["latitude"] == "-6.200000"
    assert body["longitude"] == "106.816666"
    assert body["gps_accuracy_meters"] == "12.50"
    assert body["selfie_file_id"] == selfie["id"]
    uuid.UUID(body["id"])


def test_create_event_rejects_missing_employee(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    """`user` must have a linked HrEmployee for `CurrentRequestContext` to
    resolve at all -- the missing employee under test is a second,
    unrelated, nonexistent `employee_id` referenced in the request body."""
    _create_employee(client, user_headers, user_id=str(user.id))
    selfie = _upload_selfie(client, user_headers)

    response = client.post(
        "/field-attendance",
        json=_event_payload(str(uuid.uuid4()), selfie["id"]),
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_event_rejects_missing_selfie_file(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))

    response = client.post(
        "/field-attendance",
        json=_event_payload(employee["id"], str(uuid.uuid4())),
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_event_rejects_invalid_latitude(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    selfie = _upload_selfie(client, user_headers)

    response = client.post(
        "/field-attendance",
        json=_event_payload(employee["id"], selfie["id"], latitude="91.0"),
        headers=user_headers,
    )

    assert response.status_code == 422


def test_create_event_rejects_negative_gps_accuracy(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    selfie = _upload_selfie(client, user_headers)

    response = client.post(
        "/field-attendance",
        json=_event_payload(employee["id"], selfie["id"], gps_accuracy_meters="-1"),
        headers=user_headers,
    )

    assert response.status_code == 422


def test_create_event_allows_multiple_per_employee(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    selfie = _upload_selfie(client, user_headers)
    _create_event(client, user_headers, employee["id"], selfie["id"], event_type="CHECK_IN")

    response = client.post(
        "/field-attendance",
        json=_event_payload(employee["id"], selfie["id"], event_type="CHECK_OUT"),
        headers=user_headers,
    )

    assert response.status_code == 201


def test_create_event_forbidden_for_non_owner(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    selfie = _upload_selfie(client, other_headers)

    response = client.post(
        "/field-attendance",
        json=_event_payload(employee["id"], selfie["id"]),
        headers=other_headers,
    )

    assert response.status_code == 403


def test_get_event(client: TestClient, user: User, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    selfie = _upload_selfie(client, user_headers)
    created = _create_event(client, user_headers, employee["id"], selfie["id"])

    response = client.get(f"/field-attendance/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_event_not_found(client: TestClient, user: User, user_headers: dict[str, str]):
    _create_employee(client, user_headers, user_id=str(user.id))

    response = client.get(f"/field-attendance/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_get_event_forbidden(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    selfie = _upload_selfie(client, user_headers)
    created = _create_event(client, user_headers, employee["id"], selfie["id"])
    _create_employee(
        client,
        user_headers,
        employee_number="OTH-1",
        email="other.employee@example.com",
        first_name="Bob",
        last_name="Smith",
        full_name="Bob Smith",
        user_id=str(other.id),
    )

    response = client.get(f"/field-attendance/{created['id']}", headers=other_headers)

    assert response.status_code == 403


def test_list_events_returns_only_owned(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    other_employee = _create_employee(
        client,
        user_headers,
        employee_number="OTH-1",
        email="other.employee@example.com",
        first_name="Bob",
        last_name="Smith",
        full_name="Bob Smith",
        user_id=str(other.id),
    )
    selfie = _upload_selfie(client, user_headers)
    other_selfie = _upload_selfie(client, other_headers)
    _create_event(client, user_headers, employee["id"], selfie["id"])
    _create_event(client, other_headers, other_employee["id"], other_selfie["id"])

    response = client.get("/field-attendance", headers=user_headers)

    assert response.status_code == 200
    assert {item["employee_id"] for item in response.json()} == {employee["id"]}


def test_list_events_paginated_returns_only_owned(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    other_employee = _create_employee(
        client,
        user_headers,
        employee_number="OTH-1",
        email="other.employee@example.com",
        first_name="Bob",
        last_name="Smith",
        full_name="Bob Smith",
        user_id=str(other.id),
    )
    selfie = _upload_selfie(client, user_headers)
    other_selfie = _upload_selfie(client, other_headers)
    _create_event(client, user_headers, employee["id"], selfie["id"])
    _create_event(client, other_headers, other_employee["id"], other_selfie["id"])

    response = client.get("/field-attendance/paginated", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["employee_id"] == employee["id"]


def test_list_events_paginated_filters_by_event_type(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    selfie = _upload_selfie(client, user_headers)
    _create_event(client, user_headers, employee["id"], selfie["id"], event_type="CHECK_IN")
    _create_event(client, user_headers, employee["id"], selfie["id"], event_type="CHECK_OUT")

    response = client.get(
        "/field-attendance/paginated", params={"event_type": "CHECK_IN"}, headers=user_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["event_type"] == "CHECK_IN"


def test_list_events_paginated_ignores_client_supplied_employee_id(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    other_employee = _create_employee(
        client,
        user_headers,
        employee_number="OTH-1",
        email="other.employee@example.com",
        first_name="Bob",
        last_name="Smith",
        full_name="Bob Smith",
        user_id=str(other.id),
    )
    selfie = _upload_selfie(client, user_headers)
    other_selfie = _upload_selfie(client, other_headers)
    _create_event(client, user_headers, employee["id"], selfie["id"])
    _create_event(client, other_headers, other_employee["id"], other_selfie["id"])

    response = client.get(
        "/field-attendance/paginated",
        params={"employee_id": other_employee["id"]},
        headers=user_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["employee_id"] == employee["id"]


def test_update_event(client: TestClient, user: User, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    selfie = _upload_selfie(client, user_headers)
    created = _create_event(client, user_headers, employee["id"], selfie["id"])

    response = client.put(
        f"/field-attendance/{created['id']}",
        json={"event_type": "CHECK_OUT"},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["event_type"] == "CHECK_OUT"


def test_update_event_not_found(client: TestClient, user: User, user_headers: dict[str, str]):
    _create_employee(client, user_headers, user_id=str(user.id))

    response = client.put(
        f"/field-attendance/{uuid.uuid4()}", json={"event_type": "CHECK_OUT"}, headers=user_headers
    )

    assert response.status_code == 404


def test_update_event_forbidden(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    selfie = _upload_selfie(client, user_headers)
    created = _create_event(client, user_headers, employee["id"], selfie["id"])
    _create_employee(
        client,
        user_headers,
        employee_number="OTH-1",
        email="other.employee@example.com",
        first_name="Bob",
        last_name="Smith",
        full_name="Bob Smith",
        user_id=str(other.id),
    )

    response = client.put(
        f"/field-attendance/{created['id']}",
        json={"event_type": "CHECK_OUT"},
        headers=other_headers,
    )

    assert response.status_code == 403


def test_delete_event(client: TestClient, user: User, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    selfie = _upload_selfie(client, user_headers)
    created = _create_event(client, user_headers, employee["id"], selfie["id"])

    response = client.delete(f"/field-attendance/{created['id']}", headers=user_headers)

    assert response.status_code == 204
    assert client.get(f"/field-attendance/{created['id']}", headers=user_headers).status_code == 404


def test_delete_event_not_found(client: TestClient, user: User, user_headers: dict[str, str]):
    _create_employee(client, user_headers, user_id=str(user.id))

    response = client.delete(f"/field-attendance/{uuid.uuid4()}", headers=user_headers)
    assert response.status_code == 404


def test_delete_event_forbidden(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    selfie = _upload_selfie(client, user_headers)
    created = _create_event(client, user_headers, employee["id"], selfie["id"])
    _create_employee(
        client,
        user_headers,
        employee_number="OTH-1",
        email="other.employee@example.com",
        first_name="Bob",
        last_name="Smith",
        full_name="Bob Smith",
        user_id=str(other.id),
    )

    response = client.delete(f"/field-attendance/{created['id']}", headers=other_headers)

    assert response.status_code == 403
