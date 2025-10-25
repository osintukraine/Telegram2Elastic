# Production Architecture: OSINT Intelligence Platform

**Last Updated:** 2025-10-25
**Status:** Design Document for Production System
**Context:** Based on PoC implementation + comprehensive user feedback

---

## Executive Summary

### What the PoC Proved

The proof-of-concept (Tasks 1.1-4.1) successfully demonstrated:

✅ **Real-time Telegram archiving** with Telethon
✅ **AI-powered classification** (LLM spam detection, OSINT value scoring 0-100)
✅ **Content-addressed storage** (SHA-256 deduplication via S3-compatible API)
✅ **Database-backed search** (PostgreSQL with semantic enrichment)
✅ **REST API** with filtering and pagination
✅ **S3-ready architecture** (MinIO gateway → future B2/S3 migration)

### What Production Needs

The production system must address:

🔧 **Separated architecture** - Listener → Queue → Processors (scalable)
🔧 **Message routing** - Trigger words route to different tables/collections
🔧 **Production spam filter** - Integrate battle-tested `spam_filter.py`
🔧 **Advanced visualization** - Baserow/Airtable-style + timeline views
🔧 **Human enrichment** - Editable fields for analyst input
🔧 **Multi-topic scaling** - Easy addition of new conflicts (Iran, Israel/Palestine)
🔧 **Data sovereignty** - Self-hosted, open-source first
🔧 **Developer platform** - REST + GraphQL APIs

---

## Core Architectural Principles

### 1. Open-Source First

**Definition:** Choose the best freely available, self-hostable open-source components.

**Why:**
- Data sovereignty (no vendor lock-in)
- Cost control (no licensing fees)
- Transparency (auditable code)
- Community support (proven at scale)

**Evaluation Criteria:**
- ✅ OSI-approved license (MIT, Apache 2.0, GPL)
- ✅ Active maintenance (commits in last 3 months)
- ✅ Production-ready (1.0+ release, used by >100 orgs)
- ✅ Self-hostable (no cloud-only dependencies)
- ✅ Good documentation (examples, API reference)

### 2. Data Sovereignty

**Definition:** Complete control over where data lives and who accesses it.

**Requirements:**
- All data stored on infrastructure you control (Hetzner, own servers)
- No mandatory cloud services (optional S3 as backend only)
- Open APIs (data export at any time)
- No tracking/telemetry to third parties
- Encryption at rest (PostgreSQL pgcrypto, MinIO encryption)

**Why:** OSINT data is sensitive; researchers need guarantees about privacy and access.

### 3. Scalability

**Definition:** Add new topics/channels with minimal effort and cost.

**Current System Pain Points:**
- Adding new topic = new SQLite DB + new static site + new storage box
- Takes weeks of setup
- Linear cost increase

**Production Solution:**
- Add topic = new row in `archives` table
- Reuse existing infrastructure
- Minimal marginal cost
- Minutes of setup

### 4. Maintainability

**Definition:** System that's easy to understand, debug, and evolve.

**Requirements:**
- Clear separation of concerns (listener ≠ processor ≠ storage)
- Modern codebase (Python 3.11+, typed, documented)
- Automated testing (>80% coverage)
- Observability (logs, metrics, tracing)
- Developer-friendly (Docker Compose, clear docs)

---

## Production System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TELEGRAM SOURCES                             │
│         (100+ channels, multiple topics/conflicts)                  │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    TELEGRAM LISTENER SERVICE                        │
│  • Lightweight (just receives messages)                             │
│  • Multiple sessions (one per funnel account)                       │
│  • Pushes to Redis queue                                            │
│  • No processing logic                                              │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       REDIS MESSAGE QUEUE                           │
│  • Streams (ordered, persistent)                                    │
│  • Consumer groups (multiple processors)                            │
│  • Dead letter queue (failed messages)                              │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   PROCESSOR WORKER POOL (N instances)               │
│                                                                     │
│  Worker 1 ────┐                                                    │
│  Worker 2 ────┤  Each worker:                                      │
│  Worker 3 ────┤  1. Fetch message from queue                       │
│  Worker N ────┘  2. Run spam filter (production rules)             │
│                  3. If not spam: download media, LLM classify       │
│                  4. Extract entities, geolocations                  │
│                  5. Calculate engagement metrics                    │
│                  6. Route to appropriate storage                    │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│                     STORAGE ROUTER                                  │
│  • Trigger word matching                                            │
│  • Route to specialized tables:                                     │
│    - messages_combat                                                │
│    - messages_civilian                                              │
│    - messages_diplomatic                                            │
│    - messages_equipment                                             │
│    - messages_general (fallback)                                    │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│                  STORAGE LAYER                                      │
│                                                                     │
│  ┌─────────────────────┐      ┌──────────────────────────────────┐│
│  │   PostgreSQL 16     │      │  MinIO (S3-Compatible)           ││
│  │                     │      │                                  ││
│  │ • 5+ message tables │      │ • Content-addressed media        ││
│  │ • Semantic metadata │◄─────┤ • Deduplication (SHA-256)        ││
│  │ • Full-text search  │      │ • Lifecycle policies             ││
│  │ • JSONB enrichment  │      │ • Migration path to B2/S3        ││
│  └─────────────────────┘      └──────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       API LAYER                                     │
│                                                                     │
│  ┌────────────────┐          ┌─────────────────────────────────┐  │
│  │  REST API      │          │  GraphQL API                    │  │
│  │  (FastAPI)     │          │  (Strawberry GraphQL)           │  │
│  │                │          │                                 │  │
│  │ • Search       │          │ • Flexible queries              │  │
│  │ • Filters      │          │ • Batching                      │  │
│  │ • Media serve  │          │ • Real-time subscriptions       │  │
│  │ • Export (CSV) │          │ • Developer-friendly            │  │
│  └────────────────┘          └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    FRONTEND APPLICATIONS                            │
│                                                                     │
│  ┌──────────────────┐  ┌───────────────────┐  ┌─────────────────┐ │
│  │ Individual Post  │  │ Table View        │  │ Timeline View   │ │
│  │ View             │  │ (Baserow-style)   │  │ (Year/Month/Day)│ │
│  │                  │  │                   │  │                 │ │
│  │ • Translation    │  │ • Inline editing  │  │ • Filtering     │ │
│  │ • Media gallery  │  │ • Sorting         │  │ • Drill-down    │ │
│  │ • Metadata       │  │ • Filtering       │  │ • Statistics    │ │
│  │ • Enrichment     │  │ • Bulk actions    │  │ • Trends        │ │
│  │ • Human input    │  │ • Export          │  │ • Heatmaps      │ │
│  └──────────────────┘  └───────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Telegram Listener Service

**Purpose:** Receive messages from Telegram, push to queue, nothing else.

**Technology:**
- **Telethon** (proven, mature Telegram client)
- **aioredis** (async Redis client for queue push)
- **Python 3.11+** with asyncio

**Architecture:**

