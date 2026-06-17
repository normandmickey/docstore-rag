from dataclasses import dataclass, field
from typing import Any


@dataclass
class SupportReplyResult:
    mode: str
    handled: bool
    should_reply: bool
    reply_text: str

    confidence: float = 0.0
    sources: list[dict[str, Any]] = field(default_factory=list)

    retrieval_metadata: dict[str, Any] = field(default_factory=dict)
    capability_metadata: dict[str, Any] = field(default_factory=dict)

    should_handoff: bool = False
    handoff_reason: str = ''

    def as_metadata(self) -> dict[str, Any]:
        return {
            'mode': self.mode,
            'handled': self.handled,
            'should_reply': self.should_reply,
            'confidence': self.confidence,
            'sources': self.sources,
            'retrieval_metadata': self.retrieval_metadata,
            'capability_metadata': self.capability_metadata,
            'should_handoff': self.should_handoff,
            'handoff_reason': self.handoff_reason,
        }
