import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from src.agent.models.fact_check import Claim, FactCheck, Occurrence
from src.agent.models.fact_check_state import FactCheckState
from src.agent.models.transcript import Transcript, TranscriptTurn
from src.agent.nodes.verify_claims import verify_claims
from src.log_context import task_id


class VerifyClaimsTests(unittest.TestCase):
    def test_zero_claims_log_completion(self) -> None:
        token = task_id.set("example-task")
        try:
            with self.assertLogs("src.agent.nodes.verify_claims", level="INFO") as logs:
                transcript = Transcript(turns=[TranscriptTurn(timestamp="00:00:01", speaker="Host", text="Hello")])
                result = asyncio.run(verify_claims(FactCheckState(transcript=transcript), {}))
        finally:
            task_id.reset(token)

        self.assertEqual(result, {"fact_checks": []})
        self.assertTrue(any("task_id=example-task stage=verification event=completed claims=0" in line for line in logs.output))
        self.assertIsNone(task_id.get())

    def test_verification_returns_checks_in_input_order(self) -> None:
        transcript = Transcript(turns=[TranscriptTurn(timestamp="00:01", speaker="Host", text="Hello")])
        checks = [FactCheck(claim=Claim(text=str(index), occurrences=[Occurrence("00:01", "00:01")])) for index in range(6)]

        async def verify(check: FactCheck, *args: object) -> FactCheck:
            await asyncio.sleep(0.001 * (6 - int(check.claim.text)))
            return check

        with (
            patch("src.agent.nodes.verify_claims.build_verifier", return_value=object()),
            patch("src.agent.nodes.verify_claims.verify_one", new=AsyncMock(side_effect=verify)) as verifier,
        ):
            result = asyncio.run(verify_claims(FactCheckState(transcript=transcript, pending_checks=checks), {}))

        self.assertEqual(result["fact_checks"], checks)
        self.assertEqual(verifier.await_count, len(checks))
