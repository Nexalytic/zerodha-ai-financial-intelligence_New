# Zerodha: AI Financial Intelligence Platform

An AI-powered, evidence-grounded financial intelligence and portfolio analytics platform for Indian equity markets (NSE & BSE).

Built with a **strict ₹0 spend policy**, the platform operates completely offline by default using deterministic quantitative models, fixed reference market baselines, rule-based analytics, and local claim-grounding verification.

## 🚀 Live Demo & Project Walkthrough

- **Live Application:** [Launch Zerodha AI Financial Intelligence Platform](https://stirring-dusk-7f4ed6.netlify.app/)
- **Project Demonstration Video:** [Watch the 10–15 Minute Walkthrough on Google Drive](https://drive.google.com/file/d/10A3qNTNxzyu5v3NI0r-qU3P2uRpOUjzz/view?usp=sharing)

The video demonstrates the application's dashboards, portfolio analytics, AI-generated reports, grounding validation, and operational features.

### AI Demonstration Screenshots

**1. Portfolio Intelligence — AI-Generated Report**

The example below shows a successfully generated AI report with a `VERIFIED GROUNDED` status, using Groq with the `openai/gpt-oss-120b` model.

**2. Recommendation Review Console — Grounding Validation**

The example below shows the Recommendation Review Console displaying `FACT-GROUNDED VERIFIED`, with 21 out of 21 claims confirmed in that particular report.

> **Important limitations:** These screenshots document successful example runs and do not guarantee that every AI report will pass validation. The deployed application uses simulated market data rather than a verified live market feed. The backend is hosted on Render's free tier, which may sleep during inactivity and cause a delay on the first request after waking.

---

## 1. Architecture Overview & Technology Stack

### Backend
- **Language & Runtime:** Python 3.11 (tested on 3.11.9)
- **API Framework:** FastAPI 0.115.0 & Uvicorn 0.31.0
- **Validation & Settings:** Pydantic v2 (2.9.2) & Pydantic-Settings (2.5.2)
- **Database Layer:** SQLAlchemy 2.0 (2.0.35) with asynchronous SQLite via `aiosqlite` (0.20.0)
- **Database Engine:** SQLite configured with Write-Ahead Logging (WAL) and enforced foreign keys
- **Protocol Extensions:** Model Context Protocol (MCP) Python SDK (1.12.4)
- **Testing:** pytest 8.3.3 & pytest-asyncio 0.24.0 (353 automated tests)

### Frontend
- **Build Tool:** Vite 5.4.9
- **Framework:** React 18.3.1 with TypeScript 5.6.2
- **Styling:** Tailwind CSS 3.4.14 & PostCSS 8.4.47
- **Iconography:** Lucide React 0.453.0
- **HTTP Client:** Axios 1.7.7
- **Testing:** Vitest 2.1.3 & React Testing Library 16.0.1 with jsdom 25.0.1 (188 automated tests across 17 test suites)

---

## 2. The Seven Financial Dashboard Consoles

The web client provides seven integrated financial consoles accessible through the primary navigation bar:

1. **Portfolio Intelligence Hub (`portfolio`):**
   - Multi-portfolio management with an interactive switcher and new portfolio creation modal (`CreatePortfolioModal`).
   - Position tracking with symbol validation, asset class selection (Equity, ETF, Mutual Fund), and average buy price tracking (`AddHoldingModal`).
   - Real-time valuation, total invested capital, total unrealized P&L, day P&L calculations, and rule-based diversification alerts.
2. **Risk Exposure Panel (`risk`):**
   - Composite risk scoring on a calibrated 0–100 scale (`RiskScoreCard`).
   - Concentration analysis using the Herfindahl-Hirschman Index (HHI) categorized into Low, Moderate, or High tiers (`ConcentrationCard`).
   - Quantitative risk analytics: annualized historical volatility, Sharpe ratio, and Maximum Drawdown (`HistoricalRiskCard`).
   - Sector allocation breakdowns and data completeness audits (`SectorAllocationsCard`, `DataCompletenessCard`).
3. **Market Movement Explainer (`market`):**
   - Reference quote tracking for Indian benchmark indices (NIFTY 50, SENSEX, BANK NIFTY) (`MarketOverviewCard`).
   - Single-stock inspector displaying trading symbol, exchange, day high/low, and sector categorization (`StockInspectorCard`).
   - Evidence-grounded AI market explanations paired with structured news sentiment feeds (`AIExplanationSection`, `MarketNewsSection`).
4. **Recommendation Review Console (`recommendation`):**
   - Evidence-grounded proposal verification comparing model statements against ledger data.
   - Grounding status banners (`VERIFIED`, `FLAGGED_WITH_WARNINGS`, `CLAIM GROUNDING REJECTED`).
   - Mandatory calibration limitation disclosures and uncertainty gap reporting.
   - Interactive claim filters (by verification status, category, severity).
   - *Note on Review State:* Approve and Reject actions are evaluated locally in UI state for demonstration and are not written to backend database tables.
5. **Operations Dashboard (`operations`):**
   - Health telemetry displaying backend API status, SQLite connectivity, WAL mode, and foreign key enforcement.
   - Provider latency tracking and active mode status (Demo vs. Live).
   - In-memory cache telemetry: hit/miss counts, hit ratio, and active key count.
   - Manual controls for cache invalidation and telemetry polling.
6. **Compliance Audit Panel (`compliance`):**
   - Automated rule-based heuristics evaluating concentration thresholds and diversification guidelines.
   - Precedence fail-safe rules: mathematical discrepancies or ungrounded claims force report status to `REJECTED`.
   - Explicit disclosures on data persistence boundaries (audit logs are generated on-demand and not stored in persistent tables).
7. **Admin Config Console (`admin`):**
   - Zero-Cost Policy monitor verifying offline simulation status and ₹0 spend enforcement.
   - Active provider inspection (`demo` vs. `alpha_vantage` for market data; `demo` vs. `groq` for AI reasoning).
   - Safe API credential detection (verifies configuration presence without displaying actual secret values).

---

## 3. Project Directory Structure

```text
Zerodha-AI-Intelligence-New/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST endpoints (health, portfolios, market-data, news, ai)
│   │   ├── core/            # Configuration, caching, and privacy-safe logging filter
│   │   ├── db/              # SQLAlchemy session, engine (WAL), declarative base
│   │   ├── mcp/             # Model Context Protocol server tools and schemas
│   │   ├── models/          # Database models (PortfolioModel, HoldingModel)
│   │   ├── providers/       # Market data & news providers (demo & Alpha Vantage)
│   │   ├── schemas/         # Pydantic validation schemas
│   │   ├── services/        # Analytics, quantitative math, risk scoring, AI reasoning
│   │   └── main.py          # FastAPI application entrypoint & lifespan
│   ├── docs/                # Feature architecture specifications
│   ├── tests/               # 30 test modules (353 unit, integration, and security tests)
│   ├── pytest.ini           # Pytest async configuration
│   ├── requirements.txt     # Pinned Python dependencies
│   ├── requirements.lock    # Exact dependency lockfile
│   └── .env.example         # Backend environment template
├── frontend/
│   ├── src/
│   │   ├── api/             # Typed Axios client modules
│   │   ├── components/      # 7 dashboard consoles, cards, modals, navigation
│   │   ├── context/         # Central PortfolioContext state provider
│   │   ├── types/           # TypeScript domain interfaces
│   │   ├── utils/           # Currency (INR), percentage, and timestamp formatters
│   │   ├── App.tsx          # Shell layout, navigation bar, header portfolio selector
│   │   └── main.tsx         # React root mounting
│   ├── tests/               # 17 test modules (188 component, integration, and security tests)
│   ├── package.json         # Pinned Node dependencies and scripts
│   ├── package-lock.json    # Exact npm lockfile
│   ├── tsconfig.json        # Strict TypeScript configuration
│   ├── vite.config.ts       # Vite & Vitest configuration
│   └── .env.example         # Frontend environment template
├── .gitignore               # Excludes secrets, databases, caches, and node_modules
└── README.md                # Project documentation
```

---

## 4. Prerequisites

- **Python:** 3.11+ (verified on Python 3.11.9)
- **Node.js:** 18.x or 20.x (verified on Node v20.19.4) & npm (verified on 10.8.2)
- **Git:** 2.40+

---

## 5. Setup & Launch Instructions

### A. Backend Setup (FastAPI)

1. Navigate to the `backend` directory from the repository root:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   - **Windows (PowerShell):**
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - **Linux / macOS (bash):**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
3. Install pinned dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy the environment configuration template:
   - **Windows (PowerShell):**
     ```powershell
     Copy-Item .env.example .env
     ```
   - **Linux / macOS (bash):**
     ```bash
     cp .env.example .env
     ```
5. Start the backend development server:
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   *The server initializes the database directory (`./data/`) and schema tables automatically on startup. API documentation is available at `http://127.0.0.1:8000/docs`.*

---

### B. Frontend Setup (React + Vite)

1. In a separate terminal, navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```
2. Install npm dependencies:
   ```bash
   npm install
   ```
3. Copy the environment configuration template:
   - **Windows (PowerShell):**
     ```powershell
     Copy-Item .env.example .env
     ```
   - **Linux / macOS (bash):**
     ```bash
     cp .env.example .env
     ```
4. Start the Vite development server:
   ```bash
   npm run dev
   ```
5. Access the web interface in your browser:
   ```text
   http://127.0.0.1:5173
   ```

---

## 6. Environment Configuration

### Backend (`backend/.env`)
| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `development` | Runtime environment mode |
| `DEBUG` | `true` | Enables interactive Swagger docs at `/docs` |
| `APP_HOST` | `127.0.0.1` | Local bind address |
| `APP_PORT` | `8000` | Local bind port |
| `CORS_ORIGINS` | `["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"]` | Allowed origins for frontend requests |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/zerodha.db` | Local SQLite database connection path |
| `USE_MOCK_DATA` | `true` | Strict ₹0 spend policy toggle |
| `MARKET_DATA_PROVIDER`| `demo` | `demo` (offline fixed baseline) or `alpha_vantage` |
| `ALPHA_VANTAGE_API_KEY`| *(empty string)* | Optional API key for live Alpha Vantage market quotes |
| `ALPHA_VANTAGE_BASE_URL`| `https://www.alphavantage.co/query` | Alpha Vantage API query endpoint |
| `AI_PROVIDER` | `demo` | `demo` (offline rule-based reasoner) or `groq` |
| `GROQ_API_KEY` | *(empty string)* | Optional API key for Groq LLM inference |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Model identifier used if Groq is enabled |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | Groq OpenAI-compatible endpoint |

### Frontend (`frontend/.env`)
| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000/api/v1` | Backend REST API base URL |
| `VITE_APP_ENV` | `development` | Client environment flag |

---

## 7. Running the Automated Tests

### Backend Test Suite (pytest)
```bash
cd backend
pytest
```
- **353 tests pass** across 30 modules (~15 seconds execution time).
- Tests execute against isolated temporary SQLite databases (`tmp_path`) with automatic connection disposal, ensuring zero contamination of the development database.

### Frontend Test Suite (Vitest)
```bash
cd frontend
npm run test
```
- **188 tests pass** across 17 test suites (~15 seconds execution time).
- Validates all 7 dashboard consoles, modal workflows, client-side input validations, and error boundaries.

### Production Build & Type Verification
```bash
cd frontend
npm run build
```
- Executes strict TypeScript type verification (`tsc`) followed by the Vite production asset bundle build (`vite build`).

---

## 8. Demo Mode & Simulation Disclosures

The application defaults to an offline simulation environment:
- **Market Quotes:** Under `MARKET_DATA_PROVIDER=demo`, stock prices are drawn from fixed, deterministic reference baselines (`DEMO_INDIAN_EQUITIES`). Quotes do not change dynamically unless updated through manual inputs or alternative provider configuration.
- **News Feed:** News articles are pre-packaged educational simulation items with assigned sentiment categories.
- **AI Reasoning:** Under `AI_PROVIDER=demo`, insights and review cards are assembled deterministically from actual ledger math and rule-based heuristics without making external network calls.
- **Live Provider Fallbacks:** If `alpha_vantage` is enabled and encounters rate limits or errors, it returns `current_price=None` rather than fabricating simulated prices.

---

## 9. Security & Architecture Limitations

1. **No Authentication or Access Control:** The platform is designed as a local single-user technical prototype. It does not contain user authentication, password hashing, session tokens, or role-based access control.
2. **Single-Tenant Database:** All portfolios and holdings exist in a single local SQLite database file (`zerodha.db`) with no multi-user tenant isolation.
3. **Logging Sanitization Scope & Limitations:** The backend implements a custom `SanitizingLogFilter` that intercepts log records and tracebacks to redact recognized patterns (such as query parameters `api_key=`, `token=`, `Bearer <token>` headers, and `gsk_` keys).
   *Limitation:* Pattern-based sanitization does not guarantee detection or removal of arbitrary, unstructured high-entropy strings or unconventional token formats.
4. **CORS Restrictions:** The backend enforces CORS restrictions, permitting requests only from configured local development origins (`localhost:5173`, `127.0.0.1:5173`, `localhost:3000`, `127.0.0.1:3000`).

---

## 10. Financial & Regulatory Disclaimers

> [!WARNING]
> **Educational & Research Prototype Only**
> This software is strictly an academic, technical demonstration, and research tool.
>
> 1. **Not Investment Advice:** Nothing in this repository, documentation, or user interface constitutes financial, investment, legal, or tax advice.
> 2. **Not a SEBI Registered Entity:** The developers and contributors are not registered with the Securities and Exchange Board of India (SEBI) as Investment Advisers (RIA) or Research Analysts (RA). The heuristic checks in the Compliance Audit Panel do not represent official regulatory compliance or legal clearance.
> 3. **No Live Order Execution:** This application does not connect to brokerage trading gateways or place live orders on the National Stock Exchange (NSE) or Bombay Stock Exchange (BSE).
> 4. **Simulated Analytics:** Quantitative metrics calculated in demo mode use simulated models. Past simulated performance is no guarantee of future returns.

---

## 11. Current Limitations & Roadmap

### Current Limitations
- **Client-Side Review Actions:** Approve, Reject, and filter actions in the Recommendation Review Console update local UI component state and are not persisted in SQLite tables.
- **On-Demand Audit Generation:** Compliance and grounding evaluations are calculated dynamically on-demand; no historical revision audit trail is stored in the database.
- **Polling Telemetry:** Dashboard updates and health metrics rely on client-side polling rather than WebSocket streaming.

### Planned Roadmap
- [ ] Database schema support for persistent compliance audit logs and historical reviews.
- [ ] User authentication and multi-tenant portfolio segregation.
- [ ] Read-only broker API integration (e.g., Zerodha Kite Connect API) for automated portfolio balance synchronization.
- [ ] WebSocket streaming ticker integration for real-time market data.
