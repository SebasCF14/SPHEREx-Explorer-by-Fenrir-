# SPHEREx Explorer v14 — Stage 1 integration patch

This ZIP is a **merge overlay** for the existing `spherex-explorer` repository, not a replacement for the React frontend.

Read `docs/STAGE1_MIGRATION.md` before merging.

Run from the repository root:

```powershell
python scripts/verify_stage1.py
python -m backend.spherex_explorer.main
```

Scientific dependencies must be installed before the Flask startup command.
