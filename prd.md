# 📄 RAG + Persona Microservice PRD v3.0
## Zero-Cost Foundation + Persona Intelligence

---

## 🎯 Mission

Build **NotebookLM-style RAG** with **persona-based responses**:
- Upload docs → chat with them
- Response mimics selected persona (Einstein, Feynman, etc.)
- Free tier (Gemini) + paid tiers (OpenAI, Claude)
- Admins manage persona library
- Users select persona per conversation

---

## 🧩 Core Concept

```
User uploads PDF about quantum physics
   ↓
Selects "Einstein" persona
   ↓
Asks: "What is entanglement?"
   ↓
RAG retrieves context from PDF
   ↓
LLM generates factual answer
   ↓
Persona engine rewrites in Einstein's style
   ↓
Response: "Ah, my friend, imagine two particles 
          dancing in perfect harmony..."
```

**Key principle:** Truth → Style (never reverse)

---

## 🏗️ System Architecture

```
┌──────────────────────────────────────┐
│         Main Backend                 │
│  - Auth                              │
│  - Subscriptions (free/paid)         │
│  - Persona management (admins)       │
│  - User persona selection            │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│      RAG Microservice (FastAPI)      │
│                                      │
│  ┌────────────┐    ┌──────────────┐ │
│  │  Ingestion │    │   Query      │ │
│  │  Pipeline  │    │   Pipeline   │ │
│  └─────┬──────┘    └──────┬───────┘ │
│        │                  │         │
│  ┌─────▼──────┐    ┌──────▼───────┐ │
│  │ Supabase   │    │   Qdrant     │ │
│  │ Storage    │    │   Vectors    │ │
│  │ Postgres   │    │   Search     │ │
│  └────────────┘    └──────┬───────┘ │
│                           │         │
│                    ┌──────▼───────┐ │
│                    │ LLM Router   │ │
│                    │ (tier-based) │ │
│                    └──────┬───────┘ │
│                           │         │
│              ┌────────────┼────────┐│
│              ▼            ▼        ││
│        ┌─────────┐  ┌──────────┐  ││
│        │ Gemini  │  │ OpenAI   │  ││
│        │ (free)  │  │ (paid-1) │  ││
│        └─────────┘  └──────────┘  ││
│                                    ││
│              ┌──────▼───────┐     ││
│              │   Persona    │     ││
│              │   Engine     │     ││
│              └──────────────┘     ││
└────────────────────────────────────┘
```

---

## 🎭 Persona System

### Admin Workflow

**Admins create personas:**

```json
{
  "persona_id": "einstein_v1",
  "name": "Albert Einstein",
  "avatar_url": "https://...",
  "description": "Theoretical physicist, uses analogies",
  
  "training_data": {
    "documents": [
      "einstein_letters.pdf",
      "relativity_explained.pdf"
    ],
    "sample_responses": [
      {
        "question": "What is time?",
        "response": "Time is relative, my friend..."
      }
    ]
  },
  
  "style_config": {
    "tone": "thoughtful, philosophical",
    "vocabulary": "simple analogies, avoids jargon",
    "structure": "story-like explanations",
    "signature_phrases": [
      "Imagine...",
      "Think of it this way...",
      "In essence..."
    ]
  },
  
  "system_prompt": "You are Albert Einstein. Explain concepts using simple analogies and thought experiments. Be warm and encouraging. Start responses with 'Ah,' or 'My friend,' occasionally."
}
```

**Stored in:** Main backend DB (not RAG service)

---

### User Workflow

```
1. User uploads PDFs to their library
2. User selects persona: "Einstein"
3. User asks questions
4. RAG responds in Einstein's style
5. User can switch persona mid-conversation
```

---

## 🔄 Data Flows

### 1. Persona Creation (Admin)

```
Admin uploads Einstein training docs
   ↓
Main backend stores persona config
   ↓
RAG service ingests Einstein's writing samples
   ↓
Creates "einstein_persona" namespace in Qdrant
   ↓
System prompt generated + cached
```

---

### 2. Document Ingestion (User)

```
User uploads quantum_physics.pdf
   ↓
Main backend → RAG /ingest endpoint
   ↓
File stored in Supabase Storage
   ↓
Extract → Chunk → Embed (BGE-small)
   ↓
Store in Qdrant (user's namespace)
   ↓
Metadata saved in Supabase Postgres
```

---

### 3. Query with Persona

