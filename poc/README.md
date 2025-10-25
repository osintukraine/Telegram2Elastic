# OSINT Semantic Archive - Proof of Concept

**AI-powered Telegram archiving for OSINT researchers**

This proof-of-concept demonstrates a next-generation Telegram archiving system that goes beyond traditional archiving by adding real-time AI analysis, semantic enrichment, and developer-friendly APIs.

## What Makes This "Out of This World"

1. **Real-time Intelligence**: Continuous monitoring vs batch mode processing
2. **AI Classification**: Automatic spam filtering + OSINT value scoring (0-100)
3. **Entity Extraction**: Automatic detection of people, locations, military units, organizations
4. **Geospatial Analysis**: Extract and map coordinates from message text
5. **Engagement Analytics**: 6 engagement metrics + 17 reaction types tracking
6. **Developer API**: REST API for building custom OSINT tools
7. **Semantic Search**: Query by topics, entities, OSINT score, not just keywords

## Architecture

```
Telegram → Telethon Client → AI Enrichment Pipeline → PostgreSQL + MinIO → REST API → Dashboard
                                      ↓
                           ┌──────────┴──────────┐
                           │                     │
                    LLM Classification    NER + Geolocation
                    (spam, OSINT score,   (spaCy + custom
                     topics, sentiment)    military patterns)
```

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Telethon
- **Database**: PostgreSQL 15+ (with JSONB for flexible enrichment)
- **Storage**: MinIO (S3-compatible, content-addressed media storage)
- **AI/ML**:
  - Together.ai (Llama 3.1 70B) for classification
  - spaCy for named entity recognition
  - sentence-transformers for embeddings
- **Frontend**: Simple HTML/JS dashboard

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose
- Telegram API credentials (api_id, api_hash)
- Together.ai API key

### 1. Clone and Install

```bash
# Navigate to the PoC directory
cd poc/

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install package with dev dependencies
pip install -e ".[dev]"

# Download spaCy model
python -m spacy download en_core_web_lg
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use your favorite editor
```

**Required environment variables:**

| Variable | Description | Example |
|----------|-------------|---------|
| `TELEGRAM_API_ID` | Telegram API ID from my.telegram.org | `12345678` |
| `TELEGRAM_API_HASH` | Telegram API hash from my.telegram.org | `abcdef1234567890...` |
| `TELEGRAM_PHONE` | Your phone number with country code | `+1234567890` |
| `TOGETHER_API_KEY` | Together.ai API key | `your-together-ai-key` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@localhost:5432/osint` |
| `MINIO_ENDPOINT` | MinIO endpoint | `localhost:9000` |
| `MINIO_ACCESS_KEY` | MinIO access key | `minioadmin` |
| `MINIO_SECRET_KEY` | MinIO secret key | `minioadmin` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379` |

### 3. Start Infrastructure

```bash
# Start PostgreSQL, MinIO, Redis
docker-compose up -d

# Wait for services to be healthy
docker-compose ps

# Run database migrations
alembic upgrade head
```

### 4. Run the Archiver

```bash
# Listen for new messages (real-time mode)
python -m src listen --channel @example_channel

# Or import historical messages
python -m src import --channel @example_channel --limit 1000
```

### 5. Start the API Server

```bash
# In a new terminal
uvicorn src.api.main:app --reload --port 8000
```

### 6. Access the Dashboard

Open your browser to: http://localhost:8000/static/index.html

## Project Structure

```
poc/
├── src/
│   ├── core/               # Core functionality
│   │   ├── config.py       # Configuration management
│   │   ├── models.py       # SQLAlchemy models
│   │   ├── telegram_client.py  # Telegram integration
│   │   └── metrics.py      # Performance tracking
│   ├── storage/            # Storage layer
│   │   └── s3_client.py    # MinIO/S3 client
│   ├── enrichment/         # AI enrichment pipeline
│   │   ├── llm_classifier.py      # Spam + OSINT classification
│   │   ├── entity_extractor.py    # Named entity recognition
│   │   ├── geo_extractor.py       # Geolocation extraction
│   │   ├── engagement_calculator.py  # Engagement metrics
│   │   └── orchestrator.py        # Enrichment coordinator
│   ├── api/                # REST API
│   │   ├── main.py         # FastAPI app
│   │   ├── routes/         # API endpoints
│   │   └── static/         # Dashboard files
│   └── __main__.py         # CLI entry point
├── alembic/                # Database migrations
├── tests/                  # Test suite
├── docs/                   # Documentation
├── pyproject.toml          # Project dependencies
├── docker-compose.yml      # Infrastructure setup
└── .env.example            # Environment template
```

