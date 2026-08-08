import uuid
from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal

from eop_api.models.payroll_statutory_parameter import PayrollStatutoryParameter
from eop_api.repositories.payroll_statutory_parameter import PayrollStatutoryParameterRepository
from eop_api.schemas.payroll_statutory_parameter import (
    PayrollStatutoryParameterCreate,
    PayrollStatutoryParameterUpdate,
)
from eop_api.services.effective_dating_evaluator import EffectiveDatingEvaluator
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class OverlappingStatutoryParameterPeriodError(Exception):
    """Raised when a new `PayrollStatutoryParameter` row's effective period
    overlaps an existing row for the same `key` (mirrors Compensation's
    O1)."""


class MissingStatutoryParameterError(Exception):
    """Raised when no `PayrollStatutoryParameter` is effective for a given
    `key`/date. A deliberate fail-loud default (`implementation-plan.md`
    §7): a payroll calculation must not silently proceed with an absent
    rate (e.g. as if tax were 0%) -- the parameter must be explicitly
    configured first, consistent with D2/E4 (statutory rules are
    configurable *data*, not an implicit default)."""


class PayrollStatutoryParameterService:
    """Business logic for `PayrollStatutoryParameter`. Owns the transaction
    boundary via a UoW.

    Implements D2/E4: statutory and payroll-operational parameters as
    configurable, effective-dated data, read by key -- never a generic
    rule/expression engine. Mirrors `CompensationService`'s overlap-check
    shape, scoped by `key` instead of `employee_id`; no correction concept
    exists for parameters (a superseding value is just a new row with a
    later `effective_from`, the same as any other effective-dated
    capacity), so there is no `corrects_id` here.

    Returned entities are expunged from the unit-of-work's session before
    it closes, mirroring every other service in this repository.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory
        self._evaluator = EffectiveDatingEvaluator()

    async def create(self, data: PayrollStatutoryParameterCreate) -> PayrollStatutoryParameter:
        async with self._uow_factory() as uow:
            repo = PayrollStatutoryParameterRepository(uow.session)

            overlapping = await repo.find_overlapping_periods(
                data.key, data.effective_from, data.effective_to
            )
            if overlapping:
                raise OverlappingStatutoryParameterPeriodError(
                    f"Effective period for key {data.key!r} overlaps an existing period"
                )

            parameter = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(parameter)
            return parameter

    async def get(self, parameter_id: uuid.UUID) -> PayrollStatutoryParameter | None:
        async with self._uow_factory() as uow:
            repo = PayrollStatutoryParameterRepository(uow.session)
            parameter = await repo.get(parameter_id)
            if parameter is not None:
                uow.session.expunge(parameter)
            return parameter

    async def list(self) -> Sequence[PayrollStatutoryParameter]:
        async with self._uow_factory() as uow:
            repo = PayrollStatutoryParameterRepository(uow.session)
            parameters = await repo.list()
            uow.session.expunge_all()
            return parameters

    async def update(
        self, parameter_id: uuid.UUID, data: PayrollStatutoryParameterUpdate
    ) -> PayrollStatutoryParameter | None:
        async with self._uow_factory() as uow:
            repo = PayrollStatutoryParameterRepository(uow.session)
            parameter = await repo.get(parameter_id)
            if parameter is None:
                return None

            values = data.model_dump(exclude_unset=True)
            updated = await repo.update(parameter_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def get_value(self, key: str, as_of_date: date) -> Decimal:
        """The configured value for `key` effective as of `as_of_date`.

        Raises `MissingStatutoryParameterError` if none is configured --
        never silently substitutes a default. Raises
        `AmbiguousEffectiveStateError` (propagated from
        `EffectiveDatingEvaluator.resolve`) if more than one row is
        effective as of `as_of_date` (genuine configuration ambiguity,
        never silently resolved -- same policy as Compensation).
        """
        async with self._uow_factory() as uow:
            repo = PayrollStatutoryParameterRepository(uow.session)
            candidates = await repo.list_effective_as_of(key, as_of_date)
            parameter = self._evaluator.resolve(list(candidates), as_of_date)
            if parameter is None:
                raise MissingStatutoryParameterError(
                    f"No PayrollStatutoryParameter configured for key {key!r} as of {as_of_date}"
                )
            return parameter.value

    async def get_value_or_default(self, key: str, as_of_date: date, default: Decimal) -> Decimal:
        """`get_value`, but returns `default` instead of raising when `key`
        is not configured.

        Reserved for parameters where an unconfigured value has a safe,
        well-defined meaning (e.g. `STATUTORY_TAX_RATE` unconfigured means
        "no tax applies yet", preserving Iteration 1-3's existing gross =
        net behavior with zero required configuration --
        `StatutoryTaxCalculator`). Parameters where a missing value could
        silently shortchange a real, already-occurred event (e.g. an
        overtime rate, once overtime hours actually exist) must keep using
        `get_value` and fail loud instead.
        """
        try:
            return await self.get_value(key, as_of_date)
        except MissingStatutoryParameterError:
            return default