```
User: "What is quantum entanglement?"
Persona: "Einstein"
Subscription: Free (Gemini)
   ↓
RAG retrieves context from user's PDFs
   ↓
Gemini generates factual answer
   ↓
Persona engine retrieves Einstein's style
   ↓
Second LLM call: rewrite in Einstein's voice
   ↓
Response: "Ah, imagine two particles..."
   ↓
Sources attached: [quantum_physics.pdf, page 42]
```

---

## 📡 API Specification

### Base: `https://rag-service.railway.app/api/v1`

---

### 1. Ingest Persona Training Data (Admin)

**`POST /admin/personas/ingest`**

**Headers:**
```
Authorization: Bearer {admin_token}
```

**Request:**
```json
{
  "persona_id": "einstein_v1",
  "documents": [
    {
      "file": "multipart/form-data",
      "type": "writing_sample"
    }
  ],
  "system_prompt": "You are Einstein...",
  "style_config": {...}
}
```

**Response:**
```json
{
  "persona_id": "einstein_v1",
  "chunks_indexed": 234,
  "status": "ready"
}
```

---

### 2. Ingest User Document

**`POST /ingest`**

**Request:**
```json
{
  "file": "multipart/form-data",
  "user_id": "user_123",
  "metadata": {
    "title": "Quantum Physics Notes",
    "tags": ["science", "physics"]
  }
}
```

**Response:**
```json
{
  "doc_id": "doc_abc123",
  "status": "processed",
  "chunks_created": 87,
  "storage_url": "https://supabase.co/.../doc.pdf",
  "processing_time_ms": 8300
}
```

---

### 3. Query with Persona

**`POST /query`**

**Request:**
```json
{
  "query": "Explain quantum entanglement simply",
  
  "user_id": "user_123",
  
  "persona": {
    "persona_id": "einstein_v1",
    "intensity": 0.8  // 0-1, how much persona vs neutral
  },
  
  "subscription_tier": "free",  // free | pro | enterprise
  
  "filters": {
    "doc_ids": ["doc_abc123"],
    "tags": ["physics"]
  },
  
  "config": {
    "top_k": 5,
    "stream": true,
    "include_sources": true
  }
}
```

**Response (streaming):**
```
data: {"type": "status", "message": "Retrieving context..."}

data: {"type": "retrieval", "chunks_found": 5}

data: {"type": "generation_start"}

data: {"type": "token", "content": "Ah,"}
data: {"type": "token", "content": " my"}
data: {"type": "token", "content": " friend,"}
data: {"type": "token", "content": " imagine"}
...

data: {"type": "sources", "sources": [
  {
    "doc_id": "doc_abc123",
    "title": "Quantum Physics Notes",
    "page": 42,
    "excerpt": "...particles become correlated...",
    "relevance": 0.89
  }
]}

data: {"type": "metadata", "data": {
  "persona_applied": "einstein_v1",
  "llm_used": "gemini-1.5-flash",
  "tokens": 1240,
  "cached": false
}}

data: {"type": "done"}
```

**Non-streaming response:**
```json
{
  "answer": "Ah, my friend, imagine two particles dancing...",
  
  "sources": [...],
  
  "metadata": {
    "persona_applied": "einstein_v1",
    "persona_intensity": 0.8,
    "llm_used": "gemini-1.5-flash",
    "subscription_tier": "free",
    "tokens_used": 1240,
    "processing_time_ms": 2340,
    "cached": false
  }
}
```

---

### 4. List Available Personas

**`GET /personas?user_id={user_id}`**

**Response:**
```json
{
  "personas": [
    {
      "persona_id": "einstein_v1",
      "name": "Albert Einstein",
      "description": "Explains through analogies",
      "avatar_url": "https://...",
      "available_in_tier": "free"
    },
    {
      "persona_id": "feynman_v1",
      "name": "Richard Feynman",
      "description": "Simple, direct explanations",
      "avatar_url": "https://...",
      "available_in_tier": "free"
    },
    {
      "persona_id": "hawking_v1",
      "name": "Stephen Hawking",
      "description": "Poetic, cosmic perspective",
      "avatar_url": "https://...",
      "available_in_tier": "pro"
    }
  ]
}
```

---

### 5. Delete Document

**`DELETE /documents/{doc_id}?user_id={user_id}`**

---

### 6. Health Check

**`GET /health`**

```json
{
  "status": "healthy",
  "services": {
    "supabase": "connected",
    "qdrant": "connected",
    "gemini": "available",
    "openai": "available"
  },
  "personas_loaded": 12
}
```

---

## 🗄️ Data Models

### Supabase Schema

