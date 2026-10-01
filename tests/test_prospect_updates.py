import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from gtm_agent import data_service, gtm_agent


class _ScoreResult:
    def __init__(self, justification):
        self.justification = justification

    def model_dump(self):
        return {
            "score": 100,
            "max_score": 100,
            "justification": self.justification,
            "rubric_breakdown": {
                "revenue_fit": 100,
                "tech_stack_match": 100,
                "segment_fit": 100,
                "component_max": 100,
            },
        }


class _ScoringStub:
    def invoke(self, messages):
        prompt = messages[1]["content"]
        prospect = json.loads(prompt.split("\n\nProspect profile:\n", 1)[1])
        required = data_service.get_offering("OFFER-10004")["required_tech_stack"]
        missing = [technology for technology in required
                   if technology not in prospect["tech_stack"]]
        justification = "All required technologies are present."
        if missing:
            justification = f"Missing: {', '.join(missing)}"
        return _ScoreResult(justification)


class ProspectUpdateTest(unittest.TestCase):
    def setUp(self):
        self.prospect_id = "LEAD-39002"
        self.original_stack = list(data_service.PROSPECTS[self.prospect_id]["tech_stack"])
        data_service._PROFILES.pop(self.prospect_id, None)

    def tearDown(self):
        data_service.PROSPECTS[self.prospect_id]["tech_stack"] = self.original_stack
        data_service._PROFILES.pop(self.prospect_id, None)

    def test_update_persists_invalidates_profile_and_scores_updated_stack(self):
        initial_profile = gtm_agent.build_prospect_profile.invoke(
            {"prospect_id": self.prospect_id}
        )["prospect_profile"]
        self.assertNotIn("Terraform", initial_profile["tech_stack"])

        update = data_service.update_prospect_info(self.prospect_id, "Terraform")

        self.assertTrue(update["updated"])
        self.assertIn("Terraform", data_service.fetch_tech_stack(self.prospect_id))
        updated_profile = gtm_agent.build_prospect_profile.invoke(
            {"prospect_id": self.prospect_id}
        )["prospect_profile"]
        self.assertIn("Terraform", updated_profile["tech_stack"])

        with patch.object(gtm_agent, "_scoring_llm", _ScoringStub()):
            score = gtm_agent.score_prospect.invoke({
                "prospect_profile": updated_profile,
                "offering": data_service.get_offering("OFFER-10004"),
            })

        self.assertNotIn("Terraform", score["justification"])


if __name__ == "__main__":
    unittest.main()
