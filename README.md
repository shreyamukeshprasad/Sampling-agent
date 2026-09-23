# Counterparty Sampling Agent

The implementation is contained in `build_1`:

- `agent.py` reads the three inputs, calculates counterparties, and creates samples.
- `sampling_prompt.txt` contains the detailed Top 3 & 3 methodology.
- `requirements.txt` lists the required Python package.
- `test_agent.py` tests the calculations and rule-level grouping.
- `sampling_results_by_rule.xlsx` is the result generated from the sample data.

Sampling is performed separately for every `Alert ID + Rule ID` combination. The
agent first calculates cumulative value and transaction volume for every eligible
counterparty in that rule, then applies the mapped sampling method.

The output workbook contains:

- one combined sheet of sampled counterparties;
- one combined sheet of all counterparty calculations and rankings;
- one separate worksheet for each rule sample.

## Run

From the `build_1` folder:

```powershell
python agent.py `
  --prompt sampling_prompt.txt `
  --mapping "C:\path\to\SAM_Rules.xlsx" `
  --transactions "C:\path\to\AML_Transactions_Full.xlsx" `
  --output sampling_results_by_rule.xlsx
```

If focal-party inference is ambiguous, provide an override for the affected alert
and rule:

```powershell
python agent.py ... --focal-party "ALERT_ID|RULE_ID=PARTY_ID"
```

## Test

```powershell
python -m unittest -v test_agent.py
```

Only `Top 3 & 3` is currently implemented. Other mapped sampling methods stop with a
clear error until their methodology is supplied.
