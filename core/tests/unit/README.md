# core/tests/unit/

Isolated unit tests per engine, using fixture `ProductDefinition` /
`ProductPlugin` / `RuleSet` objects — never real product plugins — so
engine tests don't break when a product plugin changes (TDD §37).

Currently contains only `test_environment_sanity.py` (Sprint 0).
