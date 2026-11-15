# SPHEREx Explorer — Stage 1 migration

## Scope

The five active modules from `SPHEREx-Explorer(1).zip` have been copied together into `backend/spherex_explorer/`:
`main.py`, `spherex_data.py`, `spherex_analysis.py`, `astronomy_catalogs.py`, `viewer.py`.

Scientific algorithms, HTTP route definitions, catalog fallback order, WCS overlay logic, spectrum and job handling were not deliberately changed. Changes are limited to:

1. Internal imports now use relative package paths (`from .spherex_data ...`, etc.).
2. Cache location is set by `SPHEREX_CACHE_DIR` (or `CACHE_DIR`) and otherwise defaults to the repository `cache/` directory. Existing cache files are not copied, deleted, or modified.
3. Auxiliary local diagnostic script imports the packaged module.
4. Package markers, verification script, baseline requirements, and Git exclusions are added.

## Merge into existing repository

**Do not replace or delete your existing `frontend/`, `satellite_detector/`, Firebase files or Git history.** Copy the contents of this patch ZIP into the root of the existing `spherex-explorer` repository. The archive is an overlay, not a complete replacement repository.

If you already have a root `.gitignore` or `requirements.txt`, merge the changes manually instead of overwriting them.

## Windows PowerShell (run in repository root)

```powershell
cd "C:\Users\dilan\Documents\spherex-explorer"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/verify_stage1.py
.\scripts\verify_stage1.ps1
python -m pytest backend/spherex_explorer/tests/test_stage1_structure.py -q
python -m backend.spherex_explorer.main
```

To preserve an existing scientific cache, before starting Flask run (adjust path):

```powershell
$env:SPHEREX_CACHE_DIR = "C:\path\to\existing\cache"
```

The cache directory must be writable. `.env.example` is documentation only; it is not automatically loaded.

In a second terminal, while Flask runs:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/health
```

`python main.py` from inside the package is **not** the supported invocation after conversion to relative imports. Use `python -m backend.spherex_explorer.main` from repository root.

## Stage 1 acceptance and limits

- Five Python modules present and syntactically valid.
- All local imports use package-relative paths.
- Existing API route definitions preserved.
- Cache path configurable; original cache not packaged.
- No backups, pycache, FITS, generated images, or secrets in patch.

The static checks do not prove runtime dependency compatibility, scientific correctness, external network services, job success, or quantitative WCS overlay accuracy. Those require installed dependencies and runtime/API/scientific tests.

## Next stages

Stage 2: dependency and Flask smoke tests, HTTP contract tests with mocks, API client and polling.
Stage 3+: React scientific UI and production deployment.