```python
# listener/main.py

from telethon import TelegramClient, events
from aioredis import Redis

class TelegramListener:
    """Lightweight listener - just receives and queues."""

    def __init__(self, session_name: str, redis: Redis):
        self.client = TelegramClient(session_name, API_ID, API_HASH)
        self.redis = redis

    async def start(self):
        """Start listening to configured channels."""
        @self.client.on(events.NewMessage(chats=self.channels))
        async def handler(event):
            # Serialize message to JSON
            message_data = serialize_telegram_message(event.message)

            # Push to Redis stream
            await self.redis.xadd(
                'telegram:messages',
                {'data': json.dumps(message_data)},
                maxlen=100000  # Keep last 100k messages
            )

            logger.info(f"Queued message {event.message.id}")

        await self.client.run_until_disconnected()
```

**Key Design Decisions:**

1. **No processing logic** - Keep listener simple and fast
2. **Multiple instances** - One per funnel account (session isolation)
3. **Queue only** - Redis streams for ordered, persistent queue
4. **Graceful degradation** - If queue is down, buffer locally (SQLite)
5. **Health monitoring** - Expose /health endpoint (last message timestamp)

**Deployment:**
- Cloudron custom app (or Docker Compose)
- Restart policy: always
- Resource limits: 512MB RAM, 0.5 CPU
- Volume: `/data/sessions` (persistent Telegram sessions)

---

### 2. Redis Message Queue

**Purpose:** Reliable, ordered, persistent message queue between listener and processors.

**Technology:** **Redis 7+ with Streams**

**Why Redis Streams (not lists/pub-sub):**
- ✅ **Ordered** (guaranteed message order per channel)
- ✅ **Persistent** (survives restarts)
- ✅ **Consumer groups** (multiple processors, automatic distribution)
- ✅ **Acknowledgment** (retry failed messages)
- ✅ **Dead letter queue** (handle poison messages)

**Stream Structure:**

```
Stream: telegram:messages
│
├─ Message 1: {data: {channel_id, message_id, text, media_url, ...}}
├─ Message 2: {data: {...}}
├─ Message 3: {data: {...}}
```

**Consumer Group:**

```bash
# Create consumer group
XGROUP CREATE telegram:messages processor-workers $ MKSTREAM

# Processors read from group
XREADGROUP GROUP processor-workers worker-1 COUNT 10 BLOCK 5000 STREAMS telegram:messages >
```

**Configuration:**

```yaml
# redis.conf
maxmemory 4gb
maxmemory-policy allkeys-lru
stream-node-max-entries 1000
```

**Dead Letter Queue:**

```python
# If message fails 3 times, move to DLQ
async def process_message(msg_id, msg_data):
    try:
        await process(msg_data)
        await redis.xack('telegram:messages', 'processor-workers', msg_id)
    except Exception as e:
        retry_count = await redis.hincrby(f'msg:{msg_id}:retries', 'count', 1)
        if retry_count >= 3:
            # Move to dead letter queue
            await redis.xadd('telegram:dlq', {'data': msg_data, 'error': str(e)})
            await redis.xack('telegram:messages', 'processor-workers', msg_id)
        else:
            # Will be retried by another worker
            logger.warning(f"Message {msg_id} failed (retry {retry_count}/3)")
```

---

### 3. Processor Worker Pool

**Purpose:** CPU/IO-intensive processing of messages (spam filtering, LLM calls, entity extraction).

**Technology:**
- **Python 3.11+** with asyncio
- **Celery** (alternative: plain workers with Redis consumer groups)
- **Together.ai** (LLM classification)
- **spaCy** (NER for production - upgrade from PoC regex)

**Worker Architecture:**

```python
# processor/worker.py

from aioredis import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from enrichment import SpamFilter, LLMClassifier, EntityExtractor
from storage import S3Client, MessageRouter

class ProcessorWorker:
    """Processes messages from queue, enriches, stores."""

    def __init__(self, worker_id: str, redis: Redis, db: AsyncSession):
        self.worker_id = worker_id
        self.redis = redis
        self.db = db

        # Initialize enrichment services
        self.spam_filter = SpamFilter()  # Production spam_filter.py
        self.llm_classifier = LLMClassifier()
        self.entity_extractor = EntityExtractor()  # spaCy-based
        self.s3_client = S3Client()
        self.router = MessageRouter()

    async def run(self):
        """Main worker loop."""
        while True:
            # Fetch batch of messages from Redis stream
            messages = await self.redis.xreadgroup(
                'processor-workers',
                self.worker_id,
                {'telegram:messages': '>'},
                count=10,
                block=5000
            )

            for stream, msg_list in messages:
                for msg_id, msg_data in msg_list:
                    try:
                        await self.process_message(msg_id, msg_data)
                    except Exception as e:
                        logger.error(f"Worker {self.worker_id} failed on {msg_id}: {e}")

    async def process_message(self, msg_id: str, msg_data: dict):
        """Process a single message."""
        # 1. Spam filter (production rules from telegram_translatorv3)
        spam_result = self.spam_filter.check(msg_data['text'])
        if spam_result.is_spam:
            # Mark as spam, skip expensive processing
            await self.store_spam(msg_data, spam_result.reasons)
            await self.redis.xack('telegram:messages', 'processor-workers', msg_id)
            return

        # 2. Download media (if present)
        media_keys = []
        if msg_data.get('media_urls'):
            media_keys = await self.download_and_upload_media(msg_data['media_urls'])

        # 3. LLM classification (OSINT value, topics, sentiment)
        classification = await self.llm_classifier.classify(msg_data['text'])

        # 4. Entity extraction (spaCy + custom military patterns)
        entities = await self.entity_extractor.extract(msg_data['text'])

        # 5. Engagement metrics (if available)
        engagement = calculate_engagement_metrics(msg_data)

        # 6. Route to appropriate table based on trigger words
        target_table = self.router.route(msg_data['text'], classification.topics)

        # 7. Store in PostgreSQL
        await self.store_message(
            msg_data,
            target_table=target_table,
            media_keys=media_keys,
            classification=classification,
            entities=entities,
            engagement=engagement
        )

        # 8. Acknowledge message
        await self.redis.xack('telegram:messages', 'processor-workers', msg_id)

        logger.info(f"Worker {self.worker_id} processed {msg_id} → {target_table}")
```

**Scaling:**

```bash
# Run N workers (automatically distribute load)
docker-compose up -d --scale processor-worker=8
```

**Resource Requirements:**
- **Per worker:** 2GB RAM, 1 CPU
- **Recommended:** 4-8 workers (depending on message volume)
- **Monitoring:** Track queue depth, processing rate, error rate

---

### 4. Production Spam Filter Integration

**Problem:** PoC uses simple regex patterns; production needs battle-tested filter.

**Solution:** Integrate existing `spam_filter.py` from `/home/rick/code/osintukraine/telegram_translatorv3/src/spam_filter.py`

**Integration:**

```python
# enrichment/spam_filter.py

from telegram_translatorv3.src.spam_filter import SpamFilter as ProductionSpamFilter

class SpamFilter:
    """Wrapper around production spam filter."""

    def __init__(self):
        # Load production spam patterns and rules
        self.filter = ProductionSpamFilter()

    def check(self, text: str, metadata: dict = None) -> SpamResult:
        """Check if message is spam using production rules."""
        result = self.filter.is_spam(text, metadata)

        return SpamResult(
            is_spam=result.spam,
            confidence=result.confidence,
            reasons=result.matched_patterns,
            filter_version=self.filter.version
        )
```

