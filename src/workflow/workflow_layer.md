# Workflow Layer

## Overview
The **Workflow Layer** is the central nervous system of the AI Email Assistant Harness. It is responsible for orchestrating the lifecycle of an email from ingestion to auditing. 

By decoupling the control flow (Orchestrator) from the business logic (Steps), this layer enforces strict Harness Engineering patterns—ensuring no step can be bypassed and mandatory human-in-the-loop (HITL) checkpoints are respected.

---

## 🔌 Integration Guide: How to Connect to the Workflow Layer

This section is for developers working on the **CLI Layer**, **API Endpoints**, or **Integrations** who need to trigger or interact with the Workflow Layer.

### 1. The Facade (For Callers)
External layers should **never** import individual steps or the state machine directly. The Workflow Layer provides a single entry point via the Orchestrator. 

To trigger the workflow, simply import the Orchestrator and call the `run()` method:

```python
from src.workflow import EmailWorkflowOrchestrator

async def process_email(gmail_thread_id: str):
    orchestrator = EmailWorkflowOrchestrator()
    
    # Start the engine
    result_context = await orchestrator.run(thread_id=gmail_thread_id)
    
    # Check the final status
    if result_context.status.name == "ERROR":
        print(f"Failed: {result_context.metadata.get('error')}")
    elif result_context.status.name == "AWAITING_APPROVAL":
        print("Draft is ready. Waiting for human approval.")
    elif result_context.status.name == "AUDITED":
        print("Email processed and sent successfully!")
2. The Data Contract (For Tool & Integration Developers)
If you are building external tools (e.g., Gmail API fetcher, LLM Router), your tools will be called by the Pipeline Steps.
Rule: You must use WorkflowContext (src/models/workflow_context.py) as the single source of truth to read and write data.

Reading: Access ctx.email_thread or ctx.draft to get data for your tool.

Writing: Attach your tool's output to the corresponding ctx attribute.

Errors: Do not crash the app. Raise standard Python Exceptions; the Orchestrator will catch them and log them to ctx.metadata["error"].

Approval Gate: To pass the approval step, ensure ctx.is_approved = True is set by the UI/CLI before the Send step.

Retry Limit: Use ctx.can_retry() and ctx.increment_retry() inside your steps for resilient LLM calls.

Core Components
1. EmailWorkflowOrchestrator
The main driver (src/workflow/engine/orchestrator.py). It manages the execution sequence, catches exceptions, and handles workflow suspension/branching when waiting for human approval.

2. WorkflowStateMachine
Enforces valid state transitions (src/workflow/engine/state_machine.py). It guarantees that a draft cannot transition to SENDING unless it is explicitly APPROVED.

3. WorkflowContext
A state object passed between steps. It holds the thread_id, intermediate results (like the drafted content), approval flags (is_approved), retry counters, and the current WorkflowStatus.

4. Pipeline Steps
Isolated business logic blocks (src/workflow/steps/). Every step inherits from a BaseWorkflowStep interface:

IngestStep: Fetches and parses Gmail threads.

DraftStep: Invokes the Email Writing Agent and Tool Layer to create a reply.

GuardrailsStep: Validates the draft against safety policies.

ApprovalStep: Registers the draft with the ApprovalGate and pauses execution.

SendStep: Directly invokes the send tool (only if is_approved is True).

AuditStep: Logs the final outcome to the immutable audit log.

State Machine Flow
Đoạn mã
graph TD
    RECEIVED --> INGESTED
    INGESTED --> DRAFTED
    DRAFTED --> GUARDRAILS_PASSED
    DRAFTED --> GUARDRAILS_FAILED
    GUARDRAILS_PASSED --> AWAITING_APPROVAL
    AWAITING_APPROVAL -. Human Intervention .-> APPROVED
    AWAITING_APPROVAL -. Human Intervention .-> REJECTED
    APPROVED --> SENDING
    SENDING --> SENT
    SENT --> AUDITED
    REJECTED --> TERMINATED
    GUARDRAILS_FAILED --> TERMINATED
How to Add a New Step
Create a new file in src/workflow/steps/ (e.g., translation_step.py).

Implement the BaseWorkflowStep interface (must have an async def run(self, ctx) method).

Register the new step in the EmailWorkflowOrchestrator.__init__ and call it in the run() execution list.

Update WorkflowStatus in constants.py to reflect the new state transition.