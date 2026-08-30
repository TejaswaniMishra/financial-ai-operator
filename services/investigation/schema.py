from typing import List, Optional, Any
from pydantic import BaseModel, Field

from database.models.investigation import RootCauseEnum

class EvidenceCitation(BaseModel):
    entity_id: str
    entity_type: str
    field: str
    value: Any
    currency: Optional[str] = None

class InvestigationClaim(BaseModel):
    claim: str
    evidence: List[EvidenceCitation]

class InvestigationResult(BaseModel):
    summary: str
    root_cause_category: RootCauseEnum
    ai_confidence: float = Field(..., ge=0.0, le=1.0)
    claims: List[InvestigationClaim]
    recommendations: List[str]