**Migration Strategy:**

1. **Copy production filter** to `poc/src/enrichment/spam_filter.py`
2. **Update patterns** - Add any new spam patterns discovered
3. **A/B test** - Compare PoC simple filter vs production filter
4. **Metrics** - Track false positives/negatives
5. **Iterate** - Improve patterns based on feedback

**Why Not LLM-Only Spam Detection?**

- **Cost:** LLM calls expensive at scale (1000s of messages/day)
- **Speed:** Rule-based filter is instant (<1ms)
- **Accuracy:** Production rules already >95% accurate
- **Fallback:** LLM can handle edge cases rule-based filter misses

**Two-Phase Approach:**

```
Phase 1: Rule-Based Filter (production spam_filter.py)
│
├─ Is spam? → Mark as spam, DONE (no LLM call)
│
└─ Not spam? → Phase 2 (LLM enrichment)
    │
    ├─ OSINT value scoring (0-100)
    ├─ Topic classification
    ├─ Sentiment analysis
    └─ Entity extraction (spaCy)
```

**This saves 80-90% of LLM costs** by filtering obvious spam upfront.

---

### 5. Message Routing System

**Purpose:** Route messages to specialized tables based on trigger words and topics.

**User Requirements:**
> "trigger words that would route the archived post to a different collection/table"

**Architecture:**

```python
# storage/router.py

class MessageRouter:
    """Routes messages to appropriate tables based on trigger words."""

    def __init__(self):
        # Load routing rules from config
        self.rules = load_routing_rules()

    def route(self, text: str, topics: list[str]) -> str:
        """Determine target table for message."""
        # Check trigger words (highest priority)
        for rule in self.rules:
            if any(trigger in text.lower() for trigger in rule.triggers):
                return rule.target_table

        # Fallback to topic-based routing
        if 'combat' in topics:
            return 'messages_combat'
        elif 'civilian' in topics:
            return 'messages_civilian'
        elif 'diplomatic' in topics:
            return 'messages_diplomatic'
        elif 'equipment' in topics:
            return 'messages_equipment'

        # Default fallback
        return 'messages_general'
```

**Routing Configuration** (YAML):

```yaml
# config/routing_rules.yaml

routing_rules:
  - name: combat_events
    description: "Combat-related messages (attacks, clashes, casualties)"
    priority: 1
    target_table: messages_combat
    triggers:
      - tank
      - artillery
      - drone
      - assault
      - casualties
      - killed
      - wounded
      - ЗСУ
      - ВСУ
      - russian forces

  - name: civilian_events
    description: "Civilian impact (shelling, humanitarian, infrastructure)"
    priority: 2
    target_table: messages_civilian
    triggers:
      - civilian
      - humanitarian
      - shelter
      - evacuation
      - shelling of
      - residential
      - school
      - hospital
      - мирні жителі

  - name: diplomatic_events
    description: "Diplomatic statements, sanctions, negotiations"
    priority: 3
    target_table: messages_diplomatic
    triggers:
      - sanctions
      - negotiations
      - statement from
      - ministry of
      - ambassador
      - UN
      - NATO
      - переговори

  - name: equipment_tracking
    description: "Military equipment deliveries, losses"
    priority: 4
    target_table: messages_equipment
    triggers:
      - HIMARS
      - Bradley
      - Leopard
      - F-16
      - delivered
      - destroyed
      - captured
      - озброєння

fallback:
  target_table: messages_general
  description: "Messages that don't match any specific category"
```

**Database Schema:**

```sql
-- Specialized tables (same structure, different data)

CREATE TABLE messages_combat (
    -- All fields from messages table
    -- + combat-specific enrichment
    combatants JSONB,  -- ["AFU", "Russian forces"]
    equipment_mentioned TEXT[],
    casualties_estimated JSONB  -- {killed: N, wounded: M}
);

CREATE TABLE messages_civilian (
    -- All fields from messages table
    -- + civilian-specific enrichment
    impact_type TEXT[],  -- ["shelling", "infrastructure"]
    affected_locations TEXT[],
    humanitarian_needs TEXT[]
);

CREATE TABLE messages_diplomatic (
    -- All fields from messages table
    -- + diplomatic-specific enrichment
    actors TEXT[],  -- ["Ukraine", "USA", "EU"]
    statement_type TEXT,  -- "sanctions", "negotiations"
    policy_area TEXT[]
);

CREATE TABLE messages_equipment (
    -- All fields from messages table
    -- + equipment-specific enrichment
    equipment_type TEXT[],  -- ["tank", "artillery"]
    action TEXT,  -- "delivered", "destroyed", "captured"
    quantity INTEGER
);

CREATE TABLE messages_general (
    -- All fields from messages table
    -- Default for uncategorized
);
```

**Benefits:**

1. **Specialized queries** - Query combat events without civilian noise
2. **Specialized enrichment** - Add domain-specific fields per table
3. **Performance** - Smaller tables = faster queries
4. **Flexibility** - Easy to add new categories (e.g., `messages_nuclear`)

**Alternative: Single Table with Routing Tag**

If multiple tables become complex, use single table with routing tag:

```sql
CREATE TABLE messages (
    -- All existing fields
    routing_category TEXT,  -- 'combat', 'civilian', 'diplomatic', 'equipment', 'general'
    INDEX idx_routing_category (routing_category)
);

-- Query becomes:
SELECT * FROM messages WHERE routing_category = 'combat';
```

**Recommendation:** Start with single table + routing tag (simpler), migrate to specialized tables if needed (performance).

---

### 6. Visualization Architecture

**User Requirements:**
> "how to vizualise the data... switch view : rows a bit like Baserow or airtable do, with filtering, advanced search, ability to have human enrichment of data"

> "but also, per year view, per month view, in which a search keyword or filter could be applied"

**Three Main Views:**

#### A. Individual Post View

**Purpose:** Deep dive into a single message with all enrichment.

**Features:**
- Translation (original + translated text)
- Media gallery (images, videos, documents)
- Complete metadata (date, channel, user, views, forwards, reactions)
- AI enrichment display (OSINT value, topics, entities, geolocations)
- Human enrichment form (editable fields for analyst input)
- Related messages (same topic, same entities)

**Technology:**
- **React** (component-based, proven)
- **TailwindCSS** (rapid styling)
- **React Query** (data fetching, caching)

**Component Structure:**

```tsx
// components/PostView.tsx

export function PostView({ messageId }: { messageId: number }) {
  const { data: message } = useQuery(['message', messageId], fetchMessage);

  return (
    <div className="post-view">
      {/* Header: Date, Channel, User */}
      <PostHeader message={message} />

      {/* Content: Text + Translation */}
      <PostContent text={message.text} translation={message.translated_text} />

      {/* Media Gallery */}
      {message.media_files && <MediaGallery files={message.media_files} />}

      {/* AI Enrichment (read-only) */}
      <EnrichmentPanel
        osintScore={message.osint_value_score}
        topics={message.topics}
        entities={message.entities}
        geolocations={message.geolocations}
      />

      {/* Human Enrichment (editable) */}
      <HumanEnrichmentForm
        messageId={messageId}
        initialValues={message.human_enrichment}
        onSave={saveHumanEnrichment}
      />

      {/* Related Messages */}
      <RelatedMessages messageId={messageId} />
    </div>
  );
}
```

