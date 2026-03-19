"""Custom agent output schemas for provider-specific JSON cleanup."""
from __future__ import annotations

from typing import Any

import structlog
from agents.agent_output import AgentOutputSchema, AgentOutputSchemaBase
from agents.exceptions import ModelBehaviorError

from app.core.llm.output_cleaners import build_json_candidates

logger = structlog.get_logger()


class CleaningOutputSchema(AgentOutputSchemaBase):
    """Wrap AgentOutputSchema with lightweight pre-validation cleanup."""

    def __init__(self, output_type: type[Any], *, strict_json_schema: bool = True) -> None:
        self._schema = AgentOutputSchema(
            output_type,
            strict_json_schema=strict_json_schema,
        )

    def is_plain_text(self) -> bool:
        return self._schema.is_plain_text()

    def name(self) -> str:
        return self._schema.name()

    def json_schema(self) -> dict[str, Any]:
        return self._schema.json_schema()

    def is_strict_json_schema(self) -> bool:
        return self._schema.is_strict_json_schema()

    def validate_json(self, json_str: str) -> Any:
        last_error: ModelBehaviorError | None = None
        candidates = build_json_candidates(json_str)
        for candidate in candidates:
            try:
                result = self._schema.validate_json(candidate.text)
                logger.info(
                    "llm_output_schema_validated",
                    schema_name=self.name(),
                    candidate_source=candidate.source,
                    recovered=(candidate.source != "original"),
                    candidate_count=len(candidates),
                )
                return result
            except ModelBehaviorError as exc:
                last_error = exc

        logger.warning(
            "llm_output_schema_validation_failed",
            schema_name=self.name(),
            candidate_count=len(candidates),
        )
        if last_error is not None:
            raise last_error
        raise ModelBehaviorError("Invalid JSON output")


def should_use_cleaning_schema(provider: str, output_type: type[Any] | None) -> bool:
    """Apply cleanup only to non-OpenAI structured outputs."""
    if output_type is None or output_type is str:
        return False
    return provider != "openai"
