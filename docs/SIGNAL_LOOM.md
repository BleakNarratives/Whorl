# Signal Loom

Signal Loom is Whorl's read-only method for finding concentrated operational
friction and proposing bounded, reversible improvements.

## Public vocabulary

- **Signal:** an observed fact from telemetry or a test.
- **Hotspot:** a normalized cluster of related signals.
- **Intervention:** a proposed bounded change; Signal Loom does not execute it.
- **Validation:** a controlled check of the expected effect.
- **Recovery:** confirmation that the system returned to an acceptable state.

## Lifecycle events

```text
signal.detected
hotspot.ranked
intervention.proposed
intervention.simulated
intervention.executed
impact.measured
recovery.verified
```

Every event carries the hotspot ID as its correlation ID and retains source and
provenance metadata.

## Ranking

The initial deterministic priority score is:

```text
impact × leverage × confidence × reversibility
```

Tie-breaking is deterministic: confidence, reversibility, category, then ID.
Severity is descriptive and never authorizes an action by itself.

## Safety boundaries

- Signal Loom is read-only in the foundation phase.
- Hotspots require provenance and a rollback plan.
- Proposed interventions default to dry-run and operator approval.
- No action is taken solely because a signal is intense.
- Production, payment, wallet, device, and deployment actions remain outside
  the automatic path.
- The Whorl bus carries audit events; source systems remain authoritative for
  their own state.
