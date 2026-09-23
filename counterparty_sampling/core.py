from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
import re
from typing import Iterable


class SamplingError(ValueError):
    """Raised when the supplied data cannot be sampled unambiguously."""


@dataclass(frozen=True)
class Party:
    key: str
    party_id: str
    name: str
    side: str


@dataclass(frozen=True)
class Transaction:
    source_row: int
    alert_id: str
    rule_id: str
    amount: Decimal
    originator_id: str = ""
    originator_account: str = ""
    originator_name: str = ""
    beneficiary_id: str = ""
    beneficiary_account: str = ""
    beneficiary_name: str = ""

    def parties(self) -> tuple[Party | None, Party | None]:
        return (
            _make_party(
                self.originator_id,
                self.originator_account,
                self.originator_name,
                "Originator",
            ),
            _make_party(
                self.beneficiary_id,
                self.beneficiary_account,
                self.beneficiary_name,
                "Beneficiary",
            ),
        )


@dataclass
class CounterpartySummary:
    key: str
    party_id: str
    name: str
    cumulative_value: Decimal
    transaction_volume: int
    sides: tuple[str, ...]
    source_rows: tuple[int, ...]
    value_rank: int = 0
    volume_rank: int = 0
    selected_by_value: bool = False
    selected_by_volume: bool = False
    selected_because_population_under_three: bool = False

    @property
    def selected(self) -> bool:
        return (
            self.selected_by_value
            or self.selected_by_volume
            or self.selected_because_population_under_three
        )

    @property
    def selection_reason(self) -> str:
        reasons: list[str] = []
        if self.selected_because_population_under_three:
            reasons.append("All counterparties: population under 3")
        if self.selected_by_value:
            reasons.append("Top 3 cumulative value")
        if self.selected_by_volume:
            reasons.append("Top 3 transaction volume")
        return "; ".join(reasons)


@dataclass
class AlertSamplingResult:
    alert_id: str
    sampling_method: str
    focal_party_key: str
    focal_party_id: str
    focal_party_name: str
    focal_inference: str
    rule_ids: tuple[str, ...]
    population: list[CounterpartySummary] = field(default_factory=list)

    @property
    def selected(self) -> list[CounterpartySummary]:
        return [counterparty for counterparty in self.population if counterparty.selected]


@dataclass
class _Accumulator:
    values: Decimal = Decimal("0")
    source_rows: set[int] = field(default_factory=set)
    sides: set[str] = field(default_factory=set)
    ids: Counter[str] = field(default_factory=Counter)
    names: Counter[str] = field(default_factory=Counter)


