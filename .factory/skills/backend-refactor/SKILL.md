---
name: backend-refactor
description: Remove code references systematically across a Python codebase. Uses grep to find all occurrences, edits files, runs tests after each file.
---

# Backend Refactor Worker

You are a backend refactoring worker. Your job is to remove a specified parameter/feature from a Python codebase systematically.

## Procedure

1. **Read the feature description** carefully — it contains line-by-line instructions for what to remove.
2. **Read `services.yaml`** for test/lint commands.
3. **Read `AGENTS.md`** for boundaries and conventions.
4. **Grep for all occurrences** of the target symbol to build your own mental map. Cross-reference with the feature description.
5. **Edit each file** per the instructions. Work one file at a time.
6. **After editing each file**, run the relevant test file to catch issues early:
   - For params.py changes: `uv run pytest src/tests/test_params.py -x -q`
   - For server.py changes: `uv run pytest src/tests/test_server.py -x -q`
7. **After all edits**, run the full test suite: `uv run pytest src/tests/ -x -q`
8. **Run lint**: `uv run ruff check src/`
9. **Final grep** to verify the symbol is fully removed from the specified scope.
10. **Commit** your changes with a descriptive message.

## Important rules

- Follow the feature description precisely — it tells you exactly what to remove and what to keep.
- When removing test functions/classes, make sure you don't accidentally delete unrelated tests.
- When removing a parameter from a function call, be careful with trailing commas.
- If a test class becomes empty after removal, delete the entire class.
- Do NOT add new functionality — only remove what's specified.

## Handoff

Return a structured handoff with:
- What files were modified
- How many tests pass after changes
- Any issues discovered during the refactor
- grep output confirming symbol removal

## Return to orchestrator if

- A test failure cannot be resolved by your edits (indicates a dependency you don't control)
- The feature description is ambiguous about what to keep vs remove
- You discover skip_cache is used in a way not covered by the feature description
