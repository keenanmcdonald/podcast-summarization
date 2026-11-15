from contextvars import ContextVar

task_id: ContextVar[str | None] = ContextVar("task_id", default=None)
claim_index: ContextVar[int | None] = ContextVar("claim_index", default=None)


def log_context() -> str:
    context = f"task_id={task_id.get()}"
    index = claim_index.get()
    if index is not None:
        context += f" claim_index={index}"
    return context
