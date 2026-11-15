from contextvars import ContextVar

task_id: ContextVar[str | None] = ContextVar("task_id", default=None)
