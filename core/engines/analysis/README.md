# core/engines/analysis/

`ManufacturingAnalysisEngine`, `ScoreCalculator`, `TimeEstimator`,
`MaterialUsageEstimator` — score/difficulty/risk/time/material-usage math,
generic across products; calls `ProductPlugin.analyze()` for product-specific
judgment (Architecture v3 §4).

**Arrives:** Sprint 9.
