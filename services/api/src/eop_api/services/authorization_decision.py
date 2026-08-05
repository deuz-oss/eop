from dataclasses import dataclass


@dataclass(frozen=True)
class AuthorizationDecision:
    """Immutable outcome of an authorization evaluation (`ADR-007`).

    Not an exception: consumers decide how a denied decision should be
    represented (HTTP, domain exception, workflow outcome). Carries no
    workflow, persistence, or transport behavior.
    """

    allowed: bool
    reason: str | None = None
