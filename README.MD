# 🤖 Viha WhatsApp AI Sales Assistant — V2 RAG Agent

> A production-grade conversational AI sales agent that qualifies return gift leads on WhatsApp — collecting requirements naturally, searching products semantically, and handing off to humans at the right moment.

Built for **Viha Return Gifts**, a real Indian business selling return gifts for weddings, baby showers, corporate events and functions in Chennai.

---

## 🎯 What It Does

Customers message the WhatsApp number asking about return gifts. The AI agent:

1. **Greets** the customer warmly
2. **Collects** all 4 required fields naturally — quantity, budget, delivery location and timeline
3. **Never reveals prices** until all 4 fields are collected — filters out casual browsers
4. **Searches semantically** using RAG (pgvector + Jina embeddings) to find best matching products
5. **Sends product images** with name and price in caption — after requirement summary
6. **Hands off silently** to the human team — no message to customer, just wife gets alerted
7. **Stays silent** — bot never interferes after human takes over

The result: wife/staff only speaks to **qualified leads** with full context already collected.

---

## 🏗️ Architecture

```
Customer (WhatsApp)
        │
        ▼
Node.js Service (Baileys)          ← WhatsApp Web connection
        │  HTTP
        ▼
Python Service (FastAPI)           ← REST API
        │
        ▼
LangGraph Conversational Agent     ← AI brain
   ├── 1 Node (sales_agent)
   ├── 6 LangChain Tools
   └── PostgreSQL Checkpointer     ← Conversation persistence
        │
        ▼
Supabase (PostgreSQL + pgvector)   ← Leads + auth + state + embeddings
        │
        ▼
Jina AI Embeddings API             ← Semantic search (768 dimensions)
Groq (Llama 3.3 70B)               ← LLM inference
Cloudinary                         ← Product image hosting
```

---

## 🧠 LangGraph Agent Design

V2 uses a **single conversational agent node** replacing V1's multi-node pipeline.

The key difference from V1: instead of routing messages through specialized nodes (greeting → intent → extraction → validation → search → recommendation), a single LLM agent with 6 tools handles the entire conversation freely.

```
Customer Message
        │
        ▼
  sales_agent_node  ← Single LLM agent with 6 tools
        │
        ▼
  LLM decides which tool to call based on context
        │
        ├── save_customer_requirements      ← capture partial info
        ├── get_product_info                ← answer product questions
        ├── get_all_products_summary        ← check availability
        ├── check_minimum_order             ← validate quantity
        ├── search_products_by_requirements ← RAG + SQL search
        └── trigger_human_handoff           ← alert wife silently
        │
        ▼
       END
```

### Agent Node

| Node | Responsibility |
|---|---|
| `sales_agent_node` | Single conversational agent — handles entire sales conversation, decides tool calls, collects requirements, shows products |

### Tools

| Tool | What It Does |
|---|---|
| `get_product_info` | Fetch full product details, sizes and pricing tiers from DB |
| `search_products_by_requirements` | RAG semantic search + SQL fallback by budget and quantity |
| `get_all_products_summary` | Get catalog overview to answer availability questions |
| `check_minimum_order` | Validate customer quantity against product minimum |
| `trigger_human_handoff` | Signal silent handoff — only wife gets alerted |
| `save_customer_requirements` | Capture partial requirements incrementally to state |

---

## 🔍 RAG Implementation

V2 adds semantic product search using pgvector and Jina AI embeddings — the main technical addition over V1.

```
Product Embedding (one-time, run locally):
  embed_products.py → Jina API → 768-dim vectors → product_embeddings table

Search at runtime:
  Customer query → Jina API → query vector
                → pgvector cosine similarity
                → top matching products
                → filter by budget + quantity
                → return ranked results
                → SQL fallback if RAG returns empty
```

**Why Jina AI?**
- Free tier: 1M tokens/month
- No local model — saves ~400MB RAM on Render free tier
- 768-dimension embeddings for high quality semantic matching

**Why RAG over SQL-only?**

V1 SQL search filters by exact budget and quantity — works well but cannot handle semantic queries like "eco friendly gifts" or "something traditional for south Indian wedding." V2 RAG matches customer intent to product descriptions semantically, returning relevant results even for vague queries.

---

## 💡 Key Business Logic

