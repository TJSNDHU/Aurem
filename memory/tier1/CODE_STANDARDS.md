# AUREM CODE STANDARDS — Non-Negotiable Rules

Every line of code ORA writes must follow these rules. No exceptions.

## Backend (FastAPI + MongoDB)

- All routes MUST be prefixed `/api` (e.g. `/api/leads`, never `/leads`).
- Use `from motor.motor_asyncio import AsyncIOMotorClient` (NEVER PyMongo).
- Read env vars with `os.environ.get("KEY")` — no hardcoded defaults.
- Pydantic models on every request body AND response.
- `datetime.now(timezone.utc)` — never `datetime.utcnow()`.
- Always exclude `_id` from MongoDB responses (projection `{"_id": 0}` or
  pop it before returning). `ObjectId` is not JSON serialisable.
- Python type hints required on every function signature.
- No unpinned `pip install` — always pin in requirements.txt, and never
  rewrite requirements.txt manually; use `pip install X && pip freeze`.
- Every endpoint needs a pytest test in `/app/backend/tests/test_iter*.py`.
- 80% line coverage minimum on new routers.

## Frontend (React + Tailwind)

- Functional components only — no class components.
- `process.env.REACT_APP_BACKEND_URL` for every fetch — never localhost.
- `data-testid` on every interactive element + every critical info element.
- `yarn add` — never `npm install`.
- Shadcn components from `/app/frontend/src/components/ui/`.
- No emojis as icons — use lucide-react or FontAwesome.
- Components <50 lines ideally; split if larger.
- Named exports for components, default export for pages.

## MongoDB Adherence Checklist

Before returning ANY data that touched Mongo, ask:
1. Did I query? → projected away `_id`?
2. Did I insert/update? → Mongo mutated my dict (added `_id`); am I
   returning that same dict?
3. Any ObjectId fields (`created_by`, `parent_id`, `author_id`)?
4. Did I spread (`{**doc}`) or copy a document? → carries `_id`.
5. Aggregation / `find_one_and_update` / upsert? → same rules.

If any answer is "yes" or "maybe", trace the response dict before returning.

## Forbidden Patterns

- `datetime.utcnow()` — use `datetime.now(timezone.utc)`.
- Hardcoded URLs like `http://localhost:8001` — use env vars.
- Bare `except:` — always catch a specific exception.
- `from pymongo import MongoClient` — use Motor async.
- Returning `{"_id": ObjectId(...)}` to JSON.
- Modifying `package.json` directly — use `yarn add`.
- Modifying `requirements.txt` directly — use `pip install && pip freeze`.
- Deleting keys from `.env`.
- Backwards-compat shims for unused code (delete instead).

## Testing Discipline

- Every bug fix gets a regression test.
- Test files live in `/app/backend/tests/test_iter{N}_{descr}.py`.
- Use the external `REACT_APP_BACKEND_URL` for API tests — never
  `http://localhost:8001` (that doesn't go through ingress).
- Run `python -m pytest tests/ -q -p no:cacheprovider --tb=line` before
  declaring any change complete.

## Naming Conventions

- Snake_case for Python, camelCase for JS, kebab-case for filenames.
- Iter markers: `iter 331a` for this sprint. Bump for new work.
- Test file names: `test_iter{N}_{descr}.py`.