**Human Enrichment Fields:**

```typescript
interface HumanEnrichment {
  verified: boolean;  // Analyst verified content
  importance: 'low' | 'medium' | 'high' | 'critical';
  notes: string;  // Analyst notes
  tags: string[];  // Custom tags
  fact_check_status: 'unchecked' | 'verified' | 'disputed' | 'false';
  related_incidents: number[];  // Links to other messages
  analyst_id: number;
  enriched_at: Date;
}
```

#### B. Table View (Baserow/Airtable-style)

**Purpose:** Spreadsheet-like view with inline editing, sorting, filtering.

**Features:**
- Configurable columns (show/hide fields)
- Inline editing (click to edit)
- Advanced filtering (multiple conditions)
- Sorting (multiple columns)
- Bulk actions (tag, export, delete)
- Export (CSV, JSON, Excel)
- Views (save filter/sort configurations)

**Technology:**
- **AG Grid React** (industry-standard data grid, open-source)
  - Why: 1M+ downloads/week, battle-tested, feature-rich
  - Features: Virtual scrolling, cell editing, advanced filters
  - License: MIT (free for all use)

**Alternative:** **TanStack Table** (lighter, more flexible)
  - Why: Modern, headless, TypeScript-first
  - Features: Virtualization, sorting, filtering
  - License: MIT

**Recommendation:** **AG Grid** (more features out-of-box)

**Component Structure:**

```tsx
// components/TableView.tsx

import { AgGridReact } from 'ag-grid-react';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

export function TableView({ tableType }: { tableType: string }) {
  const [columnDefs] = useState([
    {
      field: 'telegram_date',
      headerName: 'Date',
      sortable: true,
      filter: 'agDateColumnFilter',
      valueFormatter: params => formatDate(params.value)
    },
    {
      field: 'text',
      headerName: 'Message',
      sortable: false,
      filter: 'agTextColumnFilter',
      flex: 3,
      cellRenderer: 'textPreviewRenderer'
    },
    {
      field: 'osint_value_score',
      headerName: 'OSINT Value',
      sortable: true,
      filter: 'agNumberColumnFilter',
      cellStyle: params => ({
        backgroundColor: getScoreColor(params.value)
      })
    },
    {
      field: 'topics',
      headerName: 'Topics',
      sortable: true,
      filter: 'agSetColumnFilter',
      cellRenderer: 'tagsRenderer'
    },
    {
      field: 'human_enrichment.importance',
      headerName: 'Importance',
      sortable: true,
      filter: 'agSetColumnFilter',
      editable: true,  // Inline editing!
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: {
        values: ['low', 'medium', 'high', 'critical']
      }
    }
  ]);

  const { data: messages, refetch } = useQuery(
    ['messages', tableType],
    () => fetchMessages(tableType)
  );

  return (
    <div className="ag-theme-alpine" style={{ height: '800px', width: '100%' }}>
      <AgGridReact
        rowData={messages}
        columnDefs={columnDefs}
        defaultColDef={{
          resizable: true,
          sortable: true,
          filter: true
        }}
        pagination={true}
        paginationPageSize={100}
        enableRangeSelection={true}
        onCellValueChanged={handleCellEdit}
        rowSelection="multiple"
        suppressRowClickSelection={true}
      />
    </div>
  );
}
```

**Filtering UI:**

```tsx
// components/TableFilters.tsx

export function TableFilters({ onFilterChange }: Props) {
  return (
    <div className="filters">
      <DateRangePicker onChange={onFilterChange} />
      <MultiSelect
        label="Topics"
        options={['combat', 'civilian', 'diplomatic', 'equipment']}
        onChange={onFilterChange}
      />
      <Slider
        label="Min OSINT Score"
        min={0}
        max={100}
        onChange={onFilterChange}
      />
      <Toggle
        label="Has Media"
        onChange={onFilterChange}
      />
      <Toggle
        label="Human Verified"
        onChange={onFilterChange}
      />
    </div>
  );
}
```

#### C. Timeline Views (Year/Month/Day)

**Purpose:** Explore data chronologically with drill-down and statistics.

**Features:**
- Year view (heatmap of activity per day)
- Month view (daily activity bars)
- Day view (hourly activity timeline)
- Global filters (apply to all views)
- Statistics (total messages, OSINT score distribution)
- Trends (engagement over time, topic shifts)

**Technology:**
- **Recharts** (React charting library)
  - Why: Simple, composable, responsive
  - License: MIT
- **D3.js** (for complex custom visualizations)
  - Why: Industry standard, maximum flexibility
  - License: ISC (permissive)

**Recommendation:** **Recharts** (simpler) + **D3.js** (advanced features)

**Component Structure:**

```tsx
// components/TimelineView.tsx

export function TimelineView({ level }: { level: 'year' | 'month' | 'day' }) {
  const { data: stats } = useQuery(['timeline', level], () => fetchTimelineStats(level));

  if (level === 'year') {
    return (
      <div className="timeline-year">
        <HeatmapCalendar data={stats.daily_counts} onDayClick={drillDownToDay} />
        <StatsSummary stats={stats.summary} />
      </div>
    );
  }

  if (level === 'month') {
    return (
      <div className="timeline-month">
        <BarChart data={stats.daily_counts}>
          <Bar dataKey="count" fill="#8884d8" />
          <Tooltip content={<DayTooltip />} />
          <XAxis dataKey="date" />
          <YAxis />
        </BarChart>
        <TopicsDistribution data={stats.topics} />
      </div>
    );
  }

  if (level === 'day') {
    return (
      <div className="timeline-day">
        <TimelineEvents events={stats.hourly_events} />
        <EngagementTrends data={stats.engagement} />
      </div>
    );
  }
}
```

**Heatmap Calendar** (Year View):

```tsx
// components/HeatmapCalendar.tsx

import CalendarHeatmap from 'react-calendar-heatmap';
import 'react-calendar-heatmap/dist/styles.css';

export function HeatmapCalendar({ data, onDayClick }: Props) {
  return (
    <CalendarHeatmap
      startDate={new Date('2022-01-01')}
      endDate={new Date('2025-12-31')}
      values={data.map(d => ({
        date: d.date,
        count: d.message_count
      }))}
      classForValue={value => {
        if (!value) return 'color-empty';
        if (value.count > 100) return 'color-scale-4';
        if (value.count > 50) return 'color-scale-3';
        if (value.count > 20) return 'color-scale-2';
        return 'color-scale-1';
      }}
      tooltipDataAttrs={value => ({
        'data-tip': `${value.date}: ${value.count} messages`
      })}
      onClick={value => onDayClick(value.date)}
    />
  );
}
```

**Global Filtering:**

All views share same filter state:

