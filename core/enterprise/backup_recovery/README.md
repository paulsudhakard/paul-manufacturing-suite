# core/enterprise/backup_recovery/

Automatic backups, version history, undo checkpoints, crash/settings/job
recovery (Architecture v3 §14.3, TDD §26–27).

**Arrives:** incrementally as the features they depend on land (e.g. job
recovery depends on Sprint 11's WorkflowInstance persistence); no single
sprint in 0–20 is dedicated solely to this — flagged for explicit scheduling
if a dedicated sprint turns out to be needed.
