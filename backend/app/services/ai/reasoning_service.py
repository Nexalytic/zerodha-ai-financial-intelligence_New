from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger, sanitize_log_message
from app.schemas.ai_reasoning import (
    AIInsightReport,
    PortfolioEvidenceBundle,
    ReviewStatus,
)
from app.services.ai.evidence_assembler import EvidenceAssemblerService
from app.services.ai.grounding_validator import ClaimGroundingValidator
from app.services.ai.providers.base import BaseAIProvider
from app.services.ai.providers.demo_provider import DeterministicDemoProvider
from app.services.market_data_service import MarketDataService
from app.services.news_service import NewsService


def resolve_ai_provider(settings_override: Optional[Any] = None) -> BaseAIProvider:
    """
    Resolves the active AI reasoning provider based on application configuration.
    Strictly honors zero-cost and safety policies:
    - If USE_MOCK_DATA is True or AI_PROVIDER is 'demo', DeterministicDemoProvider is used.
    - Only when USE_MOCK_DATA is False and AI_PROVIDER is 'groq' is GroqAIProvider selected.
    - An API key's mere presence never activates Groq automatically.
    """
    from app.core import config as config_module
    from app.core.config import settings

    cfg = settings_override or getattr(config_module, "settings", settings)
    if cfg.USE_MOCK_DATA:
        return DeterministicDemoProvider()

    provider_name = (cfg.AI_PROVIDER or "demo").strip().lower()
    if provider_name == "groq":
        from app.services.ai.providers.groq_provider import GroqAIProvider

        return GroqAIProvider(
            api_key=cfg.GROQ_API_KEY,
            model=cfg.GROQ_MODEL,
            base_url=cfg.GROQ_BASE_URL,
        )

    return DeterministicDemoProvider()


class AIReasoningError(Exception):
    """Base exception for AI reasoning and orchestration errors."""
    def __init__(self, message: str, code: str = "AI_REASONING_ERROR"):
        super().__init__(message)
        self.code = code
        self.message = message


class AIProviderError(AIReasoningError):
    """Raised when an AI reasoning provider fails during inference."""
    def __init__(self, message: str = "AI reasoning provider failed to generate insights."):
        super().__init__(message=message, code="AI_PROVIDER_ERROR")


class AIMalformedOutputError(AIReasoningError):
    """Raised when an AI reasoning provider produces invalid or unparseable output."""
    def __init__(self, message: str = "AI reasoning provider produced invalid report structure."):
        super().__init__(message=message, code="AI_MALFORMED_OUTPUT")


class AIReasoningService:
    """
    Orchestration service for evidence-grounded AI portfolio financial intelligence.
    Orchestration sequence:
    1. Assemble trustworthy portfolio evidence (valuations, completeness, market data, news).
    2. Invoke configured reasoning provider abstraction (default: DeterministicDemoProvider).
    3. Validate generated insights against evidence using ClaimGroundingValidator.
    4. Enforce grounding and review status invariants.
    5. Return typed, verified AIInsightReport.
    """

    def __init__(
        self,
        session: AsyncSession,
        provider: Optional[BaseAIProvider] = None,
        evidence_assembler: Optional[EvidenceAssemblerService] = None,
        grounding_validator: Optional[ClaimGroundingValidator] = None,
        market_data_service: Optional[MarketDataService] = None,
        news_service: Optional[NewsService] = None,
    ):
        self.session = session
        self.provider = provider or resolve_ai_provider()
        self.evidence_assembler = evidence_assembler or EvidenceAssemblerService(
            session=session,
            market_data_service=market_data_service,
            news_service=news_service,
        )
        self.grounding_validator = grounding_validator or ClaimGroundingValidator()


    async def generate_portfolio_insights(
        self,
        portfolio_id: str,
        include_news: bool = True,
        news_limit: int = 10,
        provider_override: Optional[str] = None,
    ) -> Optional[AIInsightReport]:
        """
        Executes end-to-end evidence assembly, AI inference, and claim grounding verification.
        Returns None if portfolio does not exist.
        Raises AIReasoningError on provider failure or malformed output.
        """
        # Step 1: Assemble evidence bundle
        evidence = await self.evidence_assembler.assemble_portfolio_evidence(
            portfolio_id=portfolio_id,
            include_news=include_news,
            news_limit=news_limit,
        )
        if evidence is None:
            return None

        # Step 2: Resolve provider
        active_provider = self._resolve_provider(provider_override)

        # Step 3: Invoke reasoning provider
        try:
            raw_report = await active_provider.generate_insights(evidence)
        except AIReasoningError:
            raise
        except Exception as exc:
            sanitized_exc = sanitize_log_message(str(exc))
            logger.error(
                "AI provider '%s' raised an unexpected error for portfolio %s: %s",
                getattr(active_provider, "PROVIDER_NAME", "UNKNOWN"),
                portfolio_id,
                sanitized_exc,
            )
            raise AIProviderError("AI reasoning provider failed to generate insights.") from None

        # Step 4: Validate output format
        if not isinstance(raw_report, AIInsightReport):
            try:
                raw_report = AIInsightReport.model_validate(raw_report)
            except Exception as exc:
                logger.error(
                    "AI provider produced malformed output for portfolio %s: %s",
                    portfolio_id,
                    exc,
                    exc_info=True,
                )
                raise AIMalformedOutputError("AI reasoning provider produced invalid report structure.") from None

        # Step 5: Claim Grounding & Verification
        try:
            validated_report = self.grounding_validator.validate_report(raw_report, evidence)
        except Exception as exc:
            logger.error(
                "Claim grounding validation failed unexpectedly for portfolio %s: %s",
                portfolio_id,
                exc,
                exc_info=True,
            )
            raise AIReasoningError("Claim grounding validation execution failed.") from None

        logger.info(
            "Successfully completed AI reasoning pipeline for portfolio %s (status=%s, provider=%s)",
            portfolio_id,
            validated_report.review_status.value,
            validated_report.provider_name,
        )

        return validated_report

    def _resolve_provider(self, provider_override: Optional[str]) -> BaseAIProvider:
        """Resolves active reasoning provider based on configuration and override."""
        if not provider_override:
            return self.provider

        cleaned_override = provider_override.strip().upper()

        if cleaned_override in ["DETERMINISTIC_DEMO_REASONER", "DEMO"]:
            return DeterministicDemoProvider()

        live_providers = {"GROQ"}
        if cleaned_override in live_providers:
            from app.core import config as config_module
            from app.core.config import settings

            cfg = getattr(config_module, "settings", settings)
            if cfg.USE_MOCK_DATA:
                raise ValueError(
                    f"Live AI provider '{cleaned_override}' cannot be selected while USE_MOCK_DATA is true."
                )

            if cleaned_override == "GROQ":
                from app.services.ai.providers.groq_provider import GroqAIProvider

                return GroqAIProvider(
                    api_key=cfg.GROQ_API_KEY,
                    model=cfg.GROQ_MODEL,
                    base_url=cfg.GROQ_BASE_URL,
                )

        default_name = getattr(self.provider, "PROVIDER_NAME", "DETERMINISTIC_DEMO_REASONER").upper()
        if cleaned_override == default_name:
            return self.provider

        raise ValueError(
            f"Unsupported AI reasoning provider '{provider_override}'. "
            f"Available providers: ['DETERMINISTIC_DEMO_REASONER', 'GROQ']."
        )

