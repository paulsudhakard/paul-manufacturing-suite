# adapters/coreldraw/

The CorelDRAW VBA Adapter — today's only CAD/UI Adapter (Architecture v3
§2.3). Thin HTTP client only: no manufacturing threshold, formula, or
decision logic ever lives here (TDD §36).

## VBA source convention (established Sprint 0, no code yet)

VBA project files (`.cls`, `.frm`) are committed as their **text export**,
never as the binary `.gms` project file (see `.gitignore`). This makes VBA
source diffable and reviewable in git like any other code. When exporting
from the CorelDRAW VBA IDE:

1. Export each class/form module as text (IDE's "Export File..." command).
2. Commit the exported `.cls`/`.frm` text files under `src/`.
3. Never commit the compiled/binary `.gms` project itself.

**Arrives:** first real code in Sprint 3 (`clsCoreClient`,
`clsAuthTokenReader`, `frmMainToolbar`) — the health-check round trip that
validates VBA↔HTTP↔Core is viable at all.
