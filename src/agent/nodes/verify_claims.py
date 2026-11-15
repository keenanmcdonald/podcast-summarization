import asyncio
import logging

from langchain_core.runnables import RunnableConfig, RunnableLambda

from src.agent.models.fact_check import FactCheck
from src.agent.models.fact_check_state import FactCheckState
from src.agent.verifier import build_verifier, verify_one
from src.log_context import claim_index, log_context

MAX_CONCURRENT_CHECKS = 4
logger = logging.getLogger(__name__)


async def verify_claims(state: FactCheckState, config: RunnableConfig) -> dict[str, list[FactCheck]]:
    logger.info("%s stage=verification event=start claims=%d", log_context(), len(state.pending_checks))
    if not state.pending_checks:
        logger.info("%s stage=verification event=completed claims=0", log_context())
        return {"fact_checks": []}
    agent = build_verifier()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)

    async def verify_one_claim(check: FactCheck, config: RunnableConfig) -> FactCheck:
        return await verify_one(check, state.transcript, agent, config)

    async def run_check(index: int, check: FactCheck) -> FactCheck:
        async with semaphore:
            token = claim_index.set(index)
            try:
                verifier = RunnableLambda(verify_one_claim, name=f"verify_claim_{index}")
                return await verifier.ainvoke(check, config=config)
            finally:
                claim_index.reset(token)

    async with asyncio.TaskGroup() as tasks:
        pending = [
            tasks.create_task(run_check(index, check))
            for index, check in enumerate(state.pending_checks, start=1)
        ]
    logger.info("%s stage=verification event=completed claims=%d", log_context(), len(pending))
    return {"fact_checks": [task.result() for task in pending]}
