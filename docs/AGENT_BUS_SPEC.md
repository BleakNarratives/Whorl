# Agent Bus Protocol — Syntax General Intelligence

**Version:** 0.2.0
**Date:** 2026-08-28
**Status:** IMPLEMENTED LOCAL CORE / INTEGRATION IN PROGRESS

This document describes the currently implemented filesystem bus and separates
verified behavior from planned protocol features. The implementation is local,
opt-in, and intentionally conservative: the bus transports and archives
messages, but does not execute service interventions itself.

## 1. What This Is

The agent bus is a local message-passing backbone for Whorl modules. Agents and
adapters communicate through JSON envelopes rather than direct cross-module
calls. The filesystem is the transport and the append-only event log is the
audit trail.

Current verified paths include:

- Filesystem message delivery with atomic write/rename.
- Agent registration, heartbeat, and derived stale/dead status.
- Offline Fire Drill dispatch/result routing with direct-call fallback.
- Idempotent score feedback consumption into agent state.
- Explicit acknowledgement and archive preservation.
- TTL expiry and dead-letter inspection/retry.

## 2. Design Principles

1. **Filesystem is the transport.** No network, sockets, broker, or external
   service is required. Messages live under `~/.whorl/bus/`.
2. **Atomic delivery.** Messages are written to a temporary file and exposed by
   rename, so incomplete temporary files are not inbox messages.
3. **Audit preservation.** Acknowledgement archives the full envelope; it does
   not erase the delivery record.
4. **Fail safely.** Unknown recipients become dead letters. Malformed files are
   skipped by readers rather than crashing the scan.
5. **Idempotency is explicit.** A caller may provide `message_id`; repeated
   sends return the existing message instead of creating another delivery.
6. **No automatic intervention execution.** The bus can carry proposals and
   requests, but service changes remain outside this local core.

## 3. Directory Layout

```text
~/.whorl/bus/
  inbox/{recipient}/       unread delivered envelopes
  outbox/                  reserved for producer-side output
  dead/                    dead-letter records with reason and envelope
  archive/{recipient}/    acknowledged envelopes
  log/bus.jsonl            append-only bus events
  registry.json            agent manifest and heartbeat state
  clock                    monotonic integer clock
```

## 4. Message Envelope

```json
{
  "id": "msg_a1b2c3d4",
  "timestamp": "2026-08-28T21:00:00Z",
  "clock": 1234,
  "from": "fire_drill",
  "to": "yvette",
  "type": "task.dispatch",
  "priority": "normal",
  "ttl_s": 300,
  "reply_to": "fire_drill",
  "payload": {
    "scenario_id": "offline_probe",
    "timeout_s": 60
  }
}
```

Required fields are `id`, `timestamp`, `clock`, `from`, `to`, `type`, and
`payload`. `payload` must be a JSON object. `priority` is `normal` or `urgent`;
`ttl_s` is a non-negative integer and defaults to 300 seconds.

The bus clock is incremented when an envelope is created. It is monotonic within
the local bus directory, not a distributed clock and not a substitute for a
wall-clock timestamp.

## 5. Message Types

The following names are defined by the broader protocol. The starred entries
have verified local implementation coverage.

- Agent lifecycle: `agent.register*`, `agent.heartbeat*`,
  `agent.deregister` (defined, not yet implemented).
- Tasks: `task.dispatch*`, `task.result*`, `task.cancel` (defined only),
  `task.timeout` (expiry is implemented; automatic timeout event emission is
  not yet implemented).
- State: `state.update`, `state.query`, `state.response` (defined only).
- Feedback: `score.record*`, `score.ack` (defined; consumer acknowledgement is
  implemented), `drill.sweep_start`, `drill.sweep_done` (defined only).
- Service management: `guard.check`, `guard.status`, `guard.restart`,
  `guard.result` (names defined; live daemon integration remains partial).
- Signal Loom lifecycle: `signal.detected`, `hotspot.ranked`,
  `intervention.proposed`, `intervention.simulated`,
  `intervention.executed`, `impact.measured`, `recovery.verified` are supported
  as validated event records; publication is opt-in.

