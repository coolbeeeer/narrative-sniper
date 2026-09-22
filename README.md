# Narrative Sniper

Real-time narrative detection and trading dashboard for crypto markets.

## Architecture

```
narrative-sniper/
├── frontend/                 # Next.js 14 dashboard
│   ├── src/
│   │   ├── app/             # App router pages
│   │   │   ├── dashboard/   # Main dashboard
│   │   │   ├── narratives/  # Narrative details
│   │   │   ├── positions/   # Position management
│   │   │   └── pnl/         # PnL analytics
│   │   ├── components/      # React components
│   │   │   ├── ui/          # Base UI components
│   │   │   ├── charts/      # Recharts visualizations
│   │   │   ├── tables/      # Data tables
│   │   │   └── layout/      # Layout components
│   │   ├── hooks/           # React hooks (Zustand store)
│   │   ├── lib/             # Utilities, API client
│   │   ├── types/           # TypeScript types
│   │   └── styles/          # Global styles
│   ├── Dockerfile
│   ├── package.json
│   ├── tailwind.config.ts
│   └── next.config.js
├── backend/                  # FastAPI backend
│   ├── app/
│   │   ├── api/             # REST API routes
│   │   ├── core/            # Configuration
│   │   ├── ingestion/       # Twitter/Telegram/Discord/Helius
│   │   ├── intelligence/    # Embedding → Clustering → Labeling
│   │   ├── execution/       # Jupiter/Jito execution
│   │   ├── paper_trading/   # Paper trading engine
│   │   └── models/          # Pydantic models
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## Quick Start

### Development

```bash
# Start all services
docker-compose up -d

# Or run individually
cd frontend && npm install && npm run dev
cd backend && pip install -e ".[dev]" && uvicorn app.main:app --reload
```

### Production Build

```bash
docker-compose -f docker-compose.yml build
docker-compose up -d
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 3000 | Next.js dashboard |
| Backend API | 8000 | FastAPI REST + WebSocket |
| PostgreSQL | 5432 | Primary database |
| Redis | 6379 | Cache & queue |

## API Endpoints

### Narratives
- `GET /api/narratives` - List narratives (paginated)
- `GET /api/narratives/{id}` - Get narrative details

### Positions
- `GET /api/positions` - List positions
- `GET /api/positions/{id}` - Get position details

### PnL
- `GET /api/pnl/history?range=24h` - PnL history

### Status
- `GET /api/status/live` - Live system status
- `GET /api/config` - Current configuration
- `PATCH /api/config` - Update configuration

### WebSocket
- `WS /ws` - Real-time updates

## Configuration

Backend configuration via environment variables (`.env`):

```env
# API Keys
TWITTER_BEARER_TOKEN=
TELEGRAM_BOT_TOKEN=
DISCORD_BOT_TOKEN=
HELIUS_API_KEY=
JUPITER_API_KEY=
JITO_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Trading
PAPER_TRADING=true
MAX_POSITION_SIZE_USD=1000
MAX_DAILY_LOSS_USD=500
SLIPPAGE_BPS=100
PRIORITY_FEE_LAMPORTS=10000

# Intelligence
NARRATIVE_CONFIDENCE_THRESHOLD=0.6
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

## Intelligence Pipeline

1. **Ingestion** - Twitter, Telegram, Discord, Helius WebSocket
2. **Embedding** - sentence-transformers (all-MiniLM-L6-v2)
3. **Clustering** - HDBSCAN for narrative discovery
4. **Labeling** - LLM-based narrative labeling
5. **Scoring** - Confidence scoring & token extraction
6. **Detection** - New narrative alerts

## Execution Layer

- **Jupiter** - Swap routing & quotes
- **Jito** - MEV-protected bundle submission
- **Paper Trading** - Simulated execution for testing

## Frontend Stack

- Next.js 14 (App Router)
- React 18 + TypeScript
- Tailwind CSS + Copper accent theme
- Recharts for visualizations
- Zustand for state management
- Socket.io-client for WebSocket

## Backend Stack

- FastAPI + Uvicorn
- PostgreSQL + SQLAlchemy
- Redis for caching
- sentence-transformers + HDBSCAN
- Tweepy, Telethon, Discord.py
- Solana.py + Solders for on-chain

## CI/CD

GitHub Actions workflow:
1. Lint & type check (ruff, mypy, eslint)
2. Run tests (pytest, jest)
3. Build Docker images
4. Push to GHCR
5. Deploy to staging/production