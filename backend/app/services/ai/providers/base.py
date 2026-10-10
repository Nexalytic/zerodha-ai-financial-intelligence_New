from abc import ABC, abstractmethod
import uuid
from typing import Optional

from app.schemas.ai_reasoning import AIInsightReport, PortfolioEvidenceBundle


class BaseAIProvider(ABC):
    """
    Abstract interface for AI reasoning and portfolio insight providers.
    Enforces strict typed contracts, audit metadata, and transparency flags.
    """

    PROVIDER_NAME: str = "BASE_AI_PROVIDER"
    MODEL_ID: str = "base-model"
    IS_SIMULATED: bool = True

    @abstractmethod
    async def generate_insights(self, evidence: PortfolioEvidenceBundle) -> AIInsightReport:
        """
        Generate grounded, reviewable AI insights from a structured portfolio evidence bundle.
        Must strictly derive conclusions from supplied evidence and reject/flag unsupported claims.
        """
        pass

    def generate_report_id(self, portfolio_id: str) -> str:
        """Helper generating a stable, structured report identifier."""
        suffix = uuid.uuid4().hex[:12]
        return f"rep-{portfolio_id[:8]}-{suffix}"
