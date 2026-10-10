# AI Reasoning Endpoint & Architecture Documentation

## 1. Overview & Simulation Disclosure

The AI Reasoning Engine provides structured, evidence-grounded portfolio insights, key drivers, risk alerts, and confidence indicators.

> [!IMPORTANT]
> **Zero-Cost Simulation Disclosure**: All current AI reasoning outputs are generated via a local deterministic simulation provider (`DeterministicDemoProvider`). **No external LLMs or paid APIs are invoked**, ensuring an operating cost of ₹0 and deterministic reproducibility for testing and development. External model providers (such as Gemini, OpenAI, Claude, or local Ollama instances) can be plugged in using the abstract `BaseAIProvider` interface without modifying the core orchestrator or grounding verification engine.

---

## 2. Endpoint Contract

### Route: `POST /api/v1/portfolios/{portfolio_id}/ai-insights`

- **HTTP Method**: `POST`
- **Path Parameter**: `portfolio_id` (string, UUID format)
- **Request Headers**: `Content-Type: application/json`
- **Request Body** (`GenerateAIInsightsRequest`):
  ```json
  {
    "include_news": true,
    "news_limit": 10,
    "provider_override": null
  }
  ```
  *Note: Extra attributes in the request payload are strictly forbidden (`extra="forbid"`) and return HTTP 422.*

### Response Schema: `AIInsightReport` (HTTP 200)

```json
{
  "report_id": "936d5e68-07e5-47e2-8238-66ec965852ef",
  "portfolio_id": "4b6ecf91-ba4d-45db-9962-d4b9bdfbcf1b",
  "generated_at": "2026-10-10T05:03:00Z",
  "model_name": "deterministic-demo-engine-v1",
  "executive_summary": "Portfolio summary with grounded quantitative metrics...",
  "key_drivers": [
    {
      "driver_id": "drv-001",
      "category": "CONCENTRATION",
      "description": "Portfolio breadth is concentrated in RELIANCE with top holding weight 28.5%.",
      "impact_direction": "NEGATIVE",
      "supporting_evidence_ids": ["hold-001", "risk-metrics"]
    }
  ],
  "risk_alerts": [
    {
      "alert_id": "alt-001",
      "severity": "MEDIUM",
      "title": "Single Stock Concentration",
      "message": "Top holding RELIANCE exceeds prudent diversification threshold of 25%.",
      "recommended_action": "Evaluate rebalancing into broader large-cap assets.",
      "supporting_evidence_ids": ["hold-001"]
    }
  ],
  "insight_cards": [
    {
      "card_id": "crd-001",
      "headline": "Technology Sector Weight Allocation",
      "narrative": "Technology sector comprises 35.0% of total portfolio value across 2 holdings.",
      "category": "DIVERSIFICATION",
      "supporting_evidence_ids": ["sector-allocation", "hold-001", "hold-002"]
    }
  ],
  "uncertainty_and_gaps": [
    "Simulated intelligence output based on historical and mock data feeds."
  ],
  "review_status": "VERIFIED",
  "grounding_report": {
    "is_acceptable": true,
    "unsupported_claims_count": 0,
    "unverified_metrics_count": 0,
    "temporal_inconsistencies_count": 0,
    "warnings": [],
    "findings": []
  }
}
```

### Error Responses (Standardized JSON Envelopes)

