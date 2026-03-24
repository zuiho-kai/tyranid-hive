# Clowder-Style Web Demo Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a chat-first web console that can submit and run `solo / trial / chain / swarm` tasks through real Codex execution with visible progress.

**Architecture:** Keep the current task/event/dispatcher/Codex adapter core, then add a thin "mission" API and a typed stage-event protocol on top. Rebuild the dashboard around a central chat console that consumes those stage events and exposes mode-specific process detail like Clowder AI.

**Tech Stack:** FastAPI, SQLAlchemy async, asyncio event bus, React 19, TypeScript, Vite, Codex CLI

---

### Task 1: Mission API Contract

**Files:**
- Create: `src/greyfield_hive/api/missions.py`
- Modify: `src/greyfield_hive/main.py`
- Test: `tests/test_missions_api.py`

**Step 1: Write the failing test**

```python
async def test_submit_mission_creates_and_dispatches_task(client):
    response = await client.post("/api/missions", json={
        "title": "Build a parser",
        "description": "Need chain execution",
        "mode": "chain",
        "auto_run": True,
    })
    assert response.status_code == 201
    body = response.json()
    assert body["task"]["exec_mode"] == "chain"
    assert body["run"]["started"] is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_missions_api.py -v`
Expected: FAIL because `/api/missions` does not exist

**Step 3: Write minimal implementation**

Create a mission endpoint that:
- creates a task
- writes requested mode into `exec_mode`
- stores mode config in `task.meta`
- optionally requests dispatch immediately

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_missions_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_missions_api.py src/greyfield_hive/api/missions.py src/greyfield_hive/main.py
git commit -m "feat: add mission submission api"
```

### Task 2: Stage Event Protocol

**Files:**
- Modify: `src/greyfield_hive/services/event_bus.py`
- Modify: `src/greyfield_hive/services/task_service.py`
- Modify: `src/greyfield_hive/workers/orchestrator.py`
- Modify: `src/greyfield_hive/workers/dispatcher.py`
- Test: `tests/test_workers.py`

**Step 1: Write the failing test**

```python
async def test_dispatcher_emits_stage_progress_events(...):
    # submit task, consume ws/bus events
    assert "task.stage.started" in event_types
    assert "task.stage.completed" in event_types
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_workers.py -k stage -v`
Expected: FAIL because the events are missing

**Step 3: Write minimal implementation**

Add stable event types for:
- `task.submitted`
- `task.analysis.started/completed`
- `task.mode.selected`
- `task.execution.started`
- `task.stage.started/progress/completed/failed`
- `task.execution.completed/failed`

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_workers.py -k stage -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/greyfield_hive/services/event_bus.py src/greyfield_hive/services/task_service.py src/greyfield_hive/workers/orchestrator.py src/greyfield_hive/workers/dispatcher.py tests/test_workers.py
git commit -m "feat: add typed execution stage events"
```

### Task 3: Fix Four-Mode Execution Core

**Files:**
- Modify: `src/greyfield_hive/services/mode_router.py`
- Modify: `src/greyfield_hive/services/trial_race.py`
- Modify: `src/greyfield_hive/services/chain_runner.py`
- Modify: `src/greyfield_hive/services/swarm_runner.py`
- Test: `tests/test_trial_race.py`
- Test: `tests/test_chain_runner.py`
- Test: `tests/test_swarm_runner.py`

**Step 1: Write the failing tests**

```python
def test_swarm_runner_persists_progress_to_task_id(...):
    ...

def test_mode_router_uses_meta_defined_mode_config(...):
    ...
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_trial_race.py tests/test_chain_runner.py tests/test_swarm_runner.py -v`
Expected: FAIL on current process/reporting bugs

**Step 3: Write minimal implementation**

