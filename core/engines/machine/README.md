# core/engines/machine/

`MachineEngine.get_profile()`, `.recommend_settings()` — machine profiles,
power/speed tables, target-system compatibility (Architecture v3 §4,
TDD §11).

**Arrives:** alongside Sprint 7 (Rule Engine) / Sprint 9 (Analysis) as a
supporting profile lookup; full CRUD via `/v1/machines` per TDD §4.2 when
first needed by a consuming sprint.
