from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from src.config.constants import WorkflowStatus
from src.models.email import EmailThread
from src.models.draft import Draft

@dataclass
class WorkflowContext:
    """
    Đối tượng lưu trữ toàn bộ dữ liệu của một phiên làm việc.
    Đảm bảo các Layer chỉ giao tiếp bằng Domain Models, không dùng API response raw.
    """
    workflow_id: str
    thread_id: str
    
    # Trạng thái hiện tại của State Machine
    status: WorkflowStatus = WorkflowStatus.RECEIVED
    
    # Dữ liệu được nhồi vào thông qua các Pipeline Steps
    email_thread: Optional[EmailThread] = None  
    draft: Optional[Draft] = None               
    
    # --- THÔNG TIN APPROVAL GATE ---
    approval_record_id: Optional[str] = None
    is_approved: bool = False  # Đưa hẳn cờ duyệt ra ngoài để Orchestrator dễ đọc
    
    # --- CƠ CHẾ RETRY LIMIT ---
    current_retry: int = 0
    max_retries: int = 3  # Giới hạn số lần thử lại tối đa cho các tác vụ dễ tịt (như gọi LLM)
    
    # Metadata phụ (vd: số lượng token đã dùng, lý do lỗi, v.v.)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def can_retry(self) -> bool:
        """Kiểm tra xem luồng này còn quyền thử lại hay không."""
        return self.current_retry < self.max_retries
    
    def increment_retry(self) -> None:
        """Tăng biến đếm số lần thử lại."""
        self.current_retry += 1