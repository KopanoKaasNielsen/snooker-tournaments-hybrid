"""Provider evidence boundary only. No external integration or successful default."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class VerificationUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class VerificationRequest:
    operation_id: str
    wallet_id: str
    kind: str
    amount_minor: int
    currency: str


@dataclass(frozen=True)
class VerifiedEvidence:
    operation_id: str
    wallet_id: str
    kind: str
    amount_minor: int
    currency: str
    provider: str
    event_digest: str
    payload_digest: str
    checked_at: datetime


class PaymentEvidenceVerifier(Protocol):
    provider: str

    def verify(self, request: VerificationRequest, reference: str) -> VerifiedEvidence:
        """Validate authentic evidence and binding; never trust a client status flag."""
        ...


class UnavailablePaymentVerifier:
    provider = "unconfigured"

    def verify(self, request: VerificationRequest, reference: str) -> VerifiedEvidence:
        raise VerificationUnavailable(
            "No approved payment evidence verifier is configured"
        )