```tsx
// hooks/useGlobalFilters.ts

export function useGlobalFilters() {
  const [filters, setFilters] = useAtom(filtersAtom);  // Jotai state

  return {
    filters,
    setDateRange: (start, end) => setFilters({ ...filters, dateRange: [start, end] }),
    setTopics: topics => setFilters({ ...filters, topics }),
    setMinScore: score => setFilters({ ...filters, minOsintScore: score }),
    clearFilters: () => setFilters(DEFAULT_FILTERS)
  };
}
```

**Frontend Architecture Summary:**

```
Frontend/
├── components/
│   ├── PostView/
│   │   ├── PostView.tsx
│   │   ├── PostHeader.tsx
│   │   ├── PostContent.tsx
│   │   ├── MediaGallery.tsx
│   │   ├── EnrichmentPanel.tsx
│   │   └── HumanEnrichmentForm.tsx
│   ├── TableView/
│   │   ├── TableView.tsx (AG Grid)
│   │   ├── TableFilters.tsx
│   │   ├── CellRenderers.tsx
│   │   └── BulkActions.tsx
│   └── TimelineView/
│       ├── TimelineView.tsx
│       ├── HeatmapCalendar.tsx
│       ├── TimelineEvents.tsx
│       └── EngagementTrends.tsx
├── hooks/
│   ├── useGlobalFilters.ts
│   ├── useMessages.ts
│   └── useEnrichment.ts
├── api/
│   ├── client.ts (REST + GraphQL clients)
│   └── queries.ts (React Query hooks)
└── state/
    └── atoms.ts (Jotai atoms for global state)
```

---

### 7. Technology Stack Recommendations

**Core Principle:** Open-source first, self-hostable, production-ready.

#### Backend

| Component | Recommendation | Alternatives | Why |
|-----------|---------------|--------------|-----|
| **API Framework** | FastAPI | Flask, Django REST | Modern, async, auto-docs, type hints |
| **Database** | PostgreSQL 16 | MySQL, MariaDB | JSONB, full-text search, mature |
| **Message Queue** | Redis 7 Streams | RabbitMQ, Kafka | Simple, fast, persistent streams |
| **Object Storage** | MinIO | SeaweedFS | S3-compatible, proven, easy migration |
| **ORM** | SQLAlchemy 2.0 | Tortoise, Peewee | Industry standard, async support |
| **Task Queue** | Redis + workers | Celery, Dramatiq | Simpler than Celery for our use case |
| **Cache** | Redis | Memcached | Multi-purpose (cache + queue + sessions) |

#### Frontend

| Component | Recommendation | Alternatives | Why |
|-----------|---------------|--------------|-----|
| **Framework** | React 18 | Vue 3, Svelte | Ecosystem, AG Grid support, hiring |
| **State Management** | Jotai | Zustand, Redux | Simple, atomic, TypeScript-first |
| **Data Fetching** | React Query | SWR, Apollo | Cache management, auto-refetch |
| **UI Components** | Shadcn/UI | Material-UI, Ant Design | Tailwind-based, customizable, free |
| **Data Grid** | AG Grid Community | TanStack Table | Feature-rich, MIT license |
| **Charts** | Recharts + D3 | Chart.js, ApexCharts | React-native, composable |
| **Forms** | React Hook Form | Formik | Performance, small bundle |
| **Styling** | TailwindCSS | CSS Modules, Styled-components | Rapid development, consistency |

#### APIs

| Component | Recommendation | Alternatives | Why |
|-----------|---------------|--------------|-----|
| **REST API** | FastAPI | Django REST, Flask-RESTX | Already using FastAPI |
| **GraphQL** | Strawberry GraphQL | Graphene, Ariadne | FastAPI integration, dataclasses |
| **API Docs** | OpenAPI (built-in) | Swagger UI, Redoc | Auto-generated from FastAPI |
| **Rate Limiting** | slowapi | Flask-Limiter | FastAPI-compatible |
| **Authentication** | OAuth2 + JWT | Basic Auth, API Keys | Industry standard, secure |

#### DevOps

| Component | Recommendation | Alternatives | Why |
|-----------|---------------|--------------|-----|
| **Deployment** | Docker Compose | Kubernetes | Simpler for single-server, Cloudron-friendly |
| **Reverse Proxy** | Caddy | nginx, Traefik | Auto HTTPS, simple config |
| **Monitoring** | Prometheus + Grafana | Datadog, New Relic | Open-source, self-hosted, proven |
| **Logging** | Loki + Grafana | ELK stack | Simpler than Elasticsearch |
| **Tracing** | Jaeger | Zipkin, Tempo | CNCF project, battle-tested |
| **Secrets** | Cloudron env vars | Vault, SOPS | Simpler for Cloudron deployment |

#### AI/ML

| Component | Recommendation | Alternatives | Why |
|-----------|---------------|--------------|-----|
| **LLM API** | Together.ai | OpenAI, Anthropic | Open models, cheaper, no lock-in |
| **NER** | spaCy | StanfordNLP, Stanza | Fast, production-ready, GPU optional |
| **Embeddings** | sentence-transformers | OpenAI embeddings | Self-hosted, free, no API costs |
| **Vector DB** | pgvector (PostgreSQL) | Qdrant, Weaviate | One less service, proven |

**Deployment Architecture:**

```yaml
# docker-compose.production.yml

services:
  # Backend
  api:
    image: osint-platform/api:latest
    depends_on: [postgres, redis, minio]
    environment:
      DATABASE_URL: postgresql://...
      REDIS_URL: redis://...
      S3_ENDPOINT: http://minio:9000

  # Telegram listener
  listener:
    image: osint-platform/listener:latest
    depends_on: [redis]
    volumes:
      - ./data/sessions:/data/sessions

  # Processor workers (scale to N)
  processor:
    image: osint-platform/processor:latest
    depends_on: [postgres, redis, minio]
    deploy:
      replicas: 4

  # Frontend
  frontend:
    image: osint-platform/frontend:latest
    depends_on: [api]

  # Infrastructure
  postgres:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  minio:
    image: minio/minio:latest
    volumes:
      - /mnt/hetzner-box:/data

  # Observability
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    depends_on: [prometheus]
    volumes:
      - grafana_data:/var/lib/grafana

  loki:
    image: grafana/loki:latest
    volumes:
      - loki_data:/loki

volumes:
  postgres_data:
  redis_data:
  grafana_data:
  loki_data:
```

---

### 8. Repository Migration Strategy

**Current Situation:**
- PoC in `/home/rick/code/Telegram2Elastic/poc/`
- Zero code shared with parent repo
- Essentially a new project

**User Concern:**
> "I'm wondering if all this work, shouldn't be moved to a complete new repo"

**Answer:** **YES, create new repository AFTER PoC is complete.**

**Why Wait?**
- PoC is nearly done (9/15 tasks complete)
- Use PoC for funding pitch
- Clean slate for production with lessons learned

**New Repository Structure:**