All non-200 responses follow the uniform application error schema:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Safe human-readable message",
    "details": null
  }
}
```

- **HTTP 404 (Not Found)**:
  - Code: `PORTFOLIO_NOT_FOUND`
  - Message: `Portfolio <id> not found`
- **HTTP 422 (Unprocessable Entity)**:
  - Code: `VALIDATION_ERROR`
  - Returns field-level validation errors (e.g. unknown fields, invalid parameter types or ranges).
- **HTTP 502 (Bad Gateway / Downstream Provider Error)**:
  - Code: `AI_PROVIDER_ERROR` or `AI_MALFORMED_OUTPUT`
  - Message: Safe sanitized description (e.g., `AI reasoning provider failed to generate insights.` or `AI reasoning provider returned malformed or incomplete output.`).
  - Sensitive details and exception traces are stripped and securely logged to internal backend logs.

---

## 3. Orchestration Flow

```text
 Client POST /api/v1/portfolios/{id}/ai-insights
                     │
                     ▼
          [AIReasoningService]
                     │
 1. Assemble Evidence via [EvidenceAssemblerService]
    - Portfolio & Holdings DB lookup
    - Market Data quotes & freshness validation
    - Risk & Analytics calculation
    - Optional financial news bundling
                     │
                     ▼
 2. Invoke Reasoning Provider via [BaseAIProvider]
    - Resolves provider (defaults to DeterministicDemoProvider)
    - Validates output structure against AIInsightReport contract
                     │
                     ▼
 3. Validate Grounding via [ClaimGroundingValidator]
    - Verifies numeric claims against evidence bundle
    - Validates symbol mentions against holdings
    - Checks temporal consistency & data gaps
    - Calculates review_status (VERIFIED, FLAGGED_WITH_WARNINGS, or REJECTED)
                     │
                     ▼
 4. Return Final Verified Report [AIInsightReport]
```

---

## 4. Grounding Review Status Interpretation

Clients and UI layers must interpret the `review_status` as follows:

| Status | Interpretation | UI Recommended Presentation |
|---|---|---|
| `VERIFIED` | All assertions, symbols, and metrics strictly match the factual evidence bundle. | Display insight cards with green badge ("Verified Analysis"). |
| `FLAGGED_WITH_WARNINGS` | The insights are acceptable but contain minor non-critical warnings (e.g. partial unpriced holdings or missing news context). | Display insights with amber alert indicator and highlight warnings in the grounding accordion. |
| `REJECTED` | Grounding validator detected hallucinated symbols, mismatched metric percentages, or unacknowledged data omissions. | Display prominent red disclaimer indicating claims failed factual verification. |

---

## 5. Extensibility: Plugging in External Providers

To connect a new model provider:

1. Subclass `BaseAIProvider` from `backend.app.services.ai.providers.base`:
   ```python
   from backend.app.services.ai.providers.base import BaseAIProvider
   from backend.app.schemas.ai_reasoning import PortfolioEvidenceBundle, AIInsightReport

   class ProductionGeminiProvider(BaseAIProvider):
       @property
       def provider_name(self) -> str:
           return "gemini-2.0-flash"

       async def generate_insights(self, evidence: PortfolioEvidenceBundle) -> AIInsightReport:
           # 1. Format prompt with serialized evidence
           # 2. Call SDK with structured output enforcement
           # 3. Return typed AIInsightReport
           ...
   ```
2. Register the provider instance in `AIReasoningService` provider registry:
   ```python
   service = AIReasoningService(
       assembler=assembler,
       validator=validator,
       providers={"gemini": ProductionGeminiProvider(), "demo": DeterministicDemoProvider()},
       default_provider="gemini",
   )
   ```
3. The claim grounding engine automatically evaluates the output before it ever reaches the client, guaranteeing that hallucinations from external models are caught and flagged.

---

## 6. Local Testing Instructions

### Run Unit and Integration Tests for AI Reasoning Service
```powershell
backend\.venv\Scripts\python -m pytest backend/tests/test_ai_reasoning_service.py -v
```

### Run Entire AI Reasoning Test Suite (Substeps 6.1 – 6.4)
```powershell
backend\.venv\Scripts\python -m pytest backend/tests/test_ai_schemas_and_demo_provider.py backend/tests/test_ai_evidence_assembler.py backend/tests/test_ai_grounding_validator.py backend/tests/test_ai_reasoning_service.py -v
```

### Run Full Backend Regression Suite
```powershell
backend\.venv\Scripts\python -m pytest backend/tests -v
```

### Test Endpoint with cURL / HTTPie (with FastAPI dev server running)
```powershell
curl -X POST "http://localhost:8000/api/v1/portfolios/<PORTFOLIO_ID>/ai-insights" \
     -H "Content-Type: application/json" \
     -d '{"include_news": true, "news_limit": 5}'
```
