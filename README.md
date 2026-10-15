# Wealth Advisor Assistant — Multi-Agent System

A beginner-friendly, local-first technical assignment project. The workflow reads a fictional financial ledger, fetches a matching profile from a mock CRM REST API, calculates cash-flow summaries, flags unusual activity with explainable rules, and asks a person to approve or reject each flag before the final report is saved.

The demonstration uses no LLM, paid API, bank connection, or real client information. LangGraph coordinates the agents; FastAPI serves the mock CRM; Pydantic validates inputs and outputs.

> **Safety note:** This is an educational demonstration, not financial, tax, legal, fraud, or investment advice. All included people and financial data are fictional.

## What is included

- **Orchestrator agent:** A LangGraph state graph coordinates fetch → analyze → human review → report. It skips analysis and creates a partial report if financial data cannot be validated.
- **Data fetcher agent:** Loads a local JSON ledger and retrieves client context through an HTTP tool abstraction.
- **Analyzer agent:** Summarizes income, expenses, monthly cash flow, and category totals; applies transparent anomaly rules.
- **Human review:** The CLI shows every flagged item and its explanation. Only explicitly approved insights are included in the report. Blank answers count as rejection.
- **Memory:** JSON files store notes for each session and historical analysis summaries per client.
- **Mock CRM:** A FastAPI server provides fictional profiles at `GET /clients/{client_id}`.
- **Tests:** Unit and workflow tests cover the analyzer, agent tools, approvals, memory, invalid data, missing files, CRM failures, and empty ledgers.
- **Example data/report:** `data/` and `examples/example_report.json`.

## Architecture

```text
run_demo.py
  └─ OrchestratorAgent (LangGraph)
       ├─ DataFetcherAgent
       │    ├─ FinancialDataTool → JSON file → Pydantic ClientFinancials
       │    └─ CrmTool → HTTP GET → FastAPI mock CRM → Pydantic ClientProfile
       ├─ AnalyzerAgent → explainable financial metrics and flagged insights
       ├─ Human review callback → approved/rejected decisions
       └─ Final report → JSON output + session and historical memory
```

### Design decisions and assumptions

1. **Local-first, no paid service:** Every feature works with the included fictional data and the local mock CRM.
2. **Rules, not opaque model output:** The analyzer does not make an investment recommendation. Each anomaly has a stable rule ID, severity, explanation, and (where applicable) transaction IDs.
3. **Human approval is fail-closed:** The terminal asks about each flag. If no reviewer is configured, a review callback fails, or a decision is omitted, the flag is excluded.
4. **Amounts are positive:** `transaction_type` determines whether a transaction contributes to income or expenses. Currency defaults to USD.
5. **The sample ledger is illustrative:** It contains two months of fictional activity and deliberate examples of a large purchase, an exact duplicate, and a category increase.
6. **Small JSON memory:** This is suitable for a single-user demo, not concurrent production workloads or regulated record retention.
7. **Tools are interfaces:** Agents depend on `FinancialDataTool` and `CrmTool`, not on direct JSON parsing or raw HTTP calls. Implementations can be swapped in tests or future extensions.

## Explainable anomaly rules

- **Large expense:** A transaction is flagged if it is at least the greater of `$2,500` or four times the median expense in the loaded ledger.
- **Possible duplicate:** Repeated date + amount + type + merchant/description combinations are flagged after the first matching transaction.
- **Category monthly spike:** A category is flagged when its current observed month's spend exceeds both twice the prior observed month and the prior month plus `$500`.
- **Cash-flow deficit:** A high-severity insight is raised when expenses exceed income in the loaded data.

These are review prompts, not fraud determinations. The final report distinguishes machine-generated flags from items approved by a person.

## Requirements

- Python 3.11 or newer
- Windows 11 with VS Code, macOS, or Linux
- Internet access for the initial dependency installation only

## Setup on Windows 11 / VS Code

Open this folder (`wealth-advisor-assistant`) in VS Code. In its integrated PowerShell terminal:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks activation, either run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, or use Command Prompt and `.venv\Scripts\activate.bat`.

### Start the mock CRM and run the assistant

Use two VS Code terminals, both opened in this folder.

**Terminal 1 — CRM API:**

```powershell
python run_crm.py
```

The API listens on `http://127.0.0.1:8000`. You can view its interactive API docs at `http://127.0.0.1:8000/docs`.

**Terminal 2 — assistant:**

```powershell
python run_demo.py --client-id client-001
```

For each flagged insight, read the rule and explanation, then enter `y` to approve it or `n`/Enter to reject it. The report is printed and saved to `outputs/generated_report.json`. Logs are written to `logs/wealth-advisor.log`; memory is stored under `data/history/`.

The assistant can still create a partial report if the CRM server is unavailable; the report will contain a warning. Financial data validation failures are included in the report's `errors` field.

### Useful options

```powershell
python run_demo.py --help
python run_demo.py --client-id client-001 --data data/client_financials.json
python run_demo.py --client-id client-001 --no-review
```

`--no-review` is intended for automation and tests. It safely rejects all flagged insights; it does not auto-approve them.

### Run tests

From the project folder with dependencies installed:

```powershell
python -m pytest
```

The test suite uses in-memory test doubles and temporary files for workflow tests, so it does not require the mock CRM server to be running.

## Project structure

```text
wealth-advisor-assistant/
├── data/
│   ├── client_financials.json
│   └── mock_crm_clients.json
├── examples/
│   └── example_report.json
├── scripts/
│   └── package_project.py
├── src/wealth_advisor/
│   ├── agents/
│   │   ├── analyzer.py
│   │   ├── data_fetcher.py
│   │   └── orchestrator.py
│   ├── tools/
│   │   ├── client_data.py
│   │   ├── crm_client.py
│   │   └── memory.py
│   ├── cli.py
│   ├── config.py
│   ├── logging_config.py
│   ├── mock_crm_api.py
│   └── models.py
├── tests/
├── .env.example
├── requirements.txt
├── run_crm.py
└── run_demo.py
```

## Configuration

Copy `.env.example` to `.env` and edit values if needed:

| Setting | Default | Purpose |
| --- | --- | --- |
| `CRM_BASE_URL` | `http://127.0.0.1:8000` | Mock CRM URL used by the data-fetching tool |
| `CRM_PORT` | `8000` | Port used by `run_crm.py` |
| `FINANCIAL_DATA_PATH` | `data/client_financials.json` | Default client ledger |
| `CRM_DATA_PATH` | `data/mock_crm_clients.json` | CRM mock data |
| `MEMORY_DIR` | `data/history` | Session notes and historical summaries |
| `LOG_FILE` | `logs/wealth-advisor.log` | Agent and workflow log file |
| `LOG_LEVEL` | `INFO` | Python logging level |

Path settings can be absolute paths or paths relative to the project folder. Do not put API keys or real client data in the sample project or ZIP.

## Build the downloadable ZIP

After installing Python (the packager uses only the standard library), run:

```powershell
python scripts/package_project.py
```

The archive is written to `dist/wealth-advisor-assistant.zip`. The packager excludes `.env`, virtual environments, logs, generated memory/reports, caches, and the archive directory itself; `.env.example`, source, tests, sample data, and documentation are included.

## Extending the project

- Add another implementation of `FinancialDataTool` or `CrmTool` without changing agent logic.
- Add a separate analyzer rule that returns a `FlaggedInsight` with a clear explanation and test it independently.
- Replace `MemoryStore` with a database-backed store if the demo grows beyond a local, single-user exercise.
- Add authentication and access controls before exposing any service beyond localhost.