**4 Fields Gate:**
```
Bot NEVER shows products or prices until ALL 4 collected:
  ✓ Quantity    (how many pieces)
  ✓ Budget      (price per piece)
  ✓ Location    (delivery city)
  ✓ Timeline    (when needed)

Casual browsers who don't answer → no products shown
Serious buyers who answer all 4  → products shown with prices ✅
```

**Natural Collection:**
```
Customer gives 2 fields → bot asks for missing 2 together (numbered list)
Customer gives all 4    → bot immediately searches and shows products
Never asks one field at a time
```

**Silent Handoff:**
```
After products shown → wife alerted with full requirements
Customer says anything → bot stays completely silent
No message to customer — seamless handoff
```

---

## 📱 Human Handoff Flow

```
Bot collects all 4 requirements
        │
        ▼
Bot searches products (RAG + SQL)
        │
        ▼
Bot sends requirements summary + product images with prices
        │
        ▼
Bot silently alerts wife with full customer details
        │
        ▼
Bot locks conversation (stays silent forever)
        │
        ▼
Wife chats with customer directly from bot phone
        │
        ▼
Admin commands from wife's personal number:
    RESET <number>   → Clear conversation, bot starts fresh
    UNLOCK <number>  → Re-enable bot for that customer
    LOCK <number>    → Manually silence bot
```

---

## 📊 Admin Commands (Wife's Phone)

```
SUMMARY              → Today's business overview
SUMMARY 7            → Last 7 days
SUMMARY 12/02 19/02  → Custom date range

LEADS 7              → All leads last 7 days
FOLLOWUP             → Customers silent after seeing products
PENDING              → Incomplete conversations
HOTLEADS 100         → Orders ≥ 100 pieces
UPCOMING 10          → Events in next 10 days
LOCKED               → Wife-handled conversations

INFO 919942463672    → Full customer details
RESET 919942463672   → Clear and restart conversation
UNLOCK 919942463672  → Re-enable bot
```

