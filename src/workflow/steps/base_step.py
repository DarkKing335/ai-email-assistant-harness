"""
base_step.py — Interface cốt lõi cho mọi Workflow Step.
"""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

# Dùng TYPE_CHECKING để tránh lỗi circular import (import vòng tròn)
if TYPE_CHECKING:
    from src.models.workflow_context import WorkflowContext

class BaseWorkflowStep(ABC):
    """
    Khuôn mẫu bắt buộc cho mọi Pipeline Step.
    Mọi step cụ thể đều phải kế thừa từ class này và triển khai các phương thức bên dưới.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Trả về tên của bước (phục vụ cho việc định danh và ghi log)."""
        pass

    @abstractmethod
    async def execute(self, ctx: "WorkflowContext") -> "WorkflowContext":
        """
        Thực thi logic chính của bước xử lý.
        
        Args:
            ctx (WorkflowContext): Đối tượng chứa trạng thái và dữ liệu hiện tại của email.
            
        Returns:
            WorkflowContext: Đối tượng context sau khi đã được xử lý và cập nhật dữ liệu.
        """
        pass