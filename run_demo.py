"""
run_demo.py — Drive the full email workflow end-to-end in ONE process.

The CLI's approval gate uses an in-memory queue, so `email process` blocks
waiting for a separate `email approve` (which can't reach the same in-process
queue). This driver runs the orchestrator AND resolves the approval in the
same process, so you see a complete run.

Usage:
    python run_demo.py <thread_id>              # SAFE: rejects at the gate (no email sent)
    python run_demo.py <thread_id> --approve    # SENDS a real reply to the thread's sender!

⚠  With real Gmail credentials, --approve SENDS a real email to whoever sent the
   thread. Test it against an email you sent yourself first.
"""
import asyncio
import sys

from src.tools.registry import build_default_registry
from src.approval.gate import approval_gate
from src.workflow.engine.orchestrator import EmailWorkflowOrchestrator


async def main(thread_id: str, approve: bool) -> None:
    build_default_registry()
    orch = EmailWorkflowOrchestrator()

    task = asyncio.create_task(orch.run(thread_id))

    resolved = False
    for _ in range(100):                       # up to ~10s for the draft to reach the gate
        await asyncio.sleep(0.1)
        pending = approval_gate.list_pending()
        if pending:
            p = pending[0]
            print("\n=== AWAITING APPROVAL ===")
            print("draft :", p["draft_id"])
            print("to    :", p["to"])
            print("flags :", p["escalations"] or "(none)")
            print("pii   :", p["pii_detected"])
            if approve:
                print("decision: APPROVE  ->  this SENDS a real email")
                approval_gate.approve(p["draft_id"], reviewer="demo-reviewer")
            else:
                print("decision: REJECT   ->  nothing is sent (pass --approve to send)")
                approval_gate.reject(p["draft_id"], reviewer="demo-reviewer", reason="demo run")
            resolved = True
            break

    ctx = await task

    print("\n=== RESULT ===")
    error = ctx.metadata.get("error")
    if error:
        print("error:", error)
    print("draft to         :", ctx.draft.to if ctx.draft else None)
    print("guardrails_passed:", ctx.draft.guardrails_passed if ctx.draft else None)
    approval = ctx.metadata.get("approval_record")
    if approval:
        print("decision         :", approval.decision.value if approval.decision else None)
        print("reviewer         :", approval.reviewer)
    if not resolved:
        print("(no draft reached the approval gate - check the error above)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python run_demo.py <thread_id> [--approve]")
        print("  get a thread id with:")
        print("  python -c \"from src.integrations.gmail.client import GmailClient; import json;"
              " print(json.dumps(GmailClient().list_threads(query='in:inbox', max_results=5), indent=2))\"")
        sys.exit(1)
    tid = sys.argv[1]
    do_approve = "--approve" in sys.argv[2:]
    asyncio.run(main(tid, do_approve))
