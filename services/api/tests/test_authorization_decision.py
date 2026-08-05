import dataclasses

import pytest

from eop_api.services.authorization_decision import AuthorizationDecision


def test_allowed_decision_carries_no_reason_by_default():
    decision = AuthorizationDecision(allowed=True)

    assert decision.allowed is True
    assert decision.reason is None


def test_denied_decision_carries_a_reason():
    decision = AuthorizationDecision(allowed=False, reason="missing role")

    assert decision.allowed is False
    assert decision.reason == "missing role"


def test_decision_is_immutable():
    decision = AuthorizationDecision(allowed=True)

    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.allowed = False  # type: ignore[misc]
