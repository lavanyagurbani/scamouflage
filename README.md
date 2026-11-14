# Scamouflage — Job Fraud and Phishing Analytics Pipeline

Scamouflage is a data engineering project designed to process and analyze fraudulent job postings and phishing reports.

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
- Provides five navigation sections:
  - Overview
  - Job Fraud Analytics
  - Phishing Intelligence
  - Ask Scamouflage
  - Pipeline Status

### 6. Guided Conversational BI

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
├── ingestion/            # BigQuery ingestion scripts
├── tests/                # Offline tests
├── README.md             # Project overview and setup
└── TECHNICAL_HANDOFF.md  # Technical handoff documentation
```

*Directory names should be checked against the current repository before finalizing this section.*

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

### Step 3: Set Up Dependencies

Follow the component-specific instructions in the `airflow/`, `airbyte/`, and `dashboard/` documentation.

The project uses separate Python environments for some components. Refer to the repository's existing setup instructions for their exact dependency versions and installation commands.

### Step 4: Run the Dashboard

From the project root, with the dashboard dependencies installed:

```powershell
$env:GCP_PROJECT_ID = "scamouflage"
python -m streamlit run dashboard/app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
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
- **19 passing dashboard tests** following the final UI updates.

---

## Project Scope

Scamouflage is an analytics and data engineering demonstration. It does not perform real-time fraud detection, machine learning-based prediction, or unrestricted natural-language-to-SQL generation.

Its primary objective is to demonstrate how data from multiple sources can be ingested, transformed, orchestrated, and explored through a cloud-based analytics workflow.
