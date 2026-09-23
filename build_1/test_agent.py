from decimal import Decimal
from pathlib import Path
import unittest

from agent import Transaction, sample_one_rule, sample_transaction_groups


def transaction(
    row: int,
    amount: str,
    counterparty: str,
    *,
    rule_id: str = "RULE-ORG-1",
    focal_side: str = "originator",
) -> Transaction:
    common = {
        "source_row": row,
        "alert_id": "ALERT-1",
        "rule_id": rule_id,
        "amount": Decimal(amount),
    }
    if focal_side == "originator":
        return Transaction(
            **common,
            originator_id="FOCAL",
            originator_name="Focal Entity",
            beneficiary_id=counterparty,
            beneficiary_name=f"Party {counterparty}",
        )
    return Transaction(
        **common,
        originator_id=counterparty,
        originator_name=f"Party {counterparty}",
        beneficiary_id="FOCAL",
        beneficiary_name="Focal Entity",
    )


class RuleSamplingTests(unittest.TestCase):
    def test_value_and_volume_samples_are_combined(self):
        rows = [
            transaction(2, "1000", "HIGH"),
            transaction(3, "400", "MID"),
            transaction(4, "300", "MID2"),
            transaction(5, "10", "FREQUENT"),
            transaction(6, "10", "FREQUENT"),
            transaction(7, "10", "FREQUENT"),
            transaction(8, "10", "VOLUME2"),
            transaction(9, "10", "VOLUME2"),
            transaction(10, "10", "VOLUME3"),
            transaction(11, "10", "VOLUME3"),
        ]

        sample = sample_one_rule(rows, "Top 3 & 3")

        self.assertEqual(
            {item.party_id for item in sample.sampled_counterparties},
            {"HIGH", "MID", "MID2", "FREQUENT", "VOLUME2", "VOLUME3"},
        )

    def test_volume_tie_uses_cumulative_value(self):
        rows = [
            transaction(2, "100", "A"),
            transaction(3, "100", "A"),
            transaction(4, "70", "B"),
            transaction(5, "70", "B"),
            transaction(6, "50", "C"),
            transaction(7, "50", "C"),
            transaction(8, "40", "D"),
            transaction(9, "40", "D"),
        ]

        sample = sample_one_rule(rows, "Top 3 & 3")
        ranks = {item.party_id: item.volume_rank for item in sample.calculations}

        self.assertEqual(ranks, {"A": 1, "B": 2, "C": 3, "D": 4})

    def test_all_counterparties_are_selected_when_fewer_than_three(self):
        rows = [
            transaction(2, "100", "A"),
            transaction(3, "75", "B"),
        ]

        sample = sample_one_rule(rows, "Top 3 & 3")

        self.assertEqual(
            {item.party_id for item in sample.sampled_counterparties},
            {"A", "B"},
        )
        self.assertTrue(
            all(item.selected_as_full_population for item in sample.sampled_counterparties)
        )

    def test_run_creates_a_separate_sample_for_each_rule(self):
        prompt_path = Path(__file__).with_name("sampling_prompt.txt")
        prompt = prompt_path.read_text(encoding="utf-8")
        mapping = {
            "RULE-ORG-1": "Top 3 & 3",
            "RULE-BEN-2": "Top 3 & 3",
            "RULE-ORG-3": "Top 3 & 3",
        }
        rows = [
            transaction(2, "100", "A", rule_id="RULE-ORG-1"),
            transaction(
                3,
                "200",
                "B",
                rule_id="RULE-BEN-2",
                focal_side="beneficiary",
            ),
            transaction(4, "300", "C", rule_id="RULE-ORG-3"),
        ]

        samples = sample_transaction_groups(prompt, mapping, rows)

        self.assertEqual(len(samples), 3)
        self.assertEqual(
            {sample.rule_id for sample in samples},
            {"RULE-ORG-1", "RULE-BEN-2", "RULE-ORG-3"},
        )
        self.assertTrue(all(len(sample.sampled_counterparties) == 1 for sample in samples))


if __name__ == "__main__":
    unittest.main()
