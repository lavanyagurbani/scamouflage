# Scamouflage — Job Fraud and Phishing Analytics Pipeline

Scamouflage is a data engineering project designed to process and analyze fraudulent job postings and phishing reports, with an advisory job-link risk checker.

The project combines data ingestion, cloud storage, SQL transformations, workflow orchestration, and an interactive analytics dashboard. It uses Apache Airflow, Airbyte, Google BigQuery, dbt, and Streamlit to demonstrate a practical data engineering workflow.

---

## Features

### 1. Data Ingestion

- Processes a dataset containing **17,880 job postings**, including **866 fraudulent postings**.
- Processes **45,680 phishing reports**.
- Loads source datasets into Google BigQuery using batch ingestion.
- Includes a verified Airbyte File Source to SQLite Destination synchronization workflow.
- Uses a separate Python batch bridge to transfer validated Airbyte output into BigQuery proof tables.

### 2. Cloud Data Warehouse

- Uses **Google BigQuery** for storing and querying datasets.
- Organizes data into raw and analytics datasets.
- Supports analytical queries for job fraud patterns and phishing activity.

### 3. Data Transformation with dbt

- Implements five analytical views:
  - `stg_job_postings`
  - `stg_phishing_reports`
  - `mart_job_fraud_overview`
  - `mart_job_fraud_patterns`
  - `mart_phishing_daily`
- Uses SQL-based transformations to prepare raw records for analysis.
- Includes dbt data quality tests.

### 4. Workflow Orchestration

- Uses **Apache Airflow** to orchestrate the main data pipeline.
- Implements three sequential tasks:
  - `ingest_raw_data`
  - `dbt_run`
  - `dbt_test`
- Runs Airflow locally through Docker Compose.
- The Airbyte synchronization and BigQuery bridge are separate workflows, not tasks in the Airflow DAG.

### 5. Interactive Analytics Dashboard

- Built using **Streamlit**.
- Provides Light and Dark themes.
- Displays key metrics for job postings, fraudulent postings, fraud rate, and phishing reports.
- Includes visualizations of job fraud patterns and phishing activity.
- Provides six navigation sections:
  - Overview
  - Check Job Link
  - Job Fraud Analytics
  - Phishing Intelligence
  - Ask Scamouflage
  - Pipeline Status

### 6. Check Job Link

- Validates a submitted URL and reports transparent URL heuristic indicators.
- Checks exact and conservatively normalized matches against a locally built historical phishing index.
- Classifies **manually pasted job title and description** with a real TF-IDF/logistic-regression model trained on the labelled job snapshot.
- Keeps URL indicators, historical matches and ML evidence separate; scores are uncalibrated and advisory.
- Does **not** scrape websites, provide live phishing intelligence or save scans to BigQuery.
- Works without BigQuery credentials, with explicit unavailable states when local artifacts are missing.

See [checker setup, actual evaluation, limitations and demo](docs/job-checker.md) and
[global theme verification](docs/dashboard-accessibility.md).

### 7. Guided Conversational BI

- Allows users to explore data through predefined analytical questions.
- Provides answers using supported BigQuery-backed queries.
- Includes questions about job fraud rates and dataset statistics.
- Uses guided question selection rather than unrestricted AI-generated SQL.

---

## Technology Stack

| Layer | Technologies |
| --- | --- |
| Data Ingestion | Python, Airbyte |
| Workflow Orchestration | Apache Airflow, Docker Compose |
| Cloud Data Warehouse | Google BigQuery |
| Data Transformation | dbt Core, dbt-bigquery, SQL |
| Dashboard | Streamlit, Python |
| Job-content classification | scikit-learn, TF-IDF, logistic regression |
| Data Sources | Fake Job Postings Dataset, PhishTank Reports |
| Version Control | Git, GitHub |

---

## Project Structure

```text
scamouflage/
├── airbyte/              # Connector sync and BigQuery batch bridge
├── airflow/              # Airflow configuration and DAG
├── dashboard/            # Streamlit application and UI
├── data/                 # Local dataset directory (datasets excluded from Git)
├── dbt/                  # dbt project and SQL models
├── docs/                 # Technical documentation
├── scripts/              # BigQuery ingestion and audit scripts
├── tests/                # Offline tests
├── README.md             # Project overview and setup
└── TECHNICAL_HANDOFF.md  # Technical handoff documentation
```

Additional folders: `checker/` contains training, inference, URL checks and historical lookup; `.streamlit/` contains native theme configuration.

---

## Getting Started

### Prerequisites

- Python
- Docker Desktop
- Google Cloud project with BigQuery access
- Google Cloud Application Default Credentials
- Git

### Step 1: Clone the Repository

