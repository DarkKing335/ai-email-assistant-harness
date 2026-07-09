# Solution Design: Context Diagrams for Tools, Proxy, and Infrastructure

Below is the detailed design (Context Diagrams) illustrating how modules interact within the **AI Email Assistant Harness** architecture. These designs focus on three main layers: **Tools Layer**, **Proxy Layer** (acting as Security/Approval), and **Infrastructure Layer**.

---

## 1. Module 1: Tools Layer (Interface Adapter)
**Design Objective:** Encapsulate all external API calls. The Agent never calls APIs directly but must route through the Tool Layer. The Tool Layer is responsible for standardizing input (schema validation) and parsing output results.

```mermaid
graph LR
    %% Actors
    Agent(("🤖 Agent (LLM)"))
    Infra(("⚙️ Infra Layer"))
    
    %% System
    subgraph ToolLayer ["🛠️ Tool Layer System"]
        Registry["Tool Registry\n(Discovery & Routing)"]
        BaseTool["BaseTool\n(Pydantic Schema Validation)"]
        
        subgraph ConcreteTools ["Registered Tools"]
            Reader["GmailReaderTool"]
            Drafter["GmailDraftTool"]
            Lookup["ContactLookupTool"]
        end
    end
    
    %% Flow
    Agent -- "1. JSON Tool Call" --> Registry
    Registry -- "2. Routes & Checks Permission" --> BaseTool
    BaseTool -- "3. Validates Args" --> ConcreteTools
    ConcreteTools -- "4. Request Data" --> Infra
    Infra -- "5. Return Data" --> ConcreteTools
    ConcreteTools -- "6. Safe JSON Result" --> Agent

    style ToolLayer fill:#f9f2ec,stroke:#d6b656,stroke-width:2px
    style Registry fill:#fff2cc,stroke:#d6b656
    style BaseTool fill:#fff2cc,stroke:#d6b656
    style ConcreteTools fill:#ffffff,stroke:#d6b656
```

---

## 2. Module 2: Proxy Layer (Harness & Security Boundary)
**Design Objective:** The Proxy is not a network proxy, but a **Security Proxy (Harness Orchestrator)**. It sits between the Agent and dangerous actions (like sending an email). Its function is to block the Agent from autonomously sending emails, run Guardrails, and wait for a Human-in-the-loop to approve.

```mermaid
graph TD
    %% Actors
    Agent(("🤖 Agent"))
    Human(("👤 Human Reviewer\n(CLI)"))
    RestrictedTool(("🔒 GmailSendTool\n(Requires Approval)"))
    
    %% System
    subgraph ProxyLayer ["🛡️ Proxy / Harness Layer"]
        Guardrails["Guardrails\n(PII & Content Filter)"]
        Gate["Approval Gate\n(asyncio.Future)"]
        Audit["Audit Logger\n(Immutable Events)"]
    end
    
    %% Flow
    Agent -- "1. Agent Completes Draft" --> Guardrails
    Guardrails -- "Fail" --> Terminate(("X Stop Workflow"))
    Guardrails -- "2. Pass Checks" --> Gate
    Gate -. "3. Notifies Pending" .-> Human
    Human -- "4. CLI Interaction: Approve" --> Gate
    Gate -- "5. Unlocks Execution" --> RestrictedTool
    RestrictedTool -- "6. Report Success" --> Audit

    style ProxyLayer fill:#e8f4f8,stroke:#6c8ebf,stroke-width:2px
    style Guardrails fill:#dae8fc,stroke:#6c8ebf
    style Gate fill:#dae8fc,stroke:#6c8ebf
    style Audit fill:#dae8fc,stroke:#6c8ebf
    style RestrictedTool fill:#f8cecc,stroke:#b85450
```

---

## 3. Module 3: Infrastructure Layer
**Design Objective:** The lowest level, containing no AI business logic. It handles all I/O, Database connections, Caching, and external API calls (OpenAI, Gmail). The Tools Layer and Proxy Layer depend entirely on the Infra Layer.

```mermaid
graph LR
    %% Actors
    ToolProxy(("🛠️ Tool & Proxy Layers"))
    ExtGmail(("📧 External Gmail API"))
    ExtLLM(("🧠 External OpenAI API"))
    
    %% System
    subgraph InfraLayer ["⚙️ Infrastructure Layer"]
        DB[(Async Database\nSQLite/PostgreSQL)]
        Cache[(In-Memory Cache)]
        LLMRouter["LLM Router & Client\n(Task-based routing)"]
        GmailAdapter["Gmail HTTP Client\n(OAuth2 Auth)"]
    end
    
    %% Flow
    ToolProxy -- "Read/Write State" --> DB
    ToolProxy -- "Store Context" --> Cache
    ToolProxy -- "Generate Summaries" --> LLMRouter
    ToolProxy -- "Fetch/Draft/Send" --> GmailAdapter
    
    LLMRouter -- "REST API" --> ExtLLM
    GmailAdapter -- "REST API" --> ExtGmail

    style InfraLayer fill:#f4eaec,stroke:#b85450,stroke-width:2px
    style DB fill:#f8cecc,stroke:#b85450
    style Cache fill:#f8cecc,stroke:#b85450
    style LLMRouter fill:#f8cecc,stroke:#b85450
    style GmailAdapter fill:#f8cecc,stroke:#b85450
```