## Features

### AI-Powered Classification

Every message is analyzed for:

- **Spam Detection**: Rule-based + LLM hybrid approach (>90% accuracy)
- **OSINT Value Score**: 0-100 scale indicating intelligence value
- **Topic Classification**: Automatic categorization (military, politics, humanitarian, etc.)
- **Sentiment Analysis**: Positive/negative/neutral detection

### Semantic Enrichment

Automatic extraction of:

- **Named Entities**: People, organizations, locations (via spaCy)
- **Military Units**: Custom patterns for military designations (93rd Brigade, etc.)
- **Geolocations**: Coordinates extracted from text with Ukraine region validation
- **Engagement Metrics**: 6 rates calculated from Telegram data

### Storage Optimization

- **Content-addressed storage**: SHA-256 based deduplication for media
- **JSONB fields**: Flexible enrichment data storage
- **Indexed search**: Fast queries on topics, entities, scores

### Developer API

RESTful endpoints for:

- `/api/search` - Query messages with filters (OSINT score, topics, dates, entities)
- `/api/media/{sha256}` - Retrieve media files
- `/api/metrics` - Performance statistics
- `/docs` - Interactive API documentation (Swagger UI)

## Environment Variables Reference

### Required

- `TELEGRAM_API_ID` - Get from https://my.telegram.org
- `TELEGRAM_API_HASH` - Get from https://my.telegram.org
- `TELEGRAM_PHONE` - Your phone number (with country code)
- `TOGETHER_API_KEY` - Get from https://together.ai
- `DATABASE_URL` - PostgreSQL connection string
- `MINIO_ENDPOINT` - MinIO server endpoint
- `MINIO_ACCESS_KEY` - MinIO access key
- `MINIO_SECRET_KEY` - MinIO secret key

### Optional

- `REDIS_URL` - Redis connection URL (default: `redis://localhost:6379`)
- `MINIO_BUCKET` - MinIO bucket name (default: `osint-archive`)
- `LOG_LEVEL` - Logging level (default: `INFO`)
- `TELEGRAM_SESSION_NAME` - Session file name (default: `osint_archive`)

## Development

### Run Tests

```bash
# Run all tests with coverage
pytest

# Run specific test file
pytest tests/test_config.py

# Run with verbose output
pytest -v
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
ruff src/ tests/

# Type checking
mypy src/
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## Troubleshooting

### Telegram Authentication Issues

If you get authentication errors:

1. Delete the session file: `rm osint_archive.session`
2. Run the archiver again and follow the authentication prompts
3. Check that your API ID and hash are correct

### Database Connection Issues

```bash
# Check if PostgreSQL is running
docker-compose ps

# View PostgreSQL logs
docker-compose logs postgres

# Test connection
psql postgresql://osint:osint_password@localhost:5432/osint_archive
```

### MinIO Connection Issues

```bash
# Check MinIO status
docker-compose ps

# Access MinIO console
# Open browser to: http://localhost:9001
# Login: minioadmin / minioadmin

# View MinIO logs
docker-compose logs minio
```

### spaCy Model Not Found

```bash
# Download the English model
python -m spacy download en_core_web_lg

# Verify installation
python -c "import spacy; nlp = spacy.load('en_core_web_lg'); print('OK')"
```

## Performance

Expected performance metrics:

- **Message Processing**: ~3 seconds per message (including all AI enrichment)
- **Spam Detection**: <100ms (rule-based stage)
- **LLM Classification**: ~2 seconds (Together.ai Llama 3.1 70B)
- **Entity Extraction**: ~200ms (spaCy)
- **Storage Savings**: 30-45% reduction via spam filtering + deduplication

## License

MIT License - see LICENSE file for details

## Contributing

This is a proof-of-concept for demonstration purposes. Contributions, issues, and feature requests are welcome.

## Acknowledgments

- Built on patterns from [Telepathy](https://github.com/jordanwildon/Telepathy) for engagement metrics
- Uses [Telethon](https://docs.telethon.dev/) for Telegram integration
- Powered by [Together.ai](https://together.ai) for LLM inference
- NER powered by [spaCy](https://spacy.io/)

## Contact

For questions or feedback, please open an issue on GitHub.