## 6. Acknowledgements

Reading an inbox is non-destructive:

```python
messages = bus.read("agent-name")
```

A consumer explicitly acknowledges a message after successful processing:

```python
bus.acknowledge("agent-name", message_id)
```

Acknowledgement behavior:

1. Locate the matching JSON envelope in `inbox/{recipient}/`.
2. Move it to `archive/{recipient}/` using atomic rename.
3. If the archive is on another filesystem, copy atomically and then unlink the
   inbox file.
4. Append `message_acknowledged` to `log/bus.jsonl`.

Acknowledgement is not deletion. A missing message returns `False`; archived
messages are retained for audit and are not re-delivered by `read()`.

The score consumer uses the envelope ID as an idempotency key: it applies a
score once, records consumption in agent state, and acknowledges the message.
Malformed or incomplete score messages remain available for inspection rather
than being silently acknowledged.

CLI:

```text
whorl bus ack <recipient> <message_id>
```

## 7. TTL and Expiry

Each message carries `timestamp` and `ttl_s`. A message is expired when the
current wall-clock time exceeds `timestamp + ttl_s`. TTL `0` therefore expires
immediately on the next expiry scan.

Expiry is explicit and local:

```python
expired = bus.expire("agent-name")
```

or:

```text
whorl bus expire [recipient]
```

For every expired inbox message, the bus:

1. Writes a dead-letter record under `dead/` with reason `ttl_expired`.
2. Preserves the original envelope inside that record.
3. Appends a dead-letter event to `log/bus.jsonl`.
4. Removes the pending inbox copy.

`bus.read()` invokes expiry for the selected recipient by default, so ordinary
reads do not return expired work. Pass `include_expired=True` only for forensic
inspection of an inbox before expiry. Expiry does not currently emit a separate
`task.timeout` envelope, notify `reply_to`, or mutate agent registry status.
Those are future protocol work.

## 8. Delivery and Idempotency

A recipient is deliverable when it is registered or is `broadcast`. Unknown
recipients are written directly to `dead/` with reason
`recipient_not_registered`.

Callers can supply a stable `message_id`:

```python
bus.send(..., message_id="score-run-42")
```

If that ID is already present in an inbox, archive, or dead-letter record, the
existing envelope is returned and no duplicate inbox file is created. This is a
local filesystem check, not a distributed transaction or locking protocol.

Dead letters can be inspected and retried explicitly:

```text
whorl bus dead [--reason REASON] [--limit N]
whorl bus retry <message_id>
```

Retries use a new ID prefixed with `retry_`; the original dead-letter record is
preserved. Retry remains operator-controlled and does not automatically delete
or suppress repeated failures.

## 9. Agent Registration and Heartbeats

`bus.register()` writes or updates an agent entry with version, capabilities,
heartbeat interval, registration time, and last heartbeat. `bus.heartbeat()`
updates liveness metadata. `registry_status()` derives:

- `stale` after more than three heartbeat intervals.
- `dead` after more than five minutes or five heartbeat intervals, whichever is
  later.

CLI:

```text
whorl bus registry
whorl bus registry --name yvette --version v3 --capability respond
```

Deregistration, heartbeat CLI actions, and automatic dispatch skipping for dead
agents are specified but not yet complete in the current local core.

## 10. Offline Fire Drill and Feedback Integration

The Fire Drill adapter provides an opt-in offline path:

1. Publish `task.dispatch` to the registered target.
2. Invoke the supplied offline responder.
3. Publish `task.result` to the requested recipient.
4. Fall back to the direct callback if bus delivery fails.
5. Publish `score.record` through the score adapter when requested.
6. Consume score records into agent state with message-ID idempotency.

The canonical live Fire Drill runner remains unchanged. Bus-native operation is
not globally enabled until parity and operational tests are complete.

## 11. Current Limitations

The following are deliberate current limitations, not implied guarantees:

1. **Single local filesystem.** There is no distributed locking, replication,
   remote transport, encryption, or multi-host ordering.
