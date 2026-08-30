import abc
from typing import Dict, Any, Type
from pydantic import BaseModel
import json

from config.settings import get_settings
from services.investigation.schema import InvestigationResult
from database.models.investigation import RootCauseEnum

class ILLMProvider(abc.ABC):
    @abc.abstractmethod
    async def generate_structured_investigation(self, prompt: str, context: Dict[str, Any], schema: Type[BaseModel]) -> BaseModel:
        """
        Takes a prompt, a JSON-serializable context, and a Pydantic schema.
        Returns an instance of the schema parsed from the LLM output.
        """
        pass

class MockLLMProvider(ILLMProvider):
    """
    A mock provider for testing and fallback when no actual LLM is configured.
    """
    async def generate_structured_investigation(self, prompt: str, context: Dict[str, Any], schema: Type[BaseModel]) -> BaseModel:
        # For mock testing, we just inspect the context and return a dummy valid object.
        # This allows us to write deterministic integration tests.
        
        # Simple heuristic for dummy response:
        discrepancy = context.get("discrepancy", {})
        rule_code = discrepancy.get("rule_code", "")
        
        rc = RootCauseEnum.UNKNOWN
        if "FEE_MISMATCH" in rule_code:
            rc = RootCauseEnum.UNEXPECTED_FEE
        elif "TIMING" in rule_code:
            rc = RootCauseEnum.TIMING_DELAY
        elif "CURRENCY" in rule_code:
            rc = RootCauseEnum.CURRENCY_FX_RATE_MISMATCH
        
        # Create dummy claim from context if possible
        entity_id = discrepancy.get("id", "dummy-id")
        
        dummy_result = InvestigationResult(
            summary="This is a deterministic mock fallback summary.",
            root_cause_category=rc,
            ai_confidence=0.9,
            claims=[
                {
                    "claim": "Dummy evidence claim",
                    "evidence": [
                        {
                            "entity_id": entity_id,
                            "entity_type": "Discrepancy",
                            "field": "rule_code",
                            "value": rule_code,
                            "currency": None
                        }
                    ]
                }
            ],
            recommendations=["Mock recommendation action"]
        )
        return dummy_result

def get_llm_provider() -> ILLMProvider:
    settings = get_settings()
    if settings.LLM_PROVIDER.lower() == "mock":
        return MockLLMProvider()
    
    # In the future, we can add OpenAIProvider, GeminiProvider, etc.
    # For now, default to mock if key is missing or explicitly mock.
    if not settings.LLM_API_KEY:
        return MockLLMProvider()
        
    return MockLLMProvider()