### Automated Reports
- ☀️ **8:00 AM IST** — Morning briefing (follow-ups + upcoming events)
- 🌟 **9:00 PM IST** — Evening summary (today's leads + hot leads)
- 📅 **Every Monday 8 AM** — Weekly report
- 🗓️ **1st of month 8 AM** — Monthly report

---

## 🛠️ Tech Stack

### Python Service
| Technology | Usage |
|---|---|
| FastAPI | REST API |
| LangGraph 0.2 | Single conversational agent |
| LangChain 0.3 | Tools, prompts, LLM integration |
| Groq (Llama 3.3 70B) | LLM inference — fast, free tier |
| Jina AI Embeddings API | Semantic search — no local model needed |
| pgvector | Vector similarity search in PostgreSQL |
| psycopg3 + psycopg-pool | PostgreSQL connection pooling |
| Supabase PostgreSQL | Leads, checkpoints, auth, embeddings |
| LangSmith | LLM tracing and observability |

### Node.js Service
| Technology | Usage |
|---|---|
| Baileys | WhatsApp Web automation |
| Express | Web interface + health check |
| node-cron | Scheduled reports |
| axios | HTTP calls to Python service |
| pg | PostgreSQL for WhatsApp auth |

---

## 📁 Project Structure

```
├── node_service/
│   ├── core/
│   │   ├── vihaBot.js           ← Main WhatsApp client + message batching
│   │   ├── authStateSupabase.js ← Session persistence in Supabase
│   │   ├── llmClient.js         ← Python API client
│   │   └── webInterface.js      ← Express server + status page
│   ├── commands/
│   │   └── adminCommands.js     ← All admin command handlers
│   ├── jobs/
│   │   └── scheduledJobs.js     ← Cron reports
│   └── utils/
│       ├── messageHelper.js     ← Send text/images/alerts to WhatsApp
│       └── dateHelper.js        ← Date range parser
│
└── python_service/
    ├── bot/
    │   ├── config.py            ← LLM (Groq) setup
    │   ├── tools.py             ← 6 LangChain tools
    │   ├── nodes.py             ← Sales agent node + system prompt
    │   ├── graph.py             ← LangGraph assembly + checkpointer
    │   └── complete_bot.py      ← Public bot interface
    ├── api/
    │   ├── chat.py              ← POST /chat
    │   ├── conversations.py     ← Lock/unlock/reset
    │   ├── leads.py             ← Leads endpoints
    │   └── analytics.py        ← Summary/pending/followup/hotleads
    ├── services/
    │   ├── rag_service.py       ← Jina embeddings + pgvector search
    │   ├── lead_service.py      ← Save/update leads
    │   └── lock_service.py      ← Conversation lock management
    ├── models/
    │   └── bot_models.py        ← LangGraph state + Pydantic models
    ├── scripts/
    │   └── embed_products.py    ← One-time product embedding script
    └── main.py                  ← FastAPI app entry point
```

---

## 🚀 Deployment

Both services deployed on **Render**:

- Node service — always-on WhatsApp connection
- Python service — FastAPI REST API
- Database — Supabase PostgreSQL with pgvector extension
- Auth persistence — WhatsApp session saved to Supabase (survives restarts)
- Keep-alive — UptimeRobot pings health endpoints every 5 minutes

---

## 📈 V1 vs V2 Comparison

| Feature | V1 | V2 |
|---|---|---|
| Agent architecture | Multiple specialized nodes in fixed pipeline | Single conversational agent node |
| Product search | SQL filters only | RAG semantic search + SQL fallback |
| Semantic queries | Not supported | Supported via pgvector + Jina AI |
| Embeddings | None | 768-dim Jina embeddings in pgvector |
| Unexpected message formats | May misroute in pipeline | LLM handles naturally |
| 4 fields gate | ✅ | ✅ |
| Silent handoff | ✅ | ✅ |
| Price hidden until qualified | ✅ | ✅ |
| Observability | None | LangSmith tracing |
| RAM usage | ~150MB | ~150MB (Jina API, no local model) |

---

## 💡 Key Design Decisions

**Why single agent node instead of multi-node pipeline?**
V1 routes every message through a fixed sequence of specialized nodes regardless of context — greeting → intent → extraction → validation → search → recommendation. This works well for standard flows but adds latency (multiple LLM calls per turn) and is harder to maintain as business logic grows. A single conversational agent with tools handles the entire conversation in one LLM call, decides freely which tool to use based on context, and is easier to update by modifying the system prompt.

**Why RAG instead of SQL-only search?**
SQL filters work well for exact budget and quantity matching. But customers often describe needs vaguely — "eco friendly", "something traditional", "good for south Indian wedding." RAG matches these semantic queries to product descriptions, returning relevant results that SQL would miss.

**Why Jina AI instead of local sentence-transformers?**
Local sentence-transformers model uses ~400MB RAM — exceeds Render free tier 512MB limit causing OOM crashes. Jina API has no local model, keeps RAM at ~150MB, and provides free 1M tokens/month.

**Why gate products behind 4 fields?**
Based on 1.5 years of real business experience — casual enquirers who don't share requirements rarely convert. Gating product images behind 4 fields ensures wife only follows up with qualified leads who have real buying intent.

**Why two services?**
Node.js handles WhatsApp (Baileys requires Node). Python handles AI (LangChain/LangGraph ecosystem). Clean separation with HTTP between them.

**Why Groq?**
Fast inference (under 3 seconds per response) with Llama 3.3 70B. Free tier sufficient for current volume.

---

**Stack used:** LangGraph · LangChain · FastAPI · Groq · Jina AI · pgvector · Supabase · Baileys · Node.js · Python

---

## 🔄 Why V2? — The Switch from V1

V1 worked well in production. The conversation flow, 4 fields collection, silent handoff and admin commands all worked correctly.

**The only limitation was product search.**

V1 used SQL filters — matches products by exact budget and quantity. This works perfectly for straightforward queries. But as the catalogue grows, customers describe needs vaguely:

- *"Something eco friendly"*
- *"Traditional gifts for Tamil wedding"*
- *"Unique and different under 50 rupees"*

SQL cannot handle these. It either returns nothing or ignores the semantic intent entirely.

**V2 adds RAG — semantic product search using pgvector and Jina AI embeddings.**

Every product is embedded as a 768-dimension vector. When a customer describes their need, the query is embedded the same way and compared against all products using cosine similarity. Products are ranked by how well they match the customer's intent — not just their price and quantity.

The single conversational agent is a secondary architectural simplification — same business logic, cleaner codebase.

**In short:** V1 = price and quantity matching. V2 = intent and meaning matching.