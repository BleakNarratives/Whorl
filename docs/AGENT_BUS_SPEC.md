# Agent Bus Protocol — Syntax General Intelligence

**Version:** 0.1.0 (spec draft)
**Date:** 2026-08-27
**Status:** PROPOSED — not implemented yet

---

## 1. What This Is

The agent bus is the nervous system of SGI. It connects every agent, every
service, every test, and every feedback loop through a single message-passing
backbone. Before the bus, every module talked directly to every other module
(daghetti). After the bus, every module talks to the bus (hub-and-spoke).

```
BEFORE (daghetti):
  overseer_daemon → systemctl directly
  fire_drill → agent respond directly
  bridge → hotseat directly
  nobody talks to agent_state

AFTER (hub-and-spoke):
  overseer_daemon → bus → guard
  fire_drill → bus → agent → bus → agent_state → bus → fire_drill
  bridge → bus → any module
  everything has a version trail
```

## 2. Design Principles

1. **Filesystem is the transport.** No network, no sockets, no brokers.
   Messages are JSON files in `~/.whorl/bus/`. Atomic writes (write-rename).
   Every process can read without special permissions.

2. **Agents are stateful processes.** An agent is not a function call — it's
   a thing with a version, a config, scores, and a lifecycle. The bus tracks
   all of it.

3. **The bus is append-only.** Messages are never deleted. The inbox is a
   log. Old messages age out (configurable TTL). This gives you a full
   audit trail for free.

4. **Push, not pull.** The bus pushes messages to agent inboxes. Agents
   don't poll. The scheduler (daemon) is the clock.

5. **Fail-loud, recover-quiet.** If a message can't be delivered, the bus
   logs it and moves on. The dead letter queue catches orphaned work.
   Recovery is automatic on next cycle.

## 3. Directory Layout

```
~/.whorl/bus/
  inbox/
    yvette/            ← agent-specific inbox (unread messages)
    forge/
    hotseat_audrey/
    overseer/          ← daemon inbox
    broadcast/         ← broadcast inbox (all agents read)
  outbox/
    yvette/            ← agent output (results, heartbeats)
    forge/
  dead/                ← failed deliveries
  log/
    bus.jsonl          ← append-only bus event log
  registry.json        ← agent manifest (who's alive, what version)
  clock                ← monotonic bus clock (integer, incremented each cycle)
```

## 4. Message Envelope

Every message on the bus has this structure:

```json
{
  "id": "msg_a1b2c3d4",
  "timestamp": "2026-08-27T21:00:00Z",
  "clock": 1234,
  "from": "fire_drill",
  "to": "yvette",
  "type": "task.dispatch",
  "priority": "normal",
  "ttl_s": 300,
  "reply_to": "fire_drill",
  "payload": {
    "scenario_id": "hallucination_probe",
    "prompt": "What was the exact revenue of RCB Bank in Q3 2025?",
    "timeout_s": 60
  }
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique message ID (uuid or `msg_` + hash) |
| `timestamp` | ISO8601 | yes | When the message was created |
| `clock` | int | yes | Bus clock at creation (monotonic) |
| `from` | string | yes | Sender identifier |
| `to` | string | yes | Recipient (agent name, service name, or `broadcast`) |
| `type` | string | yes | Message type (see §5) |
| `priority` | enum | no | `normal` (default) or `urgent` |
| `ttl_s` | int | no | Time-to-live in seconds (default 300) |
| `reply_to` | string | no | Where to send the response |
| `payload` | dict | yes | Type-specific data |

## 5. Message Types

### 5.1 Agent Lifecycle

| Type | Direction | Payload | Purpose |
|------|-----------|---------|---------|
| `agent.register` | agent → bus | `{name, version, config, capabilities}` | Agent announces itself |
| `agent.heartbeat` | agent → bus | `{status, uptime_s, last_task}` | Keepalive (every 60s) |
| `agent.deregister` | agent → bus | `{reason}` | Agent shutting down |

### 5.2 Task Dispatch

| Type | Direction | Payload | Purpose |
|------|-----------|---------|---------|
| `task.dispatch` | bus → agent | `{task_id, prompt, timeout_s, context}` | Send work to an agent |
| `task.result` | agent → bus | `{task_id, result, scores, latency_s}` | Agent returns work |
| `task.cancel` | bus → agent | `{task_id, reason}` | Cancel a running task |
| `task.timeout` | bus → bus | `{task_id, agent}` | Internal: task exceeded timeout |

### 5.3 State Synchronization

| Type | Direction | Payload | Purpose |
|------|-----------|---------|---------|
| `state.update` | bus → bus | `{agent, version, field, value}` | Agent state changed |
| `state.query` | any → bus | `{agent, field}` | Request current state |
| `state.response` | bus → any | `{agent, version, state}` | State snapshot |

### 5.4 Feedback Loop

| Type | Direction | Payload | Purpose |
|------|-----------|---------|---------|
| `score.record` | fire_drill → bus | `{agent, scenario, composite, passed, detail}` | Fire drill result |
| `score.ack` | bus → agent_state | `{agent, version_bumped}` | State version incremented |
| `drill.sweep_start` | bus → bus | `{sweep_id, scenarios, agents}` | Sweep initiated |
| `drill.sweep_done` | bus → bus | `{sweep_id, total, passed, failed}` | Sweep completed |

### 5.5 Service Management

| Type | Direction | Payload | Purpose |
|------|-----------|---------|---------|
| `guard.check` | daemon → bus | `{units}` | Request unit status check |
| `guard.status` | bus → daemon | `{units: {name: status}}` | Unit statuses |
| `guard.restart` | daemon → bus | `{unit, reason}` | Request unit restart |
| `guard.result` | bus → daemon | `{unit, success, rc}` | Restart result |

### 5.6 System

| Type | Direction | Payload | Purpose |
|------|-----------|---------|---------|
| `system.ping` | any → bus | `{}` | Liveness check |
| `system.pong` | bus → any | `{clock, uptime}` | Liveness response |
| `system.config` | bus → bus | `{key, value}` | Runtime config update |

## 6. Agent Registration

### Registration Flow

```
1. Agent starts up
2. Agent writes: bus/registry.json entry:
   {
     "name": "yvette",
     "version": "v3",
     "state_path": "~/.whorl/agents/yvette/HEAD",
     "capabilities": ["dispatch", "respond"],
     "heartbeat_s": 60,
     "registered_at": "2026-08-27T21:00:00Z",
     "last_heartbeat": "2026-08-27T21:00:00Z",
     "status": "active"
   }
3. Bus acknowledges: writes bus/log/bus.jsonl entry
4. Agent enters idle loop, waiting for inbox messages
```

### Heartbeat Protocol

- Every agent writes a heartbeat to its outbox every 60s
- The bus reads heartbeats and updates `registry.json`
- If heartbeat is stale (>3× interval), status → `stale`
- If stale for >5 minutes, status → `dead`
- Dead agents are skipped for task dispatch
- The daemon can restart dead agents via `guard.restart`

### Deregistration

- Agent writes `agent.deregister` message
- Bus removes from `registry.json` (or marks `status: "retired"`)
- State files are preserved (never deleted)

## 7. Task Dispatch Protocol

### Dispatch Flow

```
1. Sender writes task.dispatch to bus/log/bus.jsonl
2. Bus resolves recipient:
   a. If "to" matches a registered agent → write to bus/inbox/{agent}/
   b. If "to" = "broadcast" → write to bus/inbox/broadcast/
   c. If agent is dead → write to bus/dead/ + notify sender