```bash
git clone https://github.com/lavanyagurbani/scamouflage.git
cd scamouflage
```

### Step 2: Configure Google Cloud

Authenticate using Google Cloud Application Default Credentials:

```bash
gcloud auth application-default login
```

Set the project ID in PowerShell:

```powershell
$env:GCP_PROJECT_ID = "scamouflage"
```

The project requires access to the appropriate BigQuery datasets and tables. Cloning the repository does not automatically provide access to the existing cloud resources.

The hosted dashboard reads three aggregate-only authorized views in `scamouflage_dashboard`, generated from the existing dbt logic; the five historical dbt views remain intact. See [the access boundary and verification gates](docs/aggregate-deployment.md).

On Streamlit Community Cloud, configure the project and service account through secure app Secrets. See [Cloud BigQuery setup and least-privilege permissions](docs/streamlit-cloud-bigquery.md). Local ADC remains supported.

### Step 3: Set Up Dependencies and Local Checker Artifacts

Use Python 3.10 or newer in a separate environment. From the repository root:

```powershell
python -m venv .venv-checker
.\.venv-checker\Scripts\python.exe -m pip install -r requirements-dev.txt
```

For classifier and phishing matching, obtain the real datasets following
[data preparation](docs/data-preparation.md), place `fake_job_postings.csv` and
`phishing_reports.csv` in `data/`, then build the local artifacts:

```powershell
.\.venv-checker\Scripts\python.exe -m checker.train
.\.venv-checker\Scripts\python.exe -m checker.history
```

Datasets, model binaries and lookup indexes are deliberately excluded from Git.
A fresh clone can run offline tests and the dashboard without them; ML and history
checks show unavailable until artifacts are built. Two real-model integration
tests skip explicitly when the model is absent. No substitute dataset is downloaded.


Follow the component-specific instructions in the `airflow/`, `airbyte/`, and `dashboard/` documentation.

The project uses separate Python environments for some components. Refer to the repository's existing setup instructions for their exact dependency versions and installation commands.

### Step 4: Run the Dashboard

From the project root, with the dashboard dependencies installed:

```powershell
$env:GCP_PROJECT_ID = "scamouflage"
.\.venv-checker\Scripts\python.exe -m streamlit run dashboard/app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Open:

`http://127.0.0.1:8501`

### Step 5: Run the Airflow Pipeline

Use the Docker Compose setup documented in `airflow/README.md`.

The Airflow DAG `scamouflage_pipeline` executes the ingestion, dbt transformation, and dbt testing stages in sequence.

---

## Data Pipeline Architecture

```text
Source CSV Datasets
        |
        v
Python Batch Ingestion
        |
        v
Google BigQuery (Raw)
        |
        v
dbt Transformations
        |
        v
Google BigQuery (Analytics)
        |
        v
Streamlit Dashboard
```

**Airflow orchestration:** Runs the main Python ingestion and dbt workflow.

**Separate Airbyte validation path:**

```text
CSV Files
    |
    v
Airbyte File Source
    |
    v
Airbyte SQLite Destination
    |
    v
Python Batch Bridge
    |
    v
BigQuery Proof Tables
```

The Airbyte proof tables demonstrate successful connector-based ingestion. The dashboard uses the main analytics views rather than these proof tables.

---

## Testing and Validation

The project has been validated through:

- Successful ingestion of **17,880 job postings** and **45,680 phishing reports**.
- Successful execution of **five dbt analytical views**.
- **Four passing dbt tests**.
- Successful execution of the three-task Airflow DAG.
- Verified Airbyte full synchronization and BigQuery proof-table batch loads.
- **22 passing dashboard-focused tests** following global theme updates.
- Latest implementation full suite: **64 passed** with local trained artifacts; Airbyte offline suites: **27 passed**.
- Held-out job-content evaluation: precision **0.6370**, recall **0.6992**, F1 **0.6667**, average precision **0.7417** on **2,946** postings.
- Release-specific validation is recorded in [release validation](docs/public-release-validation.md).

Run offline tests from a fresh clone after installing `requirements-dev.txt`:

```powershell
.\.venv-checker\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-checker\Scripts\python.exe -m unittest discover -s airbyte -p 'test*offline.py' -v
```

---

## Project Scope

Scamouflage is an analytics and data engineering demonstration with a baseline ML job-content classifier. It does not perform automatic website scraping, live threat intelligence, guaranteed fraud detection, or unrestricted natural-language-to-SQL generation. Automatic extraction is disabled for SSRF safety; users supply job text manually.

Its primary objective is to demonstrate how data from multiple sources can be ingested, transformed, orchestrated, and explored through a cloud-based analytics workflow.

Private Cloud checker artifact provisioning and rebuild instructions: [deployment guide](docs/private-checker-deployment.md).