```
osint-intelligence-platform/
├── README.md
├── LICENSE (MIT or GPL-3.0)
├── ARCHITECTURE.md (this document)
├── CONTRIBUTING.md
├── docker-compose.yml
├── docker-compose.production.yml
│
├── services/
│   ├── listener/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── src/
│   │       ├── __main__.py
│   │       └── telegram_listener.py
│   ├── processor/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── src/
│   │       ├── __main__.py
│   │       ├── worker.py
│   │       └── enrichment/
│   │           ├── spam_filter.py (production)
│   │           ├── llm_classifier.py
│   │           └── entity_extractor.py (spaCy)
│   ├── api/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── src/
│   │       ├── __main__.py
│   │       ├── rest/ (FastAPI)
│   │       └── graphql/ (Strawberry)
│   └── frontend/
│       ├── Dockerfile
│       ├── package.json
│       └── src/
│           ├── components/
│           ├── hooks/
│           └── api/
│
├── shared/
│   └── python/
│       ├── models.py (SQLAlchemy models)
│       ├── config.py (shared config)
│       └── storage.py (S3 client)
│
├── infrastructure/
│   ├── postgres/
│   │   └── init.sql
│   ├── redis/
│   │   └── redis.conf
│   ├── prometheus/
│   │   └── prometheus.yml
│   └── grafana/
│       └── dashboards/
│
├── migrations/
│   └── alembic/
│       └── versions/
│
├── scripts/
│   ├── create_session.py
│   ├── migrate_from_sqlite.py
│   └── cleanup_spam.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
└── docs/
    ├── API.md
    ├── DEPLOYMENT.md
    ├── DEVELOPMENT.md
    └── USER_GUIDE.md
```

**Repository Name Ideas:**
- `osint-intelligence-platform` (descriptive)
- `telegram-osint-archive` (specific)
- `semantic-osint-platform` (emphasizes AI)
- `osint-archive-pro` (marketing-friendly)

**Migration Checklist:**

- [ ] Create new GitHub repository
- [ ] Copy PoC code to new structure
- [ ] Update documentation (README, ARCHITECTURE)
- [ ] Set up CI/CD (GitHub Actions)
- [ ] Configure branch protection (main branch)
- [ ] Add issue templates
- [ ] Create CONTRIBUTING.md
- [ ] Choose license (MIT recommended for funding appeal)
- [ ] Create project board for production roadmap
- [ ] Invite collaborators (if applicable)

**Development Workflow:**

```
main (production)
│
├── develop (integration branch)
│   │
│   ├── feature/telegram-listener-improvements
│   ├── feature/spam-filter-update
│   ├── feature/graphql-api
│   └── feature/timeline-visualization
│
└── hotfix/critical-bug-fix
```

**Branching Strategy:** GitHub Flow (simpler than Git Flow)
- `main` = production-ready
- Feature branches → PR → review → merge
- Tag releases: `v0.1.0`, `v0.2.0`, etc.

---

### 9. GraphQL API Design

**Why GraphQL (in addition to REST)?**

- ✅ **Flexible queries** - Fetch exactly what frontend needs
- ✅ **Batching** - Single request for multiple resources
- ✅ **Type safety** - Auto-generated TypeScript types
- ✅ **Real-time** - Subscriptions for live updates
- ✅ **Developer-friendly** - GraphQL Playground for exploration

**Technology:** **Strawberry GraphQL**
- Why: FastAPI integration, dataclasses-based, modern
- License: MIT

**Schema:**

```python
# api/graphql/schema.py

import strawberry
from typing import Optional, List
from datetime import datetime

@strawberry.type
class Message:
    id: int
    text: str
    translated_text: Optional[str]
    telegram_date: datetime
    osint_value_score: Optional[float]
    topics: List[str]
    entities: Optional[strawberry.scalars.JSON]
    media_files: List['MediaFile']
    human_enrichment: Optional['HumanEnrichment']

@strawberry.type
class MediaFile:
    id: int
    sha256: str
    s3_key: str
    file_size: int
    mime_type: str
    url: str  # Signed URL for download

@strawberry.type
class HumanEnrichment:
    verified: bool
    importance: str
    notes: str
    tags: List[str]
    fact_check_status: str

@strawberry.input
class MessageFilter:
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    min_osint_score: Optional[float] = None
    topics: Optional[List[str]] = None
    has_media: Optional[bool] = None
    verified_only: Optional[bool] = None

@strawberry.type
class Query:
    @strawberry.field
    async def messages(
        self,
        filter: Optional[MessageFilter] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Message]:
        """Fetch messages with flexible filtering."""
        return await fetch_messages(filter, limit, offset)

    @strawberry.field
    async def message(self, id: int) -> Optional[Message]:
        """Fetch a single message by ID."""
        return await fetch_message_by_id(id)

    @strawberry.field
    async def timeline_stats(
        self,
        level: str,  # 'year', 'month', 'day'
        date: datetime
    ) -> TimelineStats:
        """Fetch timeline statistics for visualization."""
        return await fetch_timeline_stats(level, date)

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def update_human_enrichment(
        self,
        message_id: int,
        enrichment: HumanEnrichmentInput
    ) -> Message:
        """Update human enrichment for a message."""
        return await update_enrichment(message_id, enrichment)

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def new_messages(
        self,
        filter: Optional[MessageFilter] = None
    ) -> Message:
        """Subscribe to new messages in real-time."""
        async for message in message_stream(filter):
            yield message

schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)
```

**Integration with FastAPI:**

```python
# api/main.py

from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

app = FastAPI()

# REST API routes
app.include_router(rest_router, prefix="/api/v1")

# GraphQL endpoint
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")
```

**Example Queries:**

```graphql
# Fetch messages with entities and media
query GetEnrichedMessages {
  messages(
    filter: {
      minOsintScore: 70,
      topics: ["combat"],
      hasMedia: true
    },
    limit: 10
  ) {
    id
    text
    osintValueScore
    entities {
      militaryUnits
      locations
    }
    mediaFiles {
      url
      mimeType
    }
  }
}

# Update human enrichment
mutation UpdateEnrichment {
  updateHumanEnrichment(
    messageId: 123,
    enrichment: {
      verified: true,
      importance: "high",
      notes: "Confirmed by multiple sources"
    }
  ) {
    id
    humanEnrichment {
      verified
      importance
    }
  }
}

# Subscribe to new high-value messages
subscription HighValueMessages {
  newMessages(filter: { minOsintScore: 80 }) {
    id
    text
    osintValueScore
    topics
  }
}
```

**Frontend Integration:**

```typescript
// api/graphql.ts

import { GraphQLClient } from 'graphql-request';
import { useQuery, useMutation } from '@tanstack/react-query';

const client = new GraphQLClient('/graphql');

export function useMessages(filter: MessageFilter) {
  return useQuery(['messages', filter], async () => {
    const { messages } = await client.request(GET_MESSAGES_QUERY, { filter });
    return messages;
  });
}

export function useUpdateEnrichment() {
  return useMutation(async ({ messageId, enrichment }) => {
    const { updateHumanEnrichment } = await client.request(
      UPDATE_ENRICHMENT_MUTATION,
      { messageId, enrichment }
    );
    return updateHumanEnrichment;
  });
}
```

---

### 10. Data Sovereignty & Privacy

**Principles:**

1. **Data stays under your control**
   - No mandatory cloud services
   - No telemetry to third parties
   - Open-source components only

2. **Transparent data handling**
   - Document what data is collected
   - Document how it's processed
   - Document who can access it

3. **Export capabilities**
   - Full database dumps
   - CSV/JSON/Parquet export via API
   - No vendor lock-in

