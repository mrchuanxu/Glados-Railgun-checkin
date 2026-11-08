# Disable GLaDOS Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Disable the GLaDOS/Railgun GitHub Actions workflow by renaming it outside GitHub's recognized workflow extensions while preserving its contents for restoration.

**Architecture:** Move the existing workflow from `gladosCheck.yml` to `gladosCheck.yml.disabled` without changing its bytes. Update the workflow tests to treat the renamed file as an archived configuration and explicitly reject the presence of the active `.yml` path.

**Tech Stack:** GitHub Actions YAML, Python 3.13, standard-library `unittest`, Git

**Spec:** `docs/superpowers/specs/2026-11-08-disable-glados-workflow-design.md`

## Global Constraints

- `.github/workflows/gladosCheck.yml` must not exist after the change.
- `.github/workflows/gladosCheck.yml.disabled` must preserve the original workflow content byte-for-byte.
- Do not modify `checkin.py`, secrets, state handling, exchange logic, or `.github/workflows/ehighCheck.yml`.
- The rename must disable both scheduled and manual GLaDOS workflow execution while remaining reversible by renaming the file back.
- Commit and push all local `master` commits as explicitly authorized by the user.

## Review Focus

- Leaving `gladosCheck.yml` present would keep the workflow active; `test_glados_workflow_is_disabled` must reject the active path.
- Failing to create the `.disabled` file would lose the recoverable configuration; the same test must require it.
- Editing content during the move could make restoration unsafe; record and compare the file's SHA-256 before and after the rename.
- Pointing legacy schedule tests at a missing file would break the suite; all preserved-content tests must read the `.disabled` path.
- Accidentally touching the one-hai workflow would broaden the outage; verify `ehighCheck.yml` is unchanged in the final diff.

---

### Task 1: Rename and verify the GLaDOS workflow

**Files:**
- Rename: `.github/workflows/gladosCheck.yml` → `.github/workflows/gladosCheck.yml.disabled`
- Modify: `tests/test_workflow_schedule.py`

**Interfaces:**
- Consumes: repository-relative workflow paths and the archived workflow text used by `WorkflowScheduleTests`.
- Produces: no recognized GLaDOS `.yml` workflow; a byte-identical `.disabled` archive; tests that enforce both conditions.

- [ ] **Step 1: Update tests to describe the disabled state**

In `tests/test_workflow_schedule.py`, define:

```python
WORKFLOWS_DIR = Path(__file__).parents[1] / ".github" / "workflows"
ACTIVE_WORKFLOW_PATH = WORKFLOWS_DIR / "gladosCheck.yml"
DISABLED_WORKFLOW_PATH = WORKFLOWS_DIR / "gladosCheck.yml.disabled"
```

Add:

```python
def test_glados_workflow_is_disabled(self):
    self.assertFalse(ACTIVE_WORKFLOW_PATH.exists())
    self.assertTrue(DISABLED_WORKFLOW_PATH.is_file())
```

Change the three preserved-content tests to read `DISABLED_WORKFLOW_PATH`. Keep their schedule, diagnostics, and run-history assertions unchanged.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m unittest tests.test_workflow_schedule -v`

Expected: FAIL/ERROR because `gladosCheck.yml` still exists and `gladosCheck.yml.disabled` does not.

- [ ] **Step 3: Record the original workflow hash**

Run: `shasum -a 256 .github/workflows/gladosCheck.yml`

Expected: exit status 0; save the printed hash for comparison after the rename.

- [ ] **Step 4: Rename the workflow without editing it**

Move `.github/workflows/gladosCheck.yml` to `.github/workflows/gladosCheck.yml.disabled`. Do not rewrite or normalize its contents.

- [ ] **Step 5: Verify GREEN and byte preservation**

Run: `python -m unittest tests.test_workflow_schedule -v`

Expected: all four tests PASS.

Run: `shasum -a 256 .github/workflows/gladosCheck.yml.disabled`

Expected: the hash exactly matches Step 3.

- [ ] **Step 6: Run full verification**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS with no failures or errors.

Run: `python -m py_compile tests/test_workflow_schedule.py`

Expected: exit status 0 and no output.

Run: `git diff --check`

Expected: exit status 0 and no output.

Run: `git diff --name-status HEAD^ -- .github/workflows`

Expected: only the GLaDOS workflow rename is present; `.github/workflows/ehighCheck.yml` is absent from the output.

- [ ] **Step 7: Commit the suspension**

```bash
git add .github/workflows/gladosCheck.yml .github/workflows/gladosCheck.yml.disabled tests/test_workflow_schedule.py
git commit -m "ci: disable glados check-in workflow"
```

- [ ] **Step 8: Integrate remote updates and push all authorized commits**

Fetch `origin/master`. If it advanced, rebase the local commits onto it without force-pushing, resolve only conflicts that preserve both sides' intended content, and rerun the complete verification from Step 6.

Run: `git push origin master`

Expected: a fast-forward update of `origin/master`, followed by identical `HEAD` and `origin/master` commit IDs.