2. **No daemon dispatcher.** Delivery is file-based; agents or adapters must
   call `read`, `expire`, and acknowledgement explicitly.
3. **TTL uses wall-clock time.** The monotonic bus clock orders messages but does
   not measure elapsed TTL.
4. **Expiry is not full timeout handling.** It creates `ttl_expired` dead
   letters but does not yet emit `task.timeout`, notify senders, or mark agents
   stale.
5. **Priority is metadata only.** Inbox reads currently sort by filename/clock;
   urgent-first scheduling is not yet enforced by the core reader.
6. **No inbox size limits.** Message-size and inbox-depth safeguards remain
   planned.
7. **Broadcast is not fan-out.** `broadcast` is a shared recipient directory;
   per-agent copy semantics are not implemented.
8. **Dead-letter retry is manual.** There is no retry backoff, retry limit, or
   automatic quarantine policy.
9. **State integration is opt-in.** The bus does not write agent state directly;
   consumers own that responsibility.
10. **Service integration is partial.** The bus does not itself call systemd,
    payment services, providers, or external devices.
11. **Malformed records are skipped.** Readers preserve unreadable files for
    inspection but do not currently create structured malformed-record alerts.
12. **Crash safety is filesystem-scoped.** Atomic rename protects individual
    message publication, not a multi-message transaction.

## 12. CLI Surface

Implemented commands:

```text
whorl bus status
whorl bus send --sender ... --recipient ... --type ... --payload ...
whorl bus read <recipient> [--limit N] [--include-expired]
whorl bus ack <recipient> <message_id>
whorl bus expire [recipient]
whorl bus dead [--reason REASON] [--limit N]
whorl bus retry <message_id>
whorl bus registry [--name ...]
```

## 13. Implementation Status

### Phase 1 — Bus Core: **PARTIALLY COMPLETE**

- [x] Atomic JSON message write/read.
- [x] Local monotonic clock.
- [x] Registry registration and heartbeat primitives.
- [x] Inbox delivery and append-only bus log.
- [x] Unknown-recipient dead letters.
- [x] Explicit acknowledgement with archive preservation.
- [x] TTL expiry to dead letters.
- [x] Dead-letter listing and explicit retry.
- [x] Caller-supplied message IDs and duplicate-send suppression.
- [x] CLI status/send/read/ack/expire/dead/retry/registry commands.
- [ ] Inbox/message size safeguards.
- [ ] Priority-aware reader.
- [ ] Structured malformed-message alerts.

### Phase 2 — Agent Integration: **PARTIAL**

- [x] Offline Fire Drill dispatch/result adapter.
- [x] Direct-call fallback.
- [x] Idempotent score-record consumer.
- [ ] Startup registration for all agents.
- [ ] Outbox worker and heartbeat loop.
- [ ] Full daemon dispatcher.

### Phase 3 — Feedback and Signal Loom: **FOUNDATION COMPLETE**

- [x] `score.record` publication and consumption adapter.
- [x] Signal Loom hotspot schema and deterministic ranking.
- [x] MemGuard and overseer read-only normalization adapters.
- [ ] Degradation alert policy.
- [ ] Automatic branch/rewind policy.
- [ ] Sweep scheduling.

### Phase 4 — Overseer Integration: **PARTIAL / OPERATOR-GATED**

- [x] Existing overseer guard path remains operational.
- [ ] Fully bus-native service management.
- [ ] Bus-native SENSE/HARVEST/GUARD/SLINGSHOT event routing.
- [ ] Automated bus health remediation.

## 14. Verification

The local Whorl regression set currently covers bus, Fire Drill, score feedback,
Signal Loom, and adapter behavior through the standard-library test runner.
The latest full discovery found **25 tests: 24 passed and 1 import error**. The
sole error is the optional Glint test, which requires unavailable `cv2` and
NumPy packages; this is documented in `docs/TESTING.md` and is not a bus or
Signal Loom regression.

No network access, provider call, payment action, service restart, deployment,
or external-device operation is part of this verification.

---

*This specification tracks the implemented local core; unchecked items are not
claims of current behavior.*