4. **Encryption**
   - At rest: PostgreSQL pgcrypto for sensitive fields
   - In transit: HTTPS/TLS everywhere
   - S3: MinIO encryption (optional)

**Implementation:**

```python
# models.py - Encrypted fields

from sqlalchemy_utils import EncryptedType
from sqlalchemy_utils.types.encrypted.encrypted_type import AesEngine

class Archive(Base):
    __tablename__ = "archives"

    # Sensitive fields encrypted
    telegram_session_string = Column(
        EncryptedType(String, settings.encryption_key, AesEngine, 'pkcs5')
    )
    api_credentials = Column(
        EncryptedType(JSONB, settings.encryption_key, AesEngine, 'pkcs5')
    )
```

**Configuration:**

```yaml
# config/data_governance.yaml

data_sovereignty:
  storage_location: "Hetzner Finland" (EU jurisdiction)
  backup_location: "On-premise" (your infrastructure)
  cloud_services:
    allowed:
      - Together.ai (LLM API only, no data stored)
      - Backblaze B2 (optional, S3-compatible, no vendor lock-in)
    forbidden:
      - AWS (except S3 API via MinIO)
      - Google Cloud Platform
      - Azure

privacy:
  pii_handling:
    - Telegram user IDs: stored (necessary for deduplication)
    - Usernames: stored (public data)
    - Phone numbers: NEVER stored
    - Analyst identities: encrypted

  data_retention:
    messages: indefinite (historical archive)
    media: indefinite
    logs: 90 days
    sessions: encrypted, persistent

  access_control:
    api_access: OAuth2 + JWT (self-hosted)
    admin_access: SSH keys only (no passwords)
    database_access: IP whitelist + encrypted connections

export:
  formats: [CSV, JSON, Parquet, SQL dump]
  frequency: on-demand via API
  full_export: available at any time
```

---

## Migration from Current System

### Phase 1: Parallel Operation (Month 1-3)

**Goal:** Run new system alongside old system, no disruption.

**Steps:**

1. **Deploy production infrastructure**
   - PostgreSQL, Redis, MinIO on Cloudron
   - Telegram listener (new session, separate from old)
   - Start archiving NEW messages only

2. **Validate new system**
   - Compare message counts (old vs new)
   - Verify media download/upload works
   - Test enrichment pipeline
   - Monitor for errors

3. **Build migration scripts**
   - SQLite → PostgreSQL (with progress tracking)
   - Hetzner filesystem → MinIO (rclone-based)
   - Preserve all metadata

### Phase 2: Historical Data Migration (Month 4-6)

**Goal:** Migrate 3 years of data without losing anything.

**Scripts:**

```python
# scripts/migrate_from_sqlite.py

from pathlib import Path
import sqlite3
from sqlalchemy import create_engine
from models import Archive, Message, MediaFile

async def migrate_archive(sqlite_path: Path, archive_id: int):
    """Migrate one SQLite database to PostgreSQL."""

    # Connect to SQLite
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    # Connect to PostgreSQL
    pg_engine = create_engine(DATABASE_URL)

    # Fetch messages from SQLite
    cursor = sqlite_conn.execute("SELECT * FROM messages ORDER BY id")

    batch = []
    for row in cursor:
        # Transform SQLite row to PostgreSQL model
        message = Message(
            archive_id=archive_id,
            message_id=row['message_id'],
            text=row['text'],
            telegram_date=parse_date(row['date']),
            # ... all fields
        )
        batch.append(message)

        # Bulk insert every 1000 messages
        if len(batch) >= 1000:
            await bulk_insert(pg_engine, batch)
            batch = []
            print(f"Migrated {cursor.rowcount} messages...")

    # Insert remaining
    if batch:
        await bulk_insert(pg_engine, batch)

    print(f"Migration complete: {cursor.rowcount} total messages")
```

**Media Migration:**

```bash
# scripts/migrate_media.sh

#!/bin/bash

# Migrate media from Hetzner boxes to MinIO
# Uses rclone for efficient parallel transfer

set -e

HETZNER_BOX_1="/mnt/hetzner-box1"
HETZNER_BOX_2="/mnt/hetzner-box2"
HETZNER_BOX_3="/mnt/hetzner-box3"
MINIO_BUCKET="telegram-archive"

echo "Starting media migration..."

# Configure rclone for MinIO
rclone config create minio s3 \
  provider=Minio \
  env_auth=false \
  access_key_id=$MINIO_ACCESS_KEY \
  secret_access_key=$MINIO_SECRET_KEY \
  endpoint=http://localhost:9000

# Sync Box 1 (2022 data)
echo "Migrating Box 1..."
rclone sync $HETZNER_BOX_1/ minio:$MINIO_BUCKET/2022/ \
  --transfers 16 \
  --checkers 32 \
  --progress \
  --stats 10s \
  --log-file migration-box1.log

# Sync Box 2 (2023 data)
echo "Migrating Box 2..."
rclone sync $HETZNER_BOX_2/ minio:$MINIO_BUCKET/2023/ \
  --transfers 16 \
  --checkers 32 \
  --progress \
  --stats 10s \
  --log-file migration-box2.log

# Sync Box 3 (2024-2025 data)
echo "Migrating Box 3..."
rclone sync $HETZNER_BOX_3/ minio:$MINIO_BUCKET/2024/ \
  --transfers 16 \
  --checkers 32 \
  --progress \
  --stats 10s \
  --log-file migration-box3.log

echo "Migration complete!"
```

### Phase 3: Spam Cleanup (Month 6-7)

**Goal:** Remove spam detected by production filter, reclaim storage.

```python
# scripts/cleanup_spam.py

async def cleanup_spam(year: int, dry_run: bool = True):
    """Scan and delete spam messages + media."""

    spam_filter = SpamFilter()  # Production filter

    # Fetch all messages from year
    messages = await db.query(Message).filter(
        extract('year', Message.telegram_date) == year
    ).all()

    spam_count = 0
    reclaimed_bytes = 0

    for msg in messages:
        # Check if spam
        result = spam_filter.check(msg.text)
        if result.is_spam:
            spam_count += 1

            # Calculate media size
            if msg.media_files:
                for media in msg.media_files:
                    reclaimed_bytes += media.file_size

                    if not dry_run:
                        # Delete from S3
                        await s3_client.delete_file(media.s3_key)

            if not dry_run:
                # Mark as spam in DB (don't delete, for audit)
                msg.is_spam = True
                msg.spam_reasons = result.reasons
                await db.commit()

    print(f"Year {year}:")
    print(f"  Spam messages: {spam_count} / {len(messages)} ({spam_count/len(messages)*100:.1f}%)")
    print(f"  Space reclaimed: {reclaimed_bytes / 1e9:.2f} GB")

    if dry_run:
        print("  (DRY RUN - no changes made)")
```

### Phase 4: Cutover (Month 7)

**Goal:** Switch from old system to new system.

**Steps:**

1. **Stop old tg-archive listeners**
2. **Verify new system capturing all messages**
3. **Update static sites to query new API** (optional)
4. **Decommission 2 Hetzner boxes** (save €80/month!)
5. **Announce to community** (if applicable)

---

## Deployment Scenarios

