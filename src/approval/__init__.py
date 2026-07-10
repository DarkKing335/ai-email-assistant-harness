"""
approval — Human-in-the-Loop approval gate.

This package manages the asynchronous pausing of the workflow to wait for human review.
"""
from src.approval.gate import ApprovalGate, approval_gate

__all__ = [
    "ApprovalGate",
    "approval_gate",
]
