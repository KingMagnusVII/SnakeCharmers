# Correctness hardening report

## Saved-layout validation

| layout | assignments | known_violations | unverified_checks | unknown_references |
| --- | --- | --- | --- | --- |
| baseline | 150 | 0 | 450 | 0 |
| optimized | 150 | 0 | 450 | 0 |

Unallocated or infeasible SKUs recorded by the saved baseline: 50.

## Separate evidence files

Each layout has a structured full validation file plus separate known-violation, unverified-safety, unknown-reference, and aggregate-load CSVs. `unallocated_or_infeasible_skus.csv` preserves the saved baseline exclusions.

## Interpretation

Known violations are only checks with sufficient input data and configured limits. `UNVERIFIED` records indicate missing observed inventory or unknown hazard/handling attributes; they are not safety-compliance results. Aggregate loads use the configured representative inventory fallback where observed inventory is unavailable.

## Defects corrected

- The former validator skipped unknown references, modeled stock volume, aggregate shelf/rack loads, and structured uncertainty results.
- Baseline and optimizer used different candidate checks; both now use the same known-feasibility predicate.
- The heavy-SKU shelf-height rule was implicit and was not enforced during optimizer candidate selection. It is now explicit configuration.
- Evaluation now handles CSV string completion flags and empty-route arithmetic consistently.

## Implemented validation rules

SKU/location references; assignment and location uniqueness; dimension orientation and boundary fit; modeled bin volume; location, shelf, and rack load; heavy-SKU ergonomics; configured known incompatibilities; invalid physical inputs; and unverified inventory/hazard/handling inputs.

## Files changed

- `src/feasibility.py` — structured validation and the shared feasibility predicate.
- `src/baseline.py`, `src/optimizer.py` — common candidate validation.
- `src/evaluation.py` — completion-count and denominator hardening.
- `config/simulation_config.json` — explicit ergonomic and no-inferred-incompatibility assumptions.
- `tests/test_engine.py` — deterministic constraint and evaluation tests.
- `scripts/validate_saved_layouts.py` — non-regenerating saved-layout validation and evidence generation.
- `README.md` and `final_validation_report.md` — evidence/limitation qualification.

## Test execution

The complete suite was run after Python compilation checks:

```text
11 passed in 1.39s
```

No tests failed or were skipped. They use synthetic fixtures only; no Kaggle access, source-data download, or full pipeline execution was required.

## Remaining limitations

Aggregate-load checks model one configured representative unit because observed inventory is unavailable. All saved-layout hazard and handling checks remain unverified because Olist provides `UNSPECIFIED` values. This work does not validate routing realism, affinity use in optimization, EDA breadth, or the dashboard.
