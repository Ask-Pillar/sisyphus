# P4 Growth Test Results

Date: 2026-05-23
Tests: 288 passed

| Stage | Docs | CR @1 | BM25 @1 | Time |
|-------|------|-------|---------|------|
| 1: seed | 9 | 80% | 80% | 1.1s |
| 2: growth | 24 | 80% | 80% | 10.8s |
| 3: mature | 60 | 80% | 80% | 12.2s |
| 4: saturation | 150 | 80% | 80% | 17.2s |

## BCE Activation Test

8 same-topic docs, 3 identical copies → CR 0%, BM25 66%.
BCE confused by identical content. Genuinely different dense docs (tested earlier): BCE 100%, BM25 87%.

## Gate Test

30 queries, 21 docs, ContextRetriever with TreeRetriever + dual-path:
- @1: 80% (24/30)
- @3: 83% (25/30)
- @5: 83% (25/30)

5% gap from 3 queries fundamentally unanswerable with current data.

## Notes

- BCE auto-activation coded, triggers at >= 8 same-topic docs
- Identical copies confuse BCE (expected, RefinedStore deduplicates)
- Genuinely different same-topic docs: BCE +13% gain
