from datetime import date
from typing import Protocol


class EffectiveDated(Protocol):
    effective_from: date
    effective_to: date | None


class AmbiguousEffectiveStateError(Exception):
    """Raised when more than one row in a candidate set is effective as of the
    same date.

    Generic to `EffectiveDatingEvaluator` -- domain-specific reasons why a
    caller's candidate set might legitimately contain more than one
    effective row (e.g. Compensation's correction-precedence policy) belong
    to that domain's own service layer, which is expected to resolve such
    cases *before* calling `resolve()` where its own policy allows it.
    `resolve()` itself never guesses; it raises.
    """


class EffectiveDatingEvaluator:
    """Resolves temporal validity for rows composed with `EffectiveDatingMixin`.

    `docs/architecture/capabilities/effective-dating/decision.md` §12:
    stateless evaluator, same shape as `AuthorizationEvaluator` -- no
    persistence, no repository access, no business policy. It only
    interprets `effective_from`/`effective_to` already present on a row.
    It does not decide overlap permission or correction behavior -- both
    are Compensation-domain policy (`compensation/decision.md` §19) -- and
    must not be extended to know about them. A domain-specific reason for
    multiple simultaneously-effective rows to exist (e.g. a correction
    overlapping the row it corrects) is resolved by the caller's own
    domain logic *before* calling `resolve()`, never inside this class.
    """

    def is_effective(self, row: EffectiveDated, as_of_date: date) -> bool:
        if row.effective_from > as_of_date:
            return False
        return row.effective_to is None or row.effective_to >= as_of_date

    def resolve[T: EffectiveDated](self, rows: list[T], as_of_date: date) -> T | None:
        """The row among `rows` effective as of `as_of_date`.

        No match: `None`. Exactly one match: that row. More than one
        match: raises `AmbiguousEffectiveStateError` -- never silently
        picks one by list order. Callers whose domain has a legitimate
        reason for multiple candidates to match (e.g. Compensation's
        correction-precedence rule) must reduce `rows` to at most the
        rows they consider genuinely resolvable before calling this.
        """
        matches = [row for row in rows if self.is_effective(row, as_of_date)]
        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]
        raise AmbiguousEffectiveStateError(
            f"{len(matches)} rows are effective as of {as_of_date}, expected at most one"
        )