Fix:
- swarm progress write target
- mode config parsing
- state progression after mode completion
- mode-specific stage progress publishing
- safer fallback behavior for malformed meta

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_trial_race.py tests/test_chain_runner.py tests/test_swarm_runner.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/greyfield_hive/services/mode_router.py src/greyfield_hive/services/trial_race.py src/greyfield_hive/services/chain_runner.py src/greyfield_hive/services/swarm_runner.py tests/test_trial_race.py tests/test_chain_runner.py tests/test_swarm_runner.py
git commit -m "fix: stabilize four-mode execution flow"
```

### Task 4: Chat-First Dashboard API Client

**Files:**
- Modify: `dashboard/src/api.ts`
- Test: `dashboard/src` manual smoke via build

**Step 1: Write the failing test**

For this repo, use a compile-level failure:

```ts
const mission = await createMission(...)
expectTypeOf(mission.task.exec_mode).toEqualTypeOf<string | null>()
```

**Step 2: Run test to verify it fails**

Run: `npm run build`
Expected: FAIL until new mission types and helpers exist

**Step 3: Write minimal implementation**

Add:
- mission request/response types
- typed stage event helpers
- task run helper methods

**Step 4: Run test to verify it passes**

Run: `npm run build`
Expected: PASS

**Step 5: Commit**

```bash
git add dashboard/src/api.ts
git commit -m "feat: add mission api client"
```

### Task 5: Chat-First Dashboard Layout

**Files:**
- Modify: `dashboard/src/App.tsx`
- Modify: `dashboard/src/components/ChannelSidebar.tsx`
- Modify: `dashboard/src/components/TrunkChat.tsx`
- Modify: `dashboard/src/components/DetailPanel.tsx`
- Modify: `dashboard/src/App.css`
- Modify: `dashboard/src/index.css`

**Step 1: Write the failing test**

Use a manual UI acceptance target:
- central composer can submit mission
- task lifecycle appears in chat timeline
- mode panels show active step

**Step 2: Run check to verify current UI fails**

Run: `npm run build`
Expected: current UX still lacks chat-first mission submission and process view

**Step 3: Write minimal implementation**

Implement:
- centered mission composer
- mode presets + advanced config
- conversation timeline mapped from stage events
- right-side inspector with current phase and active synapses
- left-side channel grouping matching Trunk / Trial / Chain / Swarm / Ledger

**Step 4: Run test to verify it passes**

Run: `npm run build`
Expected: PASS

**Step 5: Commit**

```bash
git add dashboard/src/App.tsx dashboard/src/components/ChannelSidebar.tsx dashboard/src/components/TrunkChat.tsx dashboard/src/components/DetailPanel.tsx dashboard/src/App.css dashboard/src/index.css
git commit -m "feat: rebuild dashboard as chat-first console"
```

### Task 6: Static Asset and App Wiring

**Files:**
- Modify: `src/greyfield_hive/static/index.html`
- Modify: `src/greyfield_hive/static/assets/*`
- Modify: `src/greyfield_hive/main.py`

**Step 1: Write the failing test**

```python
async def test_root_serves_new_dashboard_assets(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "Mission Console" in response.text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py -k root -v`
Expected: FAIL if new built assets are not wired

**Step 3: Write minimal implementation**

Rebuild dashboard and copy assets into `src/greyfield_hive/static`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api.py -k root -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/greyfield_hive/static/index.html src/greyfield_hive/static/assets src/greyfield_hive/main.py
git commit -m "build: ship updated dashboard assets"
```

### Task 7: Real Codex Verification

**Files:**
- Modify: `test_e2e.py`
- Modify: `README.md`

**Step 1: Write the failing test**

Use the real script to assert:
- health is ok
- mission submission works
- task produces progress

**Step 2: Run test to verify it fails**

Run: `python test_e2e.py`
Expected: FAIL until mission endpoint and UI-driven flow exist

**Step 3: Write minimal implementation**

Update the script and README to use:
- web mission flow
- Codex adapter requirement
- expected observable stages

**Step 4: Run test to verify it passes**

Run: `python test_e2e.py`
Expected: PASS with real Codex available

**Step 5: Commit**

```bash
git add test_e2e.py README.md
git commit -m "docs: update readme demo and e2e flow"
```
