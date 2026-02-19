# Getting Started with Funnelier
## Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker (optional, for containerized setup)
## Quick Setup
### 1. Clone and Setup Environment
```bash
cd /Users/univers/projects/funnelier
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate
# Install dependencies
pip install -e ".[dev]"
# Copy environment configuration
cp .env.example .env
```
### 2. Start Infrastructure (Docker)
```bash
cd docker
docker-compose up -d postgres redis mongodb
```
### 3. Run the API
```bash
cd /Users/univers/projects/funnelier
PYTHONPATH=. uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```
API will be available at: http://localhost:8000
- Swagger Docs: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc
## Importing Your Data
### Import Leads from Excel
```bash
PYTHONPATH=. python scripts/import_leads.py
```
This will scan `leads-numbers/`# Getting Started with Funnelier
## Prerequisites
- Python 3.11+
- PostgreSQL p## Prerequisites
- Python 3.11+py- Python 3.11+
sc- PostgreSQL /`- Redis 7+
- Door- Docker  f## Quick Setup
### 1. Clone and Setup Envir??### 1. Clone│```bash
cd /Users/univers/projectarcd /Usai# Create virtual environment (recom  python -m venv venv
source venv/bin/activ?ource venv/bin/ac  # Install dependencies
 ?ip install -e ".[devic# Copy environment con
?p .env.example .env
```
#/      ```
### 2. Start Ints##??   │   ├── analytics/  # Funncd docridocker-c ?``
### 3. Run the API
```bash
cd /Users/uys##
?``bash
cd /Users?d /UsaiPYTHONPATH=. uvicorn src.api.main:a??```
API will be available at: http://localhost:8000
- Swagger Docs: httptoAP/ - Swagger Docs: http://localhost:8000/api/docsat- ReDoc: http://localhost:80│   └── api## Importing Your Data application
├─### Import Leads from  ```bash
PYTHONPATH=. pytho??PYTHON/ ```
This will scan `leads-numbers/`# Gettir/Th  ## Prerequisites
- Python 3.11+
- PostgreSQL p## Prerequisitesag- Python 3.11+
ir- PostgreSQL  S- Python 3.11+py- Python 3.114.sc- PostgreSQL /`- Redis 7+
-nswered (≥90s) → 6. Invoic### 1. Clone and Setup Envir??edcd /Users/univers/projectarcd /Usai# Createecency, Frequency, and Monetary value:
- Champions (555): Best customers
- Loyal (4xx, 5xx with high F ?ip install -e ".[devic# Copy environment con
?p .env.example c?p .env.example .env
```
#/      ```
### 2. Scu```
#/      ```
### na#/y
### 2. Staan### 3. Run the API
```bash
cd /Users/uys##
?``bash
cd (RFM thresholds, funnel s```bash
cd /Users data sour?``bash
cd /U pcd /UsentAPI will be available at: http://localhost:8000
- Swagger vo- Swagger Docs: httptoAP/ - Swagger Docs: http. ├─### Import Leads from  ```bash
PYTHONPATH=. pytho??PYTHON/ ```
This will scan `leads-numbers/`# Gettir/Th  ## Prerequisites
- Python 3"
