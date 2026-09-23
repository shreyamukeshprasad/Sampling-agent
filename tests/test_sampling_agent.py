from decimal import Decimal
import unittest

from counterparty_sampling import Transaction, sample_alert


def transaction(
    row: int,
    amount: str,
    counterparty: str,
    *,
    focal_side: str = "originator",
    rule_id: str | None = None,
) -> Transaction:
    if focal_side == "originator":
        return Transaction(
            source_row=row,
            alert_id="A1",
            rule_id=rule_id or "AML-TEST-ORG",
            amount=Decimal(amount),
            originator_id="FOCAL",
            originator_name="Focal Entity",
            beneficiary_id=counterparty,
            beneficiary_name=f"Party {counterparty}",
        )
    return Transaction(
        source_row=row,
        alert_id="A1",
        rule_id=rule_id or "AML-TEST-BEN",
        amount=Decimal(amount),
        originator_id=counterparty,
        originator_name=f"Party {counterparty}",
        beneficiary_id="FOCAL",
        beneficiary_name="Focal Entity",
    )


class TopThreeAndThreeTests(unittest.TestCase):
    def test_unions_value_and_volume_selections(self):
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

        result = sample_alert(rows, "Top 3 & 3")

        selected = {item.party_id for item in result.selected}
        self.assertEqual(
            selected,
            {"HIGH", "MID", "MID2", "FREQUENT", "VOLUME2", "VOLUME3"},
        )
        self.assertNotIn("FOCAL", {item.party_id for item in result.population})

    def test_volume_tie_is_broken_by_cumulative_value(self):
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

        result = sample_alert(rows, "Top 3 & 3")
        volume_ranks = {item.party_id: item.volume_rank for item in result.population}

        self.assertEqual(volume_ranks, {"A": 1, "B": 2, "C": 3, "D": 4})

    def test_selects_all_when_population_has_fewer_than_three(self):
        rows = [
            transaction(2, "100", "A"),
            transaction(3, "75", "B", focal_side="beneficiary"),
        ]

        result = sample_alert(rows, "Top 3 & 3")

        self.assertEqual({item.party_id for item in result.selected}, {"A", "B"})
        self.assertTrue(
            all(item.selected_because_population_under_three for item in result.selected)
        )

    def test_pools_counterparties_from_both_sides(self):
        rows = [
            transaction(2, "100", "A", focal_side="originator"),
            transaction(3, "75", "B", focal_side="beneficiary"),
            transaction(4, "50", "C", focal_side="originator"),
        ]

        result = sample_alert(rows, "Top 3 & 3")

        self.assertEqual({item.party_id for item in result.population}, {"A", "B", "C"})
        self.assertEqual(result.focal_party_id, "FOCAL")


if __name__ == "__main__":
    unittest.main()
