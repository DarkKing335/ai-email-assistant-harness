"""
viewmodels — Pure functions mapping domain models to display dicts.

Nothing here imports a GUI toolkit, ``src.config.settings``, or any singleton.
Everything is ``(domain object) -> dict``, so the whole package runs headless
on CI with no display server and no third-party dependencies.

This is also where the real display *decisions* live — most importantly the
tri-state guardrail badge, which has to infer "not evaluated" from a boolean
that cannot express it. Those decisions get tests. Widget paint methods do not.
"""

__all__ = []