```sql
-- Documents
CREATE TABLE documents (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  doc_id TEXT UNIQUE NOT NULL,
  user_id TEXT NOT NULL,
  title TEXT,
  filename TEXT,
  
  storage_provider TEXT,
  storage_path TEXT,
  storage_url TEXT,
  file_size_mb DECIMAL,
  
  chunks_count INT,
  status TEXT,
  
  tags TEXT[],
  metadata JSONB,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  processed_at TIMESTAMPTZ
);

-- Query logs (analytics)
CREATE TABLE query_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id TEXT NOT NULL,
  query TEXT,
  
  persona_id TEXT,
  subscription_tier TEXT,
  
  answer TEXT,
  sources JSONB,
  
  llm_provider TEXT,
  tokens_used INT,
  latency_ms INT,
  cached BOOLEAN,
  
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Persona usage (track popular personas)
CREATE TABLE persona_usage (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  persona_id TEXT,
  user_id TEXT,
  queries_count INT DEFAULT 1,
  last_used TIMESTAMPTZ DEFAULT NOW()
);
```

---

### Qdrant Collections

**Collection 1:** `user_documents`
```python
{
  "id": "user_123_doc_abc_chunk_5",
  "vector": [...],  # 384 dims
  "payload": {
    "user_id": "user_123",
    "doc_id": "doc_abc123",
    "chunk_idx": 5,
    "page": 3,
    "text": "...",
    "title": "Quantum Physics",
    "tags": ["physics"]
  }
}
```

**Collection 2:** `persona_knowledge`
```python
{
  "id": "einstein_v1_sample_12",
  "vector": [...],
  "payload": {
    "persona_id": "einstein_v1",
    "type": "writing_sample",
    "text": "Time is relative...",
    "source": "einstein_letters.pdf"
  }
}
```

---

## 🤖 LLM Routing (Subscription Tiers)

### Tier Configuration

```python
LLM_TIERS = {
    "free": {
        "provider": "gemini",
        "models": {
            "generation": "gemini-1.5-flash",
            "persona_rewrite": "gemini-1.5-flash"
        },
        "limits": {
            "queries_per_day": 50,
            "max_tokens": 2000
        }
    },
    
    "pro": {
        "provider": "openai",
        "models": {
            "generation": "gpt-4o-mini",
            "persona_rewrite": "gpt-4o-mini"
        },
        "limits": {
            "queries_per_day": 500,
            "max_tokens": 4000
        }
    },
    
    "enterprise": {
        "provider": "anthropic",
        "models": {
            "generation": "claude-3-5-sonnet",
            "persona_rewrite": "claude-3-5-sonnet"
        },
        "limits": {
            "queries_per_day": -1,  # unlimited
            "max_tokens": 8000
        }
    }
}
```

---

### Routing Logic

```python
def get_llm_config(subscription_tier: str):
    tier_config = LLM_TIERS.get(subscription_tier, LLM_TIERS["free"])
    
    return {
        "provider": tier_config["provider"],
        "generation_model": tier_config["models"]["generation"],
        "persona_model": tier_config["models"]["persona_rewrite"],
        "max_tokens": tier_config["limits"]["max_tokens"]
    }
```

---

## 🎭 Persona Engine Design

### Two-Step Generation

**Step 1: Factual Answer**
```
Context: [retrieved chunks]
Query: "What is quantum entanglement?"

System: Answer factually using only the context.

LLM → "Quantum entanglement is a phenomenon where..."
```

**Step 2: Persona Transformation**
```
Factual answer: "Quantum entanglement is..."
Persona: Einstein
Intensity: 0.8

System: Rewrite this answer in Einstein's style:
- Use analogies
- Be warm and encouraging
- Start with "Ah," or "My friend,"
- PRESERVE ALL FACTS

LLM → "Ah, my friend, imagine two particles..."
```

---

### Persona Intensity

```python
def apply_persona(answer: str, persona_config: dict, intensity: float):
    if intensity == 0:
        return answer  # No persona
    
    elif intensity < 0.5:
        # Light touch: just adjust tone
        prompt = f"Lightly adjust tone to match {persona_config['name']}"
    
    elif intensity < 0.8:
        # Medium: apply style
        prompt = persona_config['system_prompt']
    
    else:
        # Strong: full persona + examples
        prompt = f"{persona_config['system_prompt']}\n\n"
        prompt += "Examples:\n"
        for ex in persona_config['training_data']['sample_responses']:
            prompt += f"Q: {ex['question']}\nA: {ex['response']}\n\n"
    
    return rewrite_with_llm(answer, prompt)
```

---

## 💰 Subscription Model

