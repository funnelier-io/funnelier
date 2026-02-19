# Funnelier - Marketing Funnel Analytics Platform

<div align="center">

**A multi-tenant SaaS platform for SMS marketing analytics, funnel optimization, and RFM customer segmentation**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

## 🎯 Overview

Funnelier is designed to help businesses optimize their SMS marketing campaigns by:

- **Tracking the complete customer journey** from lead acquisition to payment
- **Analyzing funnel conversion rates** at each stage
- **Segmenting customers using RFM analysis** (Recency, Frequency, Monetary)
- **Recommending optimal messages and products** for each customer segment
- **Measuring sales team performance** and campaign effectiveness

## 📊 Funnel Stages

```
┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
│   LEAD     │───▶│    SMS     │───▶│    CALL    │───▶│  INVOICE   │───▶│  PAYMENT   │
│  ACQUIRED  │    │    SENT    │    │  ANSWERED  │    │   ISSUED   │    │  RECEIVED  │
│            │    │            │    │  (≥90sec)  │    │            │    │            │
└────────────┘    └────────────┘    └────────────┘    └────────────┘    └────────────┘
```

## 🏗️ Architecture

Funnelier follows **Domain-Driven Design (DDD)** principles with a **Modular Monolith** architecture:

- **Bounded Contexts**: Leads, Communications, Sales, Analytics, Segmentation, Campaigns
- **Event-Driven**: Domain events for cross-module communication
- **Multi-Tenant**: Schema-based isolation with configurable data sources
- **ETL Pipeline**: Flexible connectors for CSV, Excel, JSON, MongoDB, and APIs

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/funnelier.git
cd funnelier

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Start services with Docker
cd docker
docker-compose up -d

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn src.api.main:app --reload
```

### Using Docker Only

```bash
cd docker
docker-compose up -d
```

The API will be available at `http://localhost:8000`

## 📁 Project Structure

```
funnelier/
├── src/
│   ├── core/                    # Shared kernel
│   │   ├── domain/              # Base entities, value objects, events
│   │   ├── interfaces/          # Abstract interfaces (Repository, Connector)
│   │   └── config.py            # Application settings
│   │
│   ├── modules/                 # Bounded contexts
│   │   ├── leads/               # Lead & contact management
│   │   ├── communications/      # SMS & call tracking
│   │   ├── sales/               # Invoices & payments
│   │   ├── analytics/           # Funnel metrics
│   │   ├── segmentation/        # RFM analysis
│   │   └── campaigns/           # Campaign management
│   │
│   ├── infrastructure/          # Technical concerns
│   │   ├── database/            # SQLAlchemy setup
│   │   ├── connectors/          # Data source adapters
│   │   └── messaging/           # Event bus, Celery
│   │
│   └── api/                     # FastAPI application
│       ├── routes/              # API endpoints
│       └── main.py              # App entry point
│
├── tests/                       # Test suites
├── docs/                        # Documentation
├── docker/                      # Docker configuration
└── scripts/                     # Utility scripts
```

## 📡 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/leads/contacts` | List contacts with filtering |
| `POST /api/v1/leads/import/excel` | Import leads from Excel |
| `GET /api/v1/communications/calls` | List call logs |
| `POST /api/v1/communications/calls/import/mobile` | Import mobile call logs |
| `GET /api/v1/analytics/funnel` | Get funnel metrics |
| `GET /api/v1/analytics/team` | Get team performance |
| `GET /api/v1/segments/distribution` | Get RFM segment distribution |
| `GET /api/v1/segments/{segment}/recommendations` | Get segment recommendations |
| `GET /api/v1/sales/invoices` | List invoices |

Full API documentation available at `/api/docs`

## 🎯 RFM Segmentation

Customers are scored on three dimensions:

| Dimension | Score 5 | Score 4 | Score 3 | Score 2 | Score 1 |
|-----------|---------|---------|---------|---------|---------|
| **Recency** | 0-3 days | 4-7 days | 8-14 days | 15-30 days | 30+ days |
| **Frequency** | 10+ purchases | 5-9 | 3-4 | 2 | 1 |
| **Monetary** | 1B+ IRR | 500M-1B | 100M-500M | 50M-100M | <50M |

### Segments

| Segment | RFM Pattern | Recommended Action |
|---------|-------------|-------------------|
| **Champions** | 555, 554, 545 | Exclusive offers, VIP treatment |
| **Loyal** | 435, 534, 443 | Upsell, loyalty programs |
| **At Risk** | 155, 154, 145 | Urgent reactivation |
| **Lost** | 111, 112, 121 | Final win-back or remove |

## 🔌 Data Source Connectors

Funnelier supports multiple data sources:

### File-Based
- **CSV**: Call logs, SMS delivery reports
- **Excel**: Lead lists, customer data
- **JSON**: VoIP call logs (Asterisk CDR)

### Database
- **MongoDB**: Invoice and payment data
- **PostgreSQL/MySQL**: ERP/CRM integration

### API
- **Kavenegar**: SMS delivery status
- **Custom webhooks**: Real-time updates

## 📈 Key Features

### Funnel Analytics
- Daily/weekly/monthly conversion tracking
- Stage-by-stage drop-off analysis
- Cohort analysis
- Bottleneck identification

### RFM Segmentation
- Automatic scoring based on purchase history
- Segment migration tracking
- Product recommendations per segment
- Template suggestions for campaigns

### Team Performance
- Per-salesperson metrics
- Lead assignment tracking
- Call duration analysis
- Conversion leaderboards

### Alerting
- Threshold-based alerts
- Conversion rate monitoring
- Anomaly detection
- Multi-channel notifications

## 🛠️ Configuration

Key environment variables:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/funnelier

# Redis
REDIS_URL=redis://localhost:6379/0

# RFM Configuration
RFM_RECENCY_DAYS_RECENT=14
RFM_MONETARY_HIGH_THRESHOLD=1000000000

# Funnel
FUNNEL_MIN_CALL_DURATION_SECONDS=90

# SMS Provider
KAVENEGAR_API_KEY=your-api-key
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific module tests
pytest tests/unit/modules/segmentation/
```

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

<div align="center">
Built with ❤️ for better marketing analytics
</div>

