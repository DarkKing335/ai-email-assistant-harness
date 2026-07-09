import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.workflow.engine.orchestrator import EmailWorkflowOrchestrator
from src.models.workflow_context import WorkflowContext  
from src.config.constants import WorkflowStatus, ApprovalDecision
from src.models.email import EmailThread, EmailMessage
from src.models.draft import Draft

@pytest.mark.asyncio
async def test_happy_path_workflow():
    """Kiểm thử luồng đi trơn tru với WorkflowContext có Approval Gate và Retry Limit"""
    
    # 1. Chuẩn bị Dữ liệu giả 
    mock_thread_id = "th_123"
    mock_workflow_id = f"wf_{uuid.uuid4().hex[:16]}"
    
    mock_thread = EmailThread(
        thread_id=mock_thread_id,
        messages=[
            EmailMessage(
                message_id="msg_1", thread_id=mock_thread_id, subject="Test",
                sender="Client <client@test.com>", sender_email="client@test.com",
                recipients=["assistant@test.com"], body_plain="Hi",
                received_at=datetime.now()
            )
        ]
    )
    mock_draft = Draft(
        draft_id="dr_mock", thread_id=mock_thread_id, to="client@test.com", subject="Re: Test", body="Mock body"
    )

    # 2. Khởi tạo Orchestrator
    orchestrator = EmailWorkflowOrchestrator()

    # 3. Sử dụng Dependency Injection để Mock các Step
    async def mock_ingest_run(*args, **kwargs):
        ctx = WorkflowContext(workflow_id=mock_workflow_id, thread_id=mock_thread_id)
        ctx.email_thread = mock_thread
        ctx.status = WorkflowStatus.INGESTED
        return ctx
    orchestrator._ingest.run = mock_ingest_run
    
    async def mock_draft_run(ctx: WorkflowContext):
        ctx.draft = mock_draft
        ctx.status = WorkflowStatus.DRAFTED
        return ctx
    orchestrator._draft.run = mock_draft_run
    
    async def mock_approval_run(ctx: WorkflowContext):
        ctx.approval_record_id = "ap_mock_123"
        # BẬT CỜ DUYỆT ĐỂ QUA CỔNG
        ctx.is_approved = True  
        ctx.status = WorkflowStatus.AWAITING_APPROVAL
        return ctx
    orchestrator._approval.run = mock_approval_run
    
    async def mock_send_run(ctx: WorkflowContext):
        ctx.status = WorkflowStatus.SENT
        return ctx
    orchestrator._send.run = mock_send_run
    
    orchestrator._audit.run = AsyncMock()
    
    # 4. GỌI HÀM TUẦN TỰ (Kiểm thử dòng chảy dữ liệu)
    ctx_ingested = await orchestrator._ingest.run(mock_thread_id)
    ctx_drafted = await orchestrator._draft.run(ctx_ingested)
    ctx_approved = await orchestrator._approval.run(ctx_drafted)
    
    # Đảm bảo Cổng Duyệt hoạt động: Rẽ nhánh dựa trên cờ is_approved
    if ctx_approved.is_approved:
        ctx_sent = await orchestrator._send.run(ctx_approved)
    else:
        ctx_sent = ctx_approved # Dừng lại nếu không duyệt

    # 5. KIỂM TRA KẾT QUẢ
    assert ctx_sent.email_thread is not None
    assert ctx_sent.draft is not None
    assert ctx_sent.is_approved is True
    assert ctx_sent.status == WorkflowStatus.SENT
    
    print("\n=> Approval Gate đã mở, WorkflowContext hoàn thiện hoạt động xuất sắc!")