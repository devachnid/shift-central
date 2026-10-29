# AMG Shift Central

Staff rotas and leave management for the practice: one rota grid for every
team (GPs included), and leave calculated correctly in hours for everyone.
It replaces FindMyShift. Sign-in is through Practice HR
(`devachnid/practice-hr`), and GP rotas stay in step with the GP rota app
(`devachnid/rota`).

## Requirements

The practice manager's requirements, approved on 29 October 2026, are in
[docs/requirements/](docs/requirements/README.md): thirteen documents from
`00-overview.md` to `12-decisions-and-open-questions.md`. Start with the
overview, then the leave policy (`05`) and its worked examples (`06`), which
become the leave calculation's tests.

Logo files and brand colours are in [docs/brand/](docs/brand/) and described
in the requirements README.

Design specs and implementation plans will go in `docs/superpowers/specs/`
and `docs/superpowers/plans/`, as in the rota and HR repositories.

## Develop

The grid and the colour picker are built from `frontend/` with Vite: `cd frontend && npm install && npm run build` writes `static/dist/`, which is committed. Run the build before committing a frontend change; CI fails on a stale bundle. `npm run dev` rebuilds on save.