| Tier | LLM | Queries/day | Personas | Price |
|------|-----|-------------|----------|-------|
| **Free** | Gemini Flash | 50 | Einstein, Feynman, Curie | $0 |
| **Pro** | GPT-4o-mini | 500 | +10 personas | $10/mo |
| **Enterprise** | Claude Sonnet | Unlimited | All + custom | $50/mo |

---

## 📏 Functional Requirements

### Core Features
- [x] Multi-document upload per user
- [x] Persona selection UI (main backend)
- [x] Persona-styled responses
- [x] Source citations
- [x] Streaming responses
- [x] NotebookLM-style chat interface

### Admin Features
- [x] Create/edit personas
- [x] Upload persona training data
- [x] Assign personas to tiers
- [x] Monitor persona usage

### Advanced
- [ ] Multi-persona conversations
- [ ] Persona mixing (Einstein 70% + Feynman 30%)
- [ ] Voice synthesis (future)

---

## ⚙️ Tech Stack (Final)

| Layer | Tool | Free Limit |
|-------|------|------------|
| **API** | FastAPI | Unlimited |
| **Hosting** | Railway | 500hrs/mo |
| **PDF Storage** | Supabase Storage | 1GB |
| **Metadata DB** | Supabase Postgres | 500MB |
| **Vector DB** | Qdrant Cloud | 1GB (250k chunks) |
| **Embeddings** | BGE-small-en-v1.5 | Unlimited |
| **LLM (Free)** | Gemini 1.5 Flash | 1500/day |
| **LLM (Pro)** | OpenAI GPT-4o-mini | Pay-as-go |
| **LLM (Enterprise)** | Claude Sonnet | Pay-as-go |

**Total free tier cost:** $0

---

## 🚨 Guardrails

### Factual Integrity
```python
def validate_persona_response(original: str, personafied: str):
    # Extract facts from both
    facts_original = extract_facts(original)
    facts_persona = extract_facts(personafied)
    
    # Check preservation
    if not all(fact in facts_persona for fact in facts_original):
        return original  # Fallback to factual
    
    return personafied
```

### Prompt Injection Defense
```python
def sanitize_context(chunks: list):
    banned_patterns = [
        r"ignore (previous|above)",
        r"you are now",
        r"system:",
        r"<\|.*?\|>"
    ]
    
    for chunk in chunks:
        for pattern in banned_patterns:
            chunk['text'] = re.sub(pattern, "[FILTERED]", chunk['text'], flags=re.I)
    
    return chunks
```

### Rate Limiting
```python
RATE_LIMITS = {
    "free": "50/day",
    "pro": "500/day",
    "enterprise": "unlimited"
}
```

---

## 📊 Success Metrics

### Retrieval Quality
- MRR@5 > 0.85
- Citation accuracy 100%

### Persona Quality
- Factual preservation rate > 99%
- User satisfaction (style rating) > 4/5
- Persona recognition (blind test) > 80%

### Performance
- p50 latency < 2s
- p95 latency < 4s
- Cache hit rate > 60%

### Business
- Free → Pro conversion > 5%
- Queries/user/week > 10
- Most popular persona: Einstein

---

## 🗓️ Development Phases

### Phase 1: MVP (Weeks 1-3)
- [ ] Basic RAG (ingest + query)
- [ ] Supabase integration
- [ ] Qdrant setup
- [ ] Gemini integration
- [ ] Single persona (Einstein)

### Phase 2: Persona System (Weeks 4-5)
- [ ] Persona engine
- [ ] Admin persona creation
- [ ] 3-5 default personas
- [ ] Persona intensity control
- [ ] Factual validation

### Phase 3: Multi-LLM (Week 6)
- [ ] LLM router
- [ ] OpenAI integration
- [ ] Subscription tier logic
- [ ] Rate limiting

### Phase 4: Polish (Weeks 7-8)
- [ ] Streaming optimization
- [ ] Cache layer
- [ ] Analytics dashboard
- [ ] Load testing
- [ ] Docs + deployment

---

## 🎓 Design Principles

> **1. Truth > Style** — Persona never distorts facts  
> **2. User Choice** — Always show original factual answer first  
> **3. Transparent Attribution** — Clear source citations  
> **4. Tier Fairness** — Free tier fully functional  
> **5. Observable** — Log everything for debugging

---

## ✅ Definition of Done

- [ ] User can upload 10+ PDFs
- [ ] Chat works like NotebookLM
- [ ] 5 personas available (free tier)
- [ ] Responses feel authentic
- [ ] Zero hallucinations
- [ ] Sub-3s latency
- [ ] Free tier = 50 queries/day working
- [ ] Admin can create persona in <10min

---

Production PRD complete. Build NotebookLM + Personas. Zero cost base. Scale with tiers.