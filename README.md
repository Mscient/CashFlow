# Cash-Flow Blindspot

**Small Business Cash-Flow Intelligence System**  
*PVPIT Computer Engineering Department · Hackathon Project*

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Initialise DB + load sample data
python backend/db/database.py

# 3. Launch the dashboard
streamlit run frontend/streamlit_app.py

# 4. (Optional) Run unit tests
python -m pytest tests/ -v

# 5. (Optional) Run Flask REST API
python backend/app.py
```

---

## Architecture

```
cashflow_blindspot/
├── backend/
│   ├── config.py                    ← All thresholds (single source of truth)
│   ├── db/database.py               ← SQLite schema + query helpers
│   ├── ingestion/
│   │   ├── csv_importer.py          ← CSV → DB (with smart defaults)
│   │   └── fuzzy_match.py           ← difflib name resolution
│   ├── forecasting/
│   │   ├── behaviour_model.py       ← 3-tier survival model (P2)
│   │   ├── forecast_engine.py       ← 90-day deterministic timeline (P3)
│   │   └── monte_carlo.py           ← 2000-run MC simulation (P3)
│   ├── alerts/alert_engine.py       ← Tiered alert generation (P4)
│   ├── suggestions/
│   │   └── suggestion_engine.py     ← Expected-Risk optimizer (P5)
│   ├── scheduler/daily_job.py       ← Pipeline orchestrator
│   └── app.py                       ← Flask REST API
├── frontend/
│   └── streamlit_app.py             ← Premium dashboard (P6)
├── data/
│   └── sample_transactions.csv      ← 8-customer synthetic dataset
└── tests/
    ├── test_behaviour_model.py
    └── test_forecast_engine.py
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Survival-based prediction** | Per-customer `personal_hazard_offset` + Bayesian shrinkage |
| **Monte Carlo bands** | 2,000 paths × 90 days → P5/P25/P50/P75/P95 |
| **Expected Risk ranking** | `Value × P(late) × Urgency_Weight` from Appel et al. |
| **Gap-closing optimizer** | Greedy selection of chase/delay actions to close cash gap |
| **One-tap message draft** | Pre-written WhatsApp/SMS for each selected invoice |
| **Cold-start safe** | Cohort prior for new customers with < 5 invoices |

## Demo vs Production

| Aspect | Demo | Production |
|--------|------|------------|
| Storage | SQLite | PostgreSQL |
| Scheduling | On dashboard load | GCP Cloud Scheduler + Cloud Run |
| Fuzzy match | `difflib` | `rapidfuzz` |
| Frontend | Streamlit | Flask/React |
