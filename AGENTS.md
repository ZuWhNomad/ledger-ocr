# Rules an agent cannot infer

1. If `../WORKSPACE.md` exists, read it first (local paths, release flow, where the notes live).
2. Walk the ladder before writing code: need it at all? stdlib? platform feature? existing dependency? one line?
3. The product is OFFLINE. No cloud OCR, no cloud model, and no document, file name or machine detail
   leaves `ledger_ocr/`. Ever. The single exception is `update.py`: one anonymous GET asking whether a
   newer release exists. It sends nothing, fails silently, and honours `LEDGEROCR_NO_UPDATE_CHECK`.
4. Real documents (statements, receipts, anything with a person's data) never enter the repo. Tracked fixtures
   are synthetic; real ones live in the folder named by `LEDGEROCR_PRIVATE_FIXTURES`.
5. Numbers come from deterministic extraction only. A model may flag a row; it may never write or "fix" a value.
6. No absolute paths, user names or machine names in anything tracked.
7. Plans, reviews, research and logs live in the notes folder, not here. Repo docs = `docs/ARCHITECTURE.md`
   (current state only) + each folder's `CONTEXT.md`.
8. After substantive work: update `docs/ARCHITECTURE.md` in the same commit, and add a dated entry to the
   project log in the notes folder.
9. Tests: `pytest`. Health: `run-ledger-ocr --health`. Engine choices are made from `bench/` numbers, not opinion.
