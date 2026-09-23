# Counterparty Sampling Agent

This project applies auditable counterparty-sampling rules to alerted transaction
data. Calculations are deterministic; the instruction text is validated as policy
input and is not used to perform arithmetic.

The currently supported method is **Top 3 & 3**:

- aggregate cumulative value and transaction volume by counterparty;
- pool originator-side and beneficiary-side counterparties;
- exclude the inferred focal party;
- select the top three by cumulative value;
- select the top three by volume, breaking volume ties by cumulative value;
- return the union, or the full population when fewer than three counterparties exist.

## Run

```powershell
python sampling_agent.py `
  --instructions-file sampling_instructions.txt `
  --mapping "C:\path\to\SAM_Rules.xlsx" `
  --transactions "C:\path\to\AML_Transactions_Full.xlsx" `
  --output sampling_results.xlsx
```

The output workbook contains a run summary, sampled counterparties, and the complete
ranked counterparty population. If focal-party inference is ambiguous, rerun with an
explicit per-alert override:

```powershell
python sampling_agent.py ... --focal-party "SAM1-251811=ROYC"
```

Mapping methods other than `Top 3 & 3` fail explicitly until their methodology is
implemented.

## Test

```powershell
python -m unittest discover -s tests -v
```
