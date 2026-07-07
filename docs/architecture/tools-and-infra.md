# Tool Layer & Infrastructure Architecture

## Overview
This document outlines the architecture and design decisions for the Tool Layer and Infrastructure Layer of the AI Email Assistant Harness. These layers provide the foundational services and actionable capabilities required by the Email Writing Agent and the Orchestrator.

---

## Infrastructure Layer (`src/infrastructure/`)

The Infrastructure Layer is the outermost ring in Clean Architecture. It provides concrete implementations for external dependencies such as databases, caches, file storage, task queues, and LLM providers.

### 1. Database (`database/connection.py`)
- **Technology**: SQLAlchemy (Async) with `aiosqlite` for local development.
- **Responsibility**: Manages the connection pool, engine creation, and provides an asynchronous context manager (`get_db_session`) for database transactions.
- **Design Pattern**: Dependency Injection. Services will receive the database session, allowing them to remain decoupled from SQLAlchemy itself.

### 2. Cache (`cache/cache_client.py`)
- **Technology**: Abstract Protocol with an `InMemoryCache` implementation.
- **Responsibility**: Provides fast access to ephemeral data (e.g., short-term memory, rate limit counters, OAuth token caching).
- **Extensibility**: Designed to be easily swapped with a Redis-backed implementation (`RedisCache`) in production environments.

### 3. Storage (`storage/file_store.py`)
- **Technology**: Local file system (`Pathlib`).
- **Responsibility**: Handles storing and retrieving binary assets, such as email attachments or exported audit logs.
- **Extensibility**: Exposes a `StorageClient` protocol that can be implemented by an `ObjectStore` (e.g., AWS S3, Google Cloud Storage) for cloud deployments.

### 4. Task Queue (`queue/task_queue.py`)
- **Technology**: Native `asyncio.Queue` for local execution.
- **Responsibility**: Dispatches non-blocking background tasks (e.g., sending webhook notifications, generating audit reports) to worker coroutines.
- **Extensibility**: Can be replaced with Celery or RQ when scaling horizontally.

### 5. LLM Client (`llm/llm_client.py`, `llm/llm_router.py`)
- **Technology**: Wrapper around LLM provider SDKs (e.g., OpenAI).
- **Responsibility**: The `LLMClient` abstracts the provider-specific API calls. The `LLMRouter` determines which client to use based on configuration, enabling fallback mechanisms and task-specific routing (e.g., GPT-4 for complex reasoning, GPT-3.5 for simple summarization).

---

## Tool Layer (`src/tools/`)

The Tool Layer contains the specific actions that the LLM agent can invoke. By encapsulating these actions into tools, the system maintains control over execution, logging, and error handling.

### 1. Base Tool (`base_tool.py`)
- **Structure**: Defines an abstract `BaseTool` class requiring a `name`, `description`, and a Pydantic `args_schema`.
- **Purpose**: Ensures that all tools have a strict input schema, which is automatically converted to the JSON schema format required by OpenAI's function calling API (`to_llm_dict`).

### 2. Gmail Interaction Tools
These tools abstract the Gmail API, allowing the agent to read and compose emails securely.
- **`gmail_reader_tool.py`**: Fetches full email threads. Returns structured messages (sender, date, snippet, body).
- **`gmail_draft_tool.py`**: Creates a new draft or updates an existing one without sending it. 
- **`gmail_send_tool.py`**: Sends an already-approved draft. *(Note: In the Harness architecture, the agent does not invoke this directly; it is typically invoked by the workflow orchestrator post-approval).*

### 3. Utility Tools
Tools that assist the agent with context and reasoning.
- **`thread_summarizer_tool.py`**: Uses a secondary LLM call to condense extremely long email threads into manageable bullet points, preventing context window overflow.
- **`contact_lookup_tool.py`**: Interfaces with a mock CRM to provide the agent with relationship context (e.g., name, company, interaction notes) based on the sender's email address.

---

## Relationship to Clean Architecture

Both of these layers sit at the boundary of the application:
1. **The Agent (Application Layer)** depends on the abstract `BaseTool` interfaces, not the concrete Gmail API logic.
2. **The Services (Application Layer)** depend on the abstract Database/Cache interfaces, not SQLAlchemy or Redis directly.
3. This guarantees that the core email processing workflow remains isolated from changes in third-party providers.