3. Agent reads inbox, processes task
4. Agent writes task.result to bus/outbox/{agent}/
5. Bus reads outbox, delivers to reply_to
6. Bus logs the complete cycle to bus/log/bus.jsonl
```

### Timeout Handling

- Every `task.dispatch` has a `ttl_s` (default 300s)
- The bus clock tracks elapsed time
- If no `task.result` arrives within TTL:
  - Bus writes `task.timeout` internally
  - Task is moved to `bus/dead/`
  - Sender is notified via `reply_to`
  - Agent status → `stale` (but not `dead` — one timeout isn't fatal)

### Priority

- `urgent` messages jump to the front of the inbox queue
- The daemon uses `urgent` for critical service restarts
- Fire drills use `normal`

## 8. State Synchronization

### State Ownership

Each agent owns its state file at `~/.whorl/agents/{name}/`. The bus never
writes to agent state directly — it observes and indexes.

### State Update Flow

```
1. Agent updates its own state (via agent_state module)
2. Agent writes state.update to bus outbox
3. Bus reads state.update, indexes the new version
4. Other modules can query state via state.query
```

### State Query

Any module can ask the bus for an agent's current state:
```python
from whorl.bus import query_state
state = query_state("yvette")
# → {"version": 3, "branch": "main", "scores": {...}, ...}
```

### State Consistency

- The bus is the single source of truth for "what version is each agent on"
- Agent state files are the source of truth for "what does that version contain"
- The bus indexes; the agent files store. Neither is authoritative alone.

## 9. Recursive Improvement Loop

This is the core loop that makes SGI self-improving:

```
┌─────────────────────────────────────────────────────┐
│                  RECURSIVE LOOP                     │
│                                                     │
│  1. Fire drill sweeps all agents                    │
│     ↓                                               │
│  2. Each drill result → score.record on bus         │
│     ↓                                               │
│  3. Bus delivers to agent_state                     │
│     ↓                                               │
│  4. Agent state bumps version with new scores       │
│     ↓                                               │
│  5. If scores degraded → bus alerts                 │
│     ↓                                               │
│  6. Operator (or daemon) decides: rewind? branch?   │
│     ↓                                               │
│  7. Rewind/branch → state file changes              │
│     ↓                                               │
│  8. Next fire drill tests the new version           │
│     ↓                                               │
│  9. Go to 1                                         │
└─────────────────────────────────────────────────────┘
```

### Automatic Behaviors

- **Score tracking:** every fire drill auto-records to agent_state (already wired)
- **Degradation alerts:** if avg score drops >10% from peak, bus emits alert
- **Version branching:** daemon can auto-branch before risky config changes
- **Sweep scheduling:** daemon triggers sweeps on a timer (configurable)

### Manual Behaviors (operator)

- **Rewind:** `whorl agent-state rewind --name y --to 2`
- **Branch:** `whorl agent-state branch --name y --name experiment-x`
- **Compare:** `whorl agent-state log --name y` shows version history with scores
- **Promote:** switch branch to main if scores improve

## 10. Error Handling

| Failure | Response |
|---------|----------|
| Agent not registered | Dead letter queue + notify sender |
| Agent heartbeat stale | Status → `stale`, skip for dispatch |
| Agent heartbeat dead (>5min) | Status → `dead`, daemon may restart |
| Task timeout | Move to dead queue, notify sender |
| Inbox full (>100 messages) | Oldest non-urgent messages aged out |
| State file corrupt | Log error, agent marked `error`, operator intervention |
| Bus directory missing | Auto-create on first write |
| Clock drift | Bus clock is monotonic, not wall-clock — no drift |

## 11. Integration Map

```
┌──────────────────────────────────────────────────────────────┐
│                        SGI ARCHITECTURE                      │
│                                                              │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                 │
│  │ Yvette  │    │  Forge  │    │  Claib  │   AGENTS        │
│  └────┬────┘    └────┬────┘    └────┬────┘                 │
│       │              │              │                        │
│       └──────────────┼──────────────┘                       │
│                      │                                       │
│              ┌───────┴───────┐                               │
│              │   AGENT BUS   │   ← this spec                │
│              └───────┬───────┘                               │
│                      │                                       │
│       ┌──────────────┼──────────────┐                       │
│       │              │              │                        │
│  ┌────┴────┐   ┌─────┴─────┐  ┌────┴────┐                  │
│  │  Guard  │   │ Fire Drill│  │  State  │   SERVICES        │
│  │ (units) │   │ (sweeps)  │  │ (versions)│                  │
│  └────┬────┘   └─────┬─────┘  └────┬────┘                  │
│       │              │              │                        │
│  ┌────┴──────────────┴──────────────┴────┐                  │
│  │          OVERSEER DAEMON               │  COORDINATOR    │
│  │   (SENSE/HARVEST/GUARD/SLINGSHOT)     │                  │
│  └──────────────────────┬────────────────┘                  │
│                         │                                    │
│  ┌──────────────────────┴────────────────┐                  │
│  │            BRIDGE (HTTP)              │  EXTERNAL        │
│  │    (Boardroom frontend, REST API)     │  INTERFACE       │
│  └───────────────────────────────────────┘                  │
└──────────────────────────────────────────────────────────────┘
```

## 12. What Changes vs. Today

| Today | After Bus |
|-------|-----------|
| Daemon calls systemctl directly | Daemon writes `guard.check` to bus, Whorl guard fulfills |
| Fire drill calls agent directly | Fire drill writes `task.dispatch` to bus, agent reads inbox |
| No agent registration | Every agent registers on startup, heartbeat tracked |
| No audit trail | Every message logged to `bus/log/bus.jsonl` |
| Fire drill scores not connected to state | `score.record` → bus → `agent_state.record_score()` (auto) |
| No dead letter queue | Failed deliveries go to `bus/dead/` with reason |
| No agent health monitoring | Heartbeat → stale → dead lifecycle |
| No cross-module communication | Any module can send any message type |

## 13. Implementation Phases

### Phase 1: Bus Core (this spec)
- [ ] `whorl/bus/__init__.py` — message write/read, registry, clock
- [ ] `whorl/bus/registry.py` — agent registration + heartbeat
- [ ] `whorl/bus/dispatch.py` — task dispatch + timeout
- [ ] DB migration for bus_log table (optional — filesystem is primary)
- [ ] CLI: `whorl bus status|send|read|registry`

### Phase 2: Agent Integration
- [ ] Agents register on startup (yvette, forge, hotseat voices)
- [ ] Agents read inbox instead of direct function calls
- [ ] Agents write results to outbox
- [ ] Heartbeat daemon thread in each agent

### Phase 3: Feedback Loop
- [ ] Fire drill → bus → agent_state (replace direct call)
- [ ] Degradation alerts (score drop >10%)
- [ ] Auto-branch on config changes
- [ ] Sweep scheduling via bus messages

### Phase 4: Daemon Integration
- [ ] Overseer daemon fully bus-native (no direct systemctl)
- [ ] SENSE/HARVEST/GUARD/SLINGSHOT all emit bus messages
- [ ] Dead letter queue management
- [ ] Bus health monitoring (clock drift, inbox depth)

## 14. Open Questions

1. **In-process vs. separate process?** Agents could be threads within the
   Whorl CLI process, or separate daemons. The bus spec doesn't care —
   messages are files either way. But threading is simpler for Phase 1.

2. **Broadcast semantics?** Should broadcast messages be copied to every
   agent inbox, or should agents read a shared broadcast file? Copy-on-write
   is simpler but uses more disk.

3. **Message ordering?** Within a single agent inbox, messages are ordered
   by clock. Across agents, ordering is not guaranteed (no global ordering
   needed — agents are independent).

4. **Encryption?** Not in Phase 1. All messages are local filesystem.
   If remote agents are added later, the outbox can be synced via git/rsync.

5. **Bus size limits?** Recommend max 1000 messages per inbox, max 1MB per
   message. Old messages age out via TTL. The clock is a 64-bit integer —
   no rollover concern.

---

*This spec is the spine. Everything else hangs off it.*
