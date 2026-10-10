# Zerodha AI Financial Intelligence — Governed Model Context Protocol (MCP) Server

This package implements a typed, governed [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server providing safe, read-only financial data and quantitative analysis tools for AI agent workflows (Antigravity, Claude Desktop, Cursor, or custom LLM orchestrators).

The server is built using the official Python MCP SDK (`mcp==1.12.4`, `FastMCP`) and operates primarily over the standard input/output (`stdio`) JSON-RPC 2.0 transport.

---

## 1. Quick Start & Execution

### Starting the Server via Stdio Transport
From the project workspace root:
```powershell
backend/.venv/Scripts/python -m app.mcp.server
```
Or from the `backend/` directory:
```bash
python -m app.mcp.server
```

> **Important Transport Rule:** `stdout` is strictly reserved for JSON-RPC 2.0 protocol frames. All diagnostic messages, operational logs, and structured audit events are directed exclusively to `stderr` to prevent stream corruption.

---

## 2. MCP Client Configuration

To integrate with an MCP-compatible host (e.g., Claude Desktop, Antigravity, or Cursor), add the following server configuration block to your client settings file (e.g., `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "zerodha-intelligence": {
      "command": "C:\\Users\\Acer\\Projects\\Zerodha-AI-Intelligence-New\\backend\\.venv\\Scripts\\python.exe",
      "args": ["-m", "app.mcp.server"],
      "cwd": "C:\\Users\\Acer\\Projects\\Zerodha-AI-Intelligence-New\\backend"
    }
  }
}
```

---

## 3. Governed Read-Only Tool Contracts

Exactly **eight** approved, read-only tools are registered on the server. All tools carry explicit read-only annotations (`readOnlyHint=True, destructiveHint=False, idempotentHint=True`) and strictly enforce parameter validation via Pydantic (`extra="forbid"`).

### 1. `get_portfolio`
- **Description:** Retrieve details and holdings for a single portfolio by ID.
- **Arguments:**
  - `portfolio_id` (*string, required*): 1–64 characters.
- **Output:** `PortfolioDetailResponse` JSON (ID, name, description, sample flag, timestamps, holdings list).
- **Error Behavior:** Returns `PORTFOLIO_NOT_FOUND` if the portfolio ID does not exist in the database.

### 2. `list_portfolios`
- **Description:** List portfolio summaries with optional sample/demo filtering.
- **Arguments:**
  - `is_sample` (*boolean, optional*): Filter for demo (`true`) or custom (`false`) portfolios. Omit for all portfolios.
- **Output:** Array of `PortfolioResponse` objects with `holdings_count`.

### 3. `get_market_snapshot`
- **Description:** Retrieve market quotes for a bounded list of symbols, preserving simulation and cache freshness flags.
- **Arguments:**
  - `symbols` (*list of strings, required*): 1 to 50 valid NSE/BSE ticker symbols.
  - `exchange` (*string, optional*): `"NSE"` (default) or `"BSE"`.
- **Output:** `BatchQuotesResponse` (quotes dictionary, cache hit/miss counts, timestamps).
- **Error Behavior:** Invalid symbols or empty lists trigger `VALIDATION_ERROR`. Provider failures fall back gracefully to stale cache (`is_stale=True`) or explicit `QuoteStatus.ERROR` with `current_price=None`.

### 4. `search_news`
- **Description:** Retrieve financial news for target symbols or general market headlines.
- **Arguments:**
  - `symbols` (*list of strings, optional*): Up to 20 ticker symbols. If omitted, returns general market news.
  - `limit` (*integer, optional*): Number of articles to return (1–50, default: 10).
- **Output:** `NewsResponse` (articles array, count, simulation flags, and regulatory disclaimer).

### 5. `calculate_portfolio_metrics`
- **Description:** Calculate comprehensive portfolio metrics: valuation, allocation, concentration, sector exposure, completeness, and historical risk status.
- **Arguments:**
  - `portfolio_id` (*string, required*): Portfolio identifier.
- **Output:** `PortfolioAnalyticsResponse` (market valuation, priced cost basis, unrealized P/L, sector exposure, HHI concentration, and historical risk availability).
- **Error Behavior:** Returns `PORTFOLIO_NOT_FOUND` if the portfolio does not exist.

### 6. `score_portfolio_risk`
- **Description:** Return portfolio risk assessment across 4 deterministic dimensions with component scores and supporting insights.
- **Arguments:**
  - `portfolio_id` (*string, required*): Portfolio identifier.
- **Output:** `PortfolioRiskScoreResponse`:
  - `risk_assessment`: Composite score (0–100), risk tier (`LOW`, `MODERATE`, `HIGH`, `VERY_HIGH`), component scores (single-stock 35%, sector 25%, breadth 20%, data quality 20%), evidence metrics, and methodology scope.
  - `insights`: List of explainable rule-based insights and risk flags.

### 7. `get_evidence_bundle`
- **Description:** Compose portfolio details, market quotes, analytics, risk assessment, and insights into a unified bounded evidence bundle for AI reasoning.
- **Arguments:**
  - `portfolio_id` (*string, required*): Portfolio identifier.
- **Output:** `EvidenceBundle`:
  - `portfolio`: Master record and holdings.
  - `market_snapshot`: Quotes for all portfolio symbols.
  - `analytics`: Financial valuation and sector breakdown.
  - `risk_assessment`: 4-component risk assessment and scores.
  - `insights`: Explainable rule-based insights.
  - `metadata`: Provenance, completeness status (`COMPLETE`, `PARTIAL`, `EMPTY`, `UNPRICED`), `has_missing_prices`, `has_stale_data`, and educational disclaimers.

### 8. `generate_portfolio_ai_insights`
- **Description:** Generate evidence-grounded AI insights, key drivers, risk alerts, and claim verification status for a portfolio.
- **Arguments:**
  - `portfolio_id` (*string, required*): Portfolio identifier (1–64 characters).
  - `include_news` (*boolean, optional, default: true*): Whether to include recent news articles in the factual evidence bundle.
  - `news_limit` (*integer, optional, default: 10*): Maximum number of news articles to include (bounded 1–20).
- **Output:** `AIInsightReport` JSON containing:
  - `executive_summary`: Quantitative narrative grounded strictly in factual portfolio evidence.
  - `key_drivers`: Array of evidence-backed drivers with metric paths and values (`EvidenceKeyDriver`).
  - `risk_alerts`: Array of structural concentration and completeness alerts (`AIRiskAlert`).
  - `confidence`: Heuristic confidence score with explicit discounts and calibration limitation notice.
  - `review_cards`: Modular inspection cards with cited metrics and symbols (`ReviewableInsightCard`).
  - `uncertainty_and_gaps`: Explicit disclosures of missing prices or data gaps.
  - `review_status`: Claim veracity assessment: `VERIFIED`, `FLAGGED_WITH_WARNINGS`, or `REJECTED`.
  - `grounding_report`: Programmatic claim verification audit summary (`passed_count`, `flagged_count`, `rejected_count`, `findings`, `is_acceptable`).
- **Grounding Invariant:** A report marked `REJECTED` is never presented as `VERIFIED`. Discrepancies and warnings remain fully visible.
- **Example Call (JSON-RPC):**
  ```json
  {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "generate_portfolio_ai_insights",
      "arguments": {
        "portfolio_id": "00000000-0000-0000-0000-000000000001",
        "include_news": false
      }
    },
    "id": 1
  }
  ```

---

## 4. Governance, Permissions & Security

1. **Strict Tool Allowlisting:**
   - Only the 8 approved tools are registered.
   - Any attempt to invoke unapproved tools (e.g., `delete_portfolio`, `execute_order`, `buy_stock`, `update_holding`, `run_shell`) is immediately rejected with an explicit `UNAUTHORIZED_TOOL` error and audited.
2. **Read-Only Invariant:**
   - The MCP server has **no capabilities** to create portfolios, modify holdings, execute trades, update configurations, access the filesystem, or execute shell commands.
3. **No Hidden Authentication:**
   - The application does not claim user authentication exists. The platform is currently single-tenant and educational. Security is enforced through strict tool allowlisting, argument schema validation (`extra="forbid"`), and read-only database transactions.
4. **Prompt Injection Defense:**
   - External news content is treated strictly as untrusted data, never as prompt instructions.
   - Prompt text cannot select or invoke unapproved tools because tool dispatching is governed by hardcoded Python allowlists and strict Pydantic argument models.

---

## 5. Structured Audit Logging

Every tool execution emits a structured JSON audit log entry to `sys.stderr` and records it in an in-memory buffer (`deque(maxlen=1000)`):

### Log Entry Fields:
- `timestamp`: UTC ISO-8601 string.
- `correlation_id`: Unique UUID generated per tool invocation.
- `tool_name`: Name of the executed tool.
- `arguments_sanitized`: Sanitized argument map.
- `duration_ms`: Latency in milliseconds.
- `status`: `"SUCCESS"` or `"ERROR"`.
- `error_code`: Machine-readable category (`VALIDATION_ERROR`, `PORTFOLIO_NOT_FOUND`, `UNAUTHORIZED_TOOL`, `PROVIDER_ERROR`, `INTERNAL_ERROR`).
- `error_message`: Sanitized error summary (never exposing internal stack traces).

### Redaction & Sanitization Rules:
- **Key-based Redaction:** Keys matching sensitive patterns (`key`, `token`, `secret`, `password`, `auth`, `api_key`, `credential`, `cookie`) are masked with `"[REDACTED]"`.
- **String Pattern Redaction (SEC-01):** Embedded credential patterns inside arbitrary string values (e.g. `Bearer <token>`, `api_key=<val>`, `password=<val>`) are programmatically detected via regex and masked with `"[REDACTED]"`.
- **Unexpected Error Sanitization (SEC-02):** Unhandled or raw Python/DB exceptions are never propagated to callers or recorded in audit error messages; they are caught and mapped to safe, generic internal errors (`"An unexpected internal error occurred."`), while full traces are emitted exclusively to backend stderr logs.
- **Large Collections:** Large collections (e.g. holding lists) are truncated to prevent leaking sensitive financial records into logs.

---

## 6. Limitations, Security Scope & Provenance Disclaimers

- **Zero-Cost Simulation Engine:** AI reasoning is currently executed via a local, deterministic demonstration heuristic (`DeterministicDemoProvider`). No external LLM APIs (OpenAI, Anthropic, Gemini) are contacted, ensuring ₹0 operating cost and offline reproducibility.
- **Simulated Market Data & News:** Quotes and news articles are generated by simulated providers for educational demonstration.
- **Historical Risk Data:** Historical price series are currently simulated/mocked; metrics explicitly report `data_status="INSUFFICIENT_HISTORY"` rather than fabricating estimates.
- **Single-Tenant / Local Boundary:** The MCP server is designed for local stdio communication with agent hosts. There is no user authentication or multi-tenant isolation implemented in this layer.
- **Residual Secret Masking Limitation:** Regex-based sanitization reliably catches standard credential formats (`Bearer ...`, labeled API keys), but arbitrary high-entropy unlabeled tokens embedded in arbitrary strings cannot be detected with 100% certainty without semantic analysis.
- **Regulatory Notice:** All analytics, insights, and risk assessments are strictly for educational and demonstration purposes and do **not** constitute SEBI-registered investment advice.

---

## 7. Running the Tests

To run the governed MCP test suite (36 tests):
```powershell
backend/.venv/Scripts/python -m pytest backend/tests/test_mcp_tools.py -v
```

To run the complete backend regression test suite:
```powershell
backend/.venv/Scripts/python -m pytest backend/tests -v
```
