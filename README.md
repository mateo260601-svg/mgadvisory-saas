# MG Advisory Finance OS

> Institutional finance SaaS — business plan modelling, QoE packs, debt analytics, and transaction outputs.

**Stack:** FastAPI · Python 3.11 · openpyxl · python-pptx · HTML/CSS/JS frontend  
**Deploy:** Railway (one-click) · GitHub Actions ready

---

## What it does

| Module | What you get |
|--------|-------------|
| **Projects** | Create a dossier per company; upload audited accounts, management accounts, trial balance, aged AR/AP, debt schedules, budget |
| **AI extraction** | Claude reads uploaded PDF/XLSX/CSV and returns a structured JSON extraction: income statement, balance sheet, cash flow, working capital, debt |
| **Excel BP model** | 30-tab institutional model: Admin, Group Assumptions, Control Panel, Historical Inputs, 3-entity data inputs, monthly/annual outputs, Revenue Drivers, Product Build, Headcount, Opex, Working Capital, Capex, 10-tranche Debt Config, Debt Schedule, Financial Statements, Covenants, Debt Capacity, Sensitivity Matrix, Restructuring Options, IC Summary, Packaged Output, Checks |
| **QoE pack** | EBITDA normalisation with category-based audit trail, revenue quality scoring, working capital DSO/DPO/DIO analysis |
| **Restructuring options** | Liquidity runway, debt capacity, ranked options paper (10 options: A&E, new money, scheme, admin, D/E swap, etc.) |
| **Lender deck (PPTX)** | 10-slide institutional presentation: cover, executive snapshot, historicals, BP bridge, debt & covenants, restructuring options, diligence priorities |
| **Debt library** | 80+ instrument types (senior, unitranche, mezzanine, PIK, HY bond, restructuring, project finance, leases, etc.) |

---

## Quick start (local)

```bash
# 1. Clone
git clone https://github.com/YOUR_USER/mg-advisory-finance-os.git
cd mg-advisory-finance-os

# 2. Install
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# 3. Configure (optional — app runs without these)
cp .env.example .env
# Edit .env with your keys

# 4. Run
uvicorn app.main:app --reload

# 5. Open
# http://127.0.0.1:8000
# License key (demo): MG-ADVISORY-DEMO-2026
```

API documentation: `http://127.0.0.1:8000/docs`

---

## Deploy to Railway

**3-minute deploy:**

1. Fork/push this repo to GitHub (large `.pptx` template files are gitignored — only the manifest JSON goes up)
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
3. Select your repo
4. Add environment variables (see `RAILWAY_SETUP.md`)
5. Railway reads `railway.json` and starts automatically

Test with: `https://your-app.up.railway.app/health`

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MG_LICENSE_KEY` | Yes | Production license key (replaces the demo key) |
| `APP_SECRET` | Yes | Long random string for cookie signing |
| `ANTHROPIC_API_KEY` | Optional | Enable AI financial extraction and project briefs |
| `ANTHROPIC_MODEL` | Optional | Default: `claude-sonnet-4-6` |
| `GOOGLE_CLIENT_ID` | Optional | Enable Google OAuth login |
| `GOOGLE_CLIENT_SECRET` | Optional | Google OAuth |
| `GOOGLE_REDIRECT_URI` | Optional | e.g. `https://your-app.up.railway.app/auth/callback` |
| `GOOGLE_ALLOWED_DOMAINS` | Optional | Restrict to `yourfirm.com,client.com` |

Without `ANTHROPIC_API_KEY`: the app runs fully with deterministic local fallbacks.  
Without Google vars: only license-key login is available.

---

## Project structure

