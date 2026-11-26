# API Documentation & Use Cases

This document outlines the internal API endpoints provided by the RAG system and the external APIs integrated into the application.

---

## 1. Internal API Endpoints (FastAPI)

These endpoints are used by the frontend or other services to interact with the RAG system.

### **Ingestion & Document Management**
| Endpoint | Method | Use Case |
| :--- | :--- | :--- |
| `/ingest` | `POST` | Uploads a document (PDF, TXT, etc.), extracts text, generates embeddings, and stores it in the vector database. Also caches document context for summarization. |
| `/ingest/status/{job_id}` | `GET` | Checks the status of an ongoing ingestion job (queued, processed, or failed). |
| `/documents/{document_id}` | `GET` | Retrieves metadata and status for a specific document. |
| `/documents/{document_id}` | `DELETE` | Removes a document from the system, including its chunks, stored assets, and cached context. |
| `/bulk-delete` | `POST` | Deletes multiple documents in a single request. |
| `/reindex/{document_id}` | `POST` | Triggers a re-indexing process for an existing document (e.g., if chunking strategy changes). |

### **Query & Generation**
| Endpoint | Method | Use Case |
| :--- | :--- | :--- |
| `/query` | `POST` | Performs a RAG query with **hybrid search** (vector + BM25 + reranking). Automatically detects summarization requests ("Summarize this document", "Brief overview", "TL;DR"). |
| `/query/stream` | `POST` | Similar to `/query` but returns a text/event-stream for real-time token generation (UI typewriter effect). Supports summarization queries. |

**Summarization Queries Supported:**
- "Summarize this document" → Returns cached document context → Generates summary
- "Give me a brief overview" → Concise overview with optional persona styling
- "TL;DR of the PDF" → Ultra-concise summary
- "Key points from chapter 3" → Chapter-specific summary (if chapter metadata available)

### **Personas (AI Personalities)**
| Endpoint | Method | Use Case |
| :--- | :--- | :--- |
| `/personas` | `GET` | Lists all available AI personas (e.g., Professional, Creative, Concise). |
| `/personas/{persona_id}` | `GET` | Gets details for a specific persona, including its prompt configuration. |
| `/admin/personas` | `POST` | (Admin) Creates a new persona with custom styling and intensity settings. |
| `/admin/personas/{persona_id}` | `PUT` | (Admin) Updates an existing persona's configuration. |
| `/admin/personas/{persona_id}` | `DELETE` | (Admin) Permanently removes a persona. |

### **Chat Sessions**
| Endpoint | Method | Use Case |
| :--- | :--- | :--- |
| `/sessions` | `POST` | Creates a new chat session to group queries and maintain history. |
| `/sessions` | `GET` | Lists all chat sessions for a specific user. |
| `/sessions/{session_id}` | `GET` | Retrieves session details and metadata. |
| `/sessions/{session_id}` | `DELETE` | Deletes a chat session and associated metadata. |

---

## 2. External APIs Integrated

These are third-party services that the application relies on for core functionality.

### **Generative AI & Embeddings**
- **Google Gemini API**
  - **Use Case**: Used for generating high-quality text embeddings (`gemini-embedding-2`) during ingestion, **Free Tier** LLM generation, and **query rewriting** for better retrieval.
- **OpenAI API**
  - **Use Case**: Powers the **Pro Tier** generation, offering higher reasoning capabilities and larger context windows.
- **Anthropic API**
  - **Use Case**: Powers the **Enterprise Tier** generation, utilized for complex, high-stakes queries requiring advanced grounding.

### **Storage & Database**
- **Cloudinary API**
  - **Use Case**: Acts as the primary storage provider for raw document assets (PDFs/Images). It handles file hosting and delivery.
- **Supabase / PostgreSQL (pgvector)**
  - **Use Case**: Stores relational metadata (users, sessions, documents) and provides high-performance vector similarity search using the `pgvector` extension.

### **Caching & Infrastructure**
- **Redis (Upstash)**
  - **Use Case**: Used for **Query Caching** (speeding up repeated questions), **Document Context Memory** (for summarization), **Rate Limiting** (preventing abuse of the ingestion and query endpoints).
- **External Search APIs (Optional)**
  - **Use Case**: Integrated via `get_external_knowledge` to supplement the RAG system with live web data when local context is insufficient.

### **Search Optimization**
- **BM25 (rank-bm25)**
  - **Use Case**: Lexical/keyword search fallback alongside vector similarity for improved recall.
- **Sentence-Transformers (Cross-Encoder)**
  - **Use Case**: Reranking retrieved chunks using `ms-marco-MiniLM-L-6-v2` for better relevance.

---

## 3. Technology Stack Summary
- **Backend**: Python 3.11+, FastAPI
- **Database**: PostgreSQL with `pgvector` (768-dim vectors)
- **Cache**: Redis / Upstash (context memory, query cache)
- **ORM**: SQLAlchemy (Async)
- **Vector Search**: pgvector extension + BM25 hybrid search
- **LLM Routing**: Gemini (free), OpenAI (pro), Anthropic (enterprise)
- **RAG Optimizations**: Query rewriting, Reciprocal Rank Fusion, Cross-Encoder reranking, Parent document retrieval
