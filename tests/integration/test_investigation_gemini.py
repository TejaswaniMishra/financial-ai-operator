import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import BaseModel

from config.settings import get_settings
from services.investigation.provider import GeminiLLMProvider, get_llm_provider, MockLLMProvider
from services.investigation.schema import InvestigationResult, RootCauseEnum

# Mock Pydantic schema for tests
class MockSchema(BaseModel):
    message: str

@pytest.fixture
def dummy_context():
    return {
        "discrepancy": {
            "id": "test-uuid",
            "rule_code": "TIMING",
            "expected_amount": "100.00",
            "actual_amount": "100.00",
            "difference_amount": "0.00",
            "currency": "USD"
        }
    }

def test_provider_factory_selection(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "LLM_API_KEY", "dummy-key")
    provider = get_llm_provider()
    assert isinstance(provider, GeminiLLMProvider)

def test_provider_factory_mock_fallback(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(settings, "LLM_API_KEY", "dummy-key")
    provider = get_llm_provider()
    assert isinstance(provider, MockLLMProvider)

def test_gemini_missing_api_key(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    provider = GeminiLLMProvider()
    assert provider.client is None

@pytest.mark.asyncio
async def test_gemini_missing_api_key_raises(monkeypatch, dummy_context):
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    provider = GeminiLLMProvider()
    with pytest.raises(ValueError, match="LLM_API_KEY is missing. Provider unavailable."):
        await provider.generate_structured_investigation("prompt", dummy_context, InvestigationResult)

@pytest.mark.asyncio
async def test_gemini_successful_mocked_response(monkeypatch, dummy_context):
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_API_KEY", "dummy-key")
    provider = GeminiLLMProvider()
    
    # Mock the aio.models.generate_content call
    mock_response = MagicMock()
    # Correct Pydantic JSON dump matching InvestigationResult
    mock_response.text = '{"summary": "Test", "root_cause_category": "UNKNOWN", "ai_confidence": 0.5, "claims": [], "recommendations": []}'
    
    mock_client = AsyncMock()
    mock_client.aio.models.generate_content.return_value = mock_response
    provider.client = mock_client
    
    result = await provider.generate_structured_investigation("prompt", dummy_context, InvestigationResult)
    assert isinstance(result, InvestigationResult)
    assert result.summary == "Test"
    assert result.root_cause_category == RootCauseEnum.UNKNOWN
    assert result.ai_confidence == 0.5

@pytest.mark.asyncio
async def test_gemini_malformed_response(monkeypatch, dummy_context):
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_API_KEY", "dummy-key")
    provider = GeminiLLMProvider()
    
    mock_response = MagicMock()
    mock_response.text = '{ "invalid_json": ' # Broken JSON
    
    mock_client = AsyncMock()
    mock_client.aio.models.generate_content.return_value = mock_response
    provider.client = mock_client
    
    with pytest.raises(Exception):
        await provider.generate_structured_investigation("prompt", dummy_context, InvestigationResult)

@pytest.mark.asyncio
async def test_gemini_schema_validation_failure(monkeypatch, dummy_context):
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_API_KEY", "dummy-key")
    provider = GeminiLLMProvider()
    
    mock_response = MagicMock()
    # Missing required fields for InvestigationResult
    mock_response.text = '{"wrong_schema_field": "Test"}'
    
    mock_client = AsyncMock()
    mock_client.aio.models.generate_content.return_value = mock_response
    provider.client = mock_client
    
    with pytest.raises(Exception): # Pydantic ValidationError
        await provider.generate_structured_investigation("prompt", dummy_context, InvestigationResult)

@pytest.mark.asyncio
async def test_gemini_empty_text_raises(monkeypatch, dummy_context):
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_API_KEY", "dummy-key")
    provider = GeminiLLMProvider()
    
    mock_response = MagicMock()
    mock_response.text = ""
    
    mock_client = AsyncMock()
    mock_client.aio.models.generate_content.return_value = mock_response
    provider.client = mock_client
    
    with pytest.raises(ValueError, match="Empty response from Gemini"):
        await provider.generate_structured_investigation("prompt", dummy_context, InvestigationResult)