```
app/
  main.py                   # FastAPI app factory + route registration
  config.py                 # All env vars and path constants
  routes/
    auth.py                 # License key + Google OAuth
    projects.py             # CRUD projects
    documents.py            # List / delete uploaded documents
    upload.py               # Upload PDF/XLSX/CSV
    bp.py                   # Generate / download BP Excel model
    debt.py                 # Debt preview + instrument library
    qoe.py                  # QoE pack, EBITDA normalisation
    restructuring.py        # Restructuring options paper
    decks.py                # Lender PPTX presentation
    ai.py                   # Claude AI extraction and briefing
  services/
    project_service.py      # Project CRUD
    extraction_service.py   # File upload + document listing
    financial_mapping_service.py  # Normalise uploaded financials
    output_service.py       # Orchestrate Excel + PPTX generation
    ai_service.py           # Claude API calls + fallbacks
    deck_planning_service.py      # AI deck blueprint planning
    template_service.py     # PPTX template manifest loading
  engines/
    historical_accounts_engine.py  # Chart-of-accounts mapping
    bp_engine.py            # Forecast periods, revenue bridge, scenarios
    debt_engine.py          # 80+ instrument library + waterfall
    qoe_engine.py           # EBITDA normalisation, revenue/WC quality
    restructuring_engine.py # Liquidity, debt capacity, options ranking
  builders/
    excel_builder.py        # openpyxl — full 30-tab BP workbook
    pptx_builder.py         # python-pptx — 10-slide lender deck
    report_builder.py       # Future: PDF report
  schemas/
    project_schema.py       # ProjectCreate, ProjectUpdate, Project
    financial_schema.py     # NormalizedFinancials, FinancialLine
    debt_schema.py          # DebtFacility
frontend/
  index.html
  styles.css
  app.js
  assets/
templates/
  pptx/
    template_manifest.json  # Slide pattern library (in git)
    README.md
    # *.pptx files are gitignored (21MB+) — store locally or in S3
data/
  projects/                 # Runtime project storage (gitignored)
outputs/                    # Generated Excel/PPTX/PDF (gitignored)
scripts/
  smoke_test.py             # Verify Excel generation works
  verify_workbook.py        # Inspect generated workbook
requirements.txt
Procfile                    # Railway fallback start command
runtime.txt                 # python-3.11.9
railway.json                # Primary Railway config
.env.example                # Template for local .env
```

---

## API endpoints (key)

```
GET  /health                                     Health check
POST /api/auth/login                             License key login
GET  /api/auth/google/url                        Google OAuth URL
GET  /api/auth/session                           Current session

GET  /api/projects                               List projects
POST /api/projects                               Create project
GET  /api/projects/{id}                          Get project
PATCH /api/projects/{id}                         Update project
POST /api/projects/{id}/archive                  Soft-archive project

GET  /api/projects/{id}/documents                List uploaded documents
DELETE /api/projects/{id}/documents/{filename}   Delete a document
POST /api/projects/{id}/upload                   Upload a file

POST /api/projects/{id}/bp/generate              Generate Excel BP model
GET  /api/projects/{id}/bp/download              Download BP model

POST /api/projects/{id}/decks/lender/plan        Plan lender deck (AI)
POST /api/projects/{id}/decks/lender/generate    Generate PPTX
GET  /api/projects/{id}/decks/lender/download    Download PPTX

POST /api/qoe/projects/{id}/pack                 Full QoE pack
GET  /api/qoe/projects/{id}/revenue-quality      Revenue quality scoring
GET  /api/qoe/projects/{id}/working-capital-quality  DSO/DPO/DIO

POST /api/restructuring/projects/{id}/paper      Restructuring options paper
POST /api/restructuring/liquidity-analysis       Standalone liquidity
POST /api/restructuring/debt-capacity            Standalone debt capacity

GET  /api/debt/library                           Debt instrument library
POST /api/debt/preview                           Preview one facility

GET  /api/ai/status                              Claude configured?
POST /api/ai/projects/{id}/brief                 AI project brief
POST /api/ai/projects/{id}/extract-historicals   AI financial extraction
```

---

## Stability guarantees

- Server never crashes at startup if an optional module fails to load.
- All heavy imports (`openpyxl`, `python-pptx`, `pypdf`) are lazy-loaded inside builder functions.
- If Claude is not configured, all AI endpoints return clean local fallbacks.
- If Google OAuth is not configured, the Google login button is hidden.
- `data/projects/` and `outputs/` are excluded from git.
- Large template PPTX files (21MB+) are excluded from git (add to object storage for production).

---

## Roadmap (next)

- [ ] QoE Excel pack export (openpyxl tab in the BP workbook)
- [ ] Covenant headroom sensitivity charts in the PPTX
- [ ] Multi-user support with JWT tokens
- [ ] S3/R2 storage for documents and outputs
- [ ] Webhook for async Excel generation (long-running jobs)
