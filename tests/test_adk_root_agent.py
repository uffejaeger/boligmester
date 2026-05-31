import unittest

from apartment_agents.adk.root_agent import build_root_agent_definition, serialize_agent_tree


class AdkRootAgentDefinitionTest(unittest.TestCase):
    def test_root_definition_contains_expected_sub_agents(self) -> None:
        root = build_root_agent_definition()

        self.assertEqual(root.name, "buyer_committee")
        self.assertEqual(len(root.children), 5)
        self.assertEqual(
            [child.name for child in root.children],
            [
                "listing_agent",
                "market_comps_agent",
                "danish_credit_agent",
                "negotiation_agent",
                "red_team_agent",
            ],
        )

    def test_serialized_tree_includes_instructions(self) -> None:
        tree = serialize_agent_tree(build_root_agent_definition())

        self.assertEqual(tree["name"], "buyer_committee")
        self.assertIn("Delegate work", tree["instruction"])
        self.assertEqual(tree["children"][0]["name"], "listing_agent")
        self.assertTrue(tree["children"][0]["instruction"])


if __name__ == "__main__":
    unittest.main()