### Scenario A: Cloudron (Recommended)

**Advantages:**
- Managed PostgreSQL, Redis
- Automatic HTTPS, backups
- One-click updates
- User-friendly admin UI

**Cloudron App Structure:**

```
osint-platform.cloudronapp.io/
├── PostgreSQL (Cloudron managed)
├── Redis (Cloudron managed)
├── MinIO (custom Cloudron app)
├── API (custom Cloudron app)
├── Frontend (custom Cloudron app)
└── Listener (custom Cloudron app)
```

**Custom App Manifest:**

```json
{
  "id": "com.osintukraine.platform",
  "title": "OSINT Intelligence Platform",
  "version": "0.1.0",
  "manifestVersion": 2,
  "description": "Real-time Telegram intelligence platform with AI",
  "icon": "logo.png",
  "tags": ["osint", "telegram", "ai"],
  "website": "https://github.com/osintukraine/osint-platform",
  "addons": {
    "postgresql": {},
    "redis": {},
    "localstorage": {}
  },
  "tcpPorts": {
    "MINIO_PORT": {
      "description": "MinIO S3 API",
      "containerPort": 9000
    }
  }
}
```

### Scenario B: Docker Compose (Self-Hosted)

**Advantages:**
- Full control
- Lower cost (no Cloudron license)
- Portable (any Docker host)

**Deployment:**

```bash
# Production deployment
git clone https://github.com/osintukraine/osint-platform
cd osint-platform
cp .env.example .env
# Edit .env with production credentials
docker-compose -f docker-compose.production.yml up -d
```

### Scenario C: Kubernetes (Future Scalability)

**Advantages:**
- Auto-scaling
- High availability
- Multi-region

**When to use:** When message volume > 10k/day, or need multi-region deployment.

---

## Cost Projections (5 Years)

### Current System (Do Nothing)

```
Year 1-5: €170/month × 60 months = €10,200
Technical debt: Increasing
Scalability: Limited
API platform: Never
```

### Production System (Hetzner + MinIO)

```
Year 1:
  - Dev (Months 1-6): €170/month × 6 = €1,020
  - Production (Months 7-12): €90/month × 6 = €540
  Subtotal: €1,560

Years 2-5: €90/month × 48 months = €4,320

Total 5 years: €5,880
Savings vs current: €4,320 (42%)
```

### Production System (Backblaze B2, After Archive Tier)

```
Year 1-2: Same as Hetzner scenario = €1,560 + €1,080 = €2,640

Years 3-5 (with B2 Archive):
  - Hot (2TB): €10.80/month
  - Cold (8TB): €14.40/month
  - Cloudron: €50/month
  - Total: €75/month × 36 months = €2,700

Total 5 years: €5,340
Savings vs current: €4,860 (48%)
```

**Winner:** Hetzner + MinIO initially, migrate to B2 when Archive tier available.

---

## Success Metrics

### Technical Metrics

- ✅ **Uptime:** >99.5% (allows 3.6 hours downtime/month)
- ✅ **Message latency:** <5 seconds (listener → database)
- ✅ **Enrichment latency:** <3 seconds (LLM + NER + storage)
- ✅ **API response time:** <200ms (p95), <500ms (p99)
- ✅ **Spam detection accuracy:** >95% (reduce false positives)
- ✅ **Storage deduplication:** >30% (via content-addressing)

### User Metrics

- ✅ **Search time:** <5 seconds (find relevant intel)
- ✅ **API adoption:** >10 developers using API (first 6 months)
- ✅ **Data exports:** >100 exports/month (researchers using data)
- ✅ **Human enrichment:** >500 messages enriched by analysts (first 3 months)

### Business Metrics

- ✅ **Cost savings:** €80/month (immediately after consolidation)
- ✅ **New topics:** Add 3 new conflicts (Iran, Israel/Palestine, USA) without infrastructure cost
- ✅ **Funding secured:** €X investment (based on PoC demo)
- ✅ **Community growth:** >50 GitHub stars, >5 contributors

---

## Open Questions & Future Enhancements

### Open Questions

1. **Multi-language support?** - Currently focused on Ukrainian/Russian, but Iran/Israel/Palestine need Arabic/Hebrew/Farsi
2. **User authentication?** - Should API be public or require auth? (OAuth2 recommended)
3. **Rate limiting?** - Prevent abuse while allowing research (10 req/sec per user?)
4. **Data retention?** - Archive indefinitely or auto-delete old low-value messages?
5. **Backups?** - Daily PostgreSQL dumps to Backblaze? (€5/month for 1TB backups)

### Future Enhancements (Post-PoC)

**Phase 1 Enhancements (Months 1-6):**
- [ ] GraphQL API with subscriptions
- [ ] Advanced visualization (Baserow-style table view)
- [ ] Timeline views (year/month/day)
- [ ] Human enrichment UI
- [ ] Production spam filter integration
- [ ] spaCy-based NER (upgrade from regex)

**Phase 2 Enhancements (Months 7-12):**
- [ ] Network analysis (forward chains, influence metrics)
- [ ] Engagement metrics (6 rates from Telepathy)
- [ ] Geolocation visualization (map view)
- [ ] Multi-language support (Arabic, Hebrew, Farsi)
- [ ] User authentication (OAuth2 + JWT)
- [ ] Python/JavaScript SDKs

**Phase 3 Enhancements (Year 2):**
- [ ] Sentiment analysis (per message, trends over time)
- [ ] Topic clustering (automatic discovery of emerging topics)
- [ ] Anomaly detection (unusual activity patterns)
- [ ] Collaboration features (shared annotations, comments)
- [ ] Export API (scheduled exports, webhooks)
- [ ] Mobile app (iOS/Android, read-only)

**Advanced Features (Year 3+):**
- [ ] Graph database integration (Neo4j for network analysis)
- [ ] Vector search (semantic similarity via pgvector)
- [ ] ML model training (custom OSINT classifiers)
- [ ] Multi-modal analysis (image OCR, video transcription)
- [ ] Federated search (query multiple OSINT sources)
- [ ] Blockchain archiving (immutable audit trail)

---

## Conclusion

This production architecture addresses all user feedback:

✅ **Separated architecture** - Listener → Queue → Processors
✅ **Message routing** - Trigger words to specialized tables
✅ **Production spam filter** - Integrate battle-tested code
✅ **Advanced visualization** - Baserow-style + timeline views
✅ **Human enrichment** - Editable fields for analysts
✅ **Open-source first** - All components self-hostable
✅ **Data sovereignty** - Complete control, no vendor lock-in
✅ **Developer platform** - REST + GraphQL APIs
✅ **Scalable** - Add topics in minutes, not weeks
✅ **Cost-effective** - €80/month savings, path to €90/month total

**Next Steps:**

1. ✅ **Complete PoC** (almost done!)
2. **Demo for funding** (use PoC to secure investment)
3. **Create new repository** (osint-intelligence-platform)
4. **Begin production implementation** (following this architecture)
5. **Migrate historical data** (3 years of archives)
6. **Launch to community** (OSINT researchers, developers)

**This architecture transforms a fragmented collection of archives into a unified intelligence platform that scales to the next decade.**

Ready to build something extraordinary! 🚀