def _clean(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _normalize(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "", _clean(value).upper())


def _make_party(party_id: object, account: object, name: object, side: str) -> Party | None:
    clean_id = _clean(party_id)
    clean_account = _clean(account)
    clean_name = _clean(name)
    if clean_id:
        key = f"ID:{_normalize(clean_id)}"
    elif clean_account:
        key = f"ACCOUNT:{_normalize(clean_account)}"
    elif clean_name:
        key = f"NAME:{_normalize(clean_name)}"
    else:
        return None
    return Party(key=key, party_id=clean_id, name=clean_name, side=side)


def _rule_focal_side(rule_id: str) -> str | None:
    tokens = {token for token in re.split(r"[^A-Z0-9]+", rule_id.upper()) if token}
    if tokens.intersection({"BEN", "BENE", "BENEFICIARY"}):
        return "Beneficiary"
    if tokens.intersection({"ORG", "ORI", "ORIG", "ORIGINATOR"}):
        return "Originator"
    return None


def _representative(counter: Counter[str]) -> str:
    if not counter:
        return ""
    return sorted(counter.items(), key=lambda item: (-item[1], item[0].upper()))[0][0]


def _infer_focal_party(transactions: list[Transaction]) -> tuple[str, str]:
    directional_counts: Counter[str] = Counter()
    all_counts: Counter[str] = Counter()
    originator_keys: set[str] = set()
    beneficiary_keys: set[str] = set()

    for transaction in transactions:
        originator, beneficiary = transaction.parties()
        if originator:
            all_counts[originator.key] += 1
            originator_keys.add(originator.key)
        if beneficiary:
            all_counts[beneficiary.key] += 1
            beneficiary_keys.add(beneficiary.key)

        focal_side = _rule_focal_side(transaction.rule_id)
        directional_party = originator if focal_side == "Originator" else beneficiary
        if directional_party and focal_side:
            directional_counts[directional_party.key] += 1

    if directional_counts:
        ordered = directional_counts.most_common()
        if len(ordered) == 1 or ordered[0][1] > ordered[1][1]:
            return ordered[0][0], "Inferred from Rule ID direction and party frequency"

    cross_side = originator_keys.intersection(beneficiary_keys)
    if cross_side:
        ordered = sorted(cross_side, key=lambda key: (-all_counts[key], key))
        if len(ordered) == 1 or all_counts[ordered[0]] > all_counts[ordered[1]]:
            return ordered[0], "Inferred as the recurring party on both transaction sides"

    raise SamplingError(
        "Could not infer one focal party unambiguously. Supply a focal party ID override."
    )


def _resolve_override(transactions: list[Transaction], focal_party_id: str) -> str:
    normalized = _normalize(focal_party_id)
    matches = {
        party.key
        for transaction in transactions
        for party in transaction.parties()
        if party
        and (
            _normalize(party.party_id) == normalized
            or party.key.removeprefix("ID:") == normalized
        )
    }
    if not matches:
        raise SamplingError(f"Focal party override {focal_party_id!r} was not found in the alert.")
    if len(matches) > 1:
        raise SamplingError(f"Focal party override {focal_party_id!r} matched multiple parties.")
    return matches.pop()


def sample_alert(
    transactions: Iterable[Transaction],
    sampling_method: str,
    focal_party_id: str | None = None,
) -> AlertSamplingResult:
    transaction_list = list(transactions)
    if not transaction_list:
        raise SamplingError("An alert must contain at least one transaction.")

    alert_ids = {transaction.alert_id for transaction in transaction_list}
    if len(alert_ids) != 1:
        raise SamplingError("sample_alert accepts transactions for exactly one Alert ID.")
    if sampling_method.strip().casefold() != "top 3 & 3":
        raise SamplingError(f"Unsupported sampling method: {sampling_method}")

    if focal_party_id:
        focal_key = _resolve_override(transaction_list, focal_party_id)
        focal_inference = "Provided explicitly"
    else:
        focal_key, focal_inference = _infer_focal_party(transaction_list)

    focal_ids: Counter[str] = Counter()
    focal_names: Counter[str] = Counter()
    accumulators: dict[str, _Accumulator] = defaultdict(_Accumulator)

    for transaction in transaction_list:
        parties = [party for party in transaction.parties() if party]
        for party in parties:
            if party.key == focal_key:
                if party.party_id:
                    focal_ids[party.party_id] += 1
                if party.name:
                    focal_names[party.name] += 1

        # A transaction contributes once to each distinct non-focal party appearing on it.
        unique_parties = {party.key: party for party in parties if party.key != focal_key}
        for party in unique_parties.values():
            accumulator = accumulators[party.key]
            accumulator.values += abs(transaction.amount)
            accumulator.source_rows.add(transaction.source_row)
            accumulator.sides.add(party.side)
            if party.party_id:
                accumulator.ids[party.party_id] += 1
            if party.name:
                accumulator.names[party.name] += 1

    population = [
        CounterpartySummary(
            key=key,
            party_id=_representative(accumulator.ids),
            name=_representative(accumulator.names),
            cumulative_value=accumulator.values,
            transaction_volume=len(accumulator.source_rows),
            sides=tuple(sorted(accumulator.sides)),
            source_rows=tuple(sorted(accumulator.source_rows)),
        )
        for key, accumulator in accumulators.items()
    ]

    by_value = sorted(
        population,
        key=lambda item: (-item.cumulative_value, -item.transaction_volume, item.key),
    )
    by_volume = sorted(
        population,
        key=lambda item: (-item.transaction_volume, -item.cumulative_value, item.key),
    )
    for rank, counterparty in enumerate(by_value, start=1):
        counterparty.value_rank = rank
    for rank, counterparty in enumerate(by_volume, start=1):
        counterparty.volume_rank = rank

    if len(population) < 3:
        for counterparty in population:
            counterparty.selected_because_population_under_three = True
    else:
        for counterparty in by_value[:3]:
            counterparty.selected_by_value = True
        for counterparty in by_volume[:3]:
            counterparty.selected_by_volume = True

    population.sort(key=lambda item: (not item.selected, item.value_rank, item.key))
    return AlertSamplingResult(
        alert_id=alert_ids.pop(),
        sampling_method="Top 3 & 3",
        focal_party_key=focal_key,
        focal_party_id=_representative(focal_ids),
        focal_party_name=_representative(focal_names),
        focal_inference=focal_inference,
        rule_ids=tuple(sorted({transaction.rule_id for transaction in transaction_list})),
        population=population,
    )
