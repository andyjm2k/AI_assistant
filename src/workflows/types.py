from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class WorkflowMessage:
    source: str
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"source": self.source, "content": self.content}


@dataclass(frozen=True)
class WorkflowAvailability:
    available: bool
    framework: str
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowRunResult:
    framework: str
    output: str
    messages: List[WorkflowMessage] = field(default_factory=list)
    summary: str = ""
    log_file: Optional[str] = None
    log_content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def response(self) -> str:
        return self.output

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "framework": self.framework,
            "output": self.output,
            "response": self.response,
            "messages": [message.to_dict() for message in self.messages],
            "message_count": self.message_count,
            "log_file": self.log_file,
            "log_content": self.log_content,
            "summary": self.summary or self.output,
            "metadata": dict(self.metadata),
        }
