# Agent Bus Protocol Specification (Whorl-Integrated)

## 1. Overview
The Agent Bus Protocol defines the standardized message exchange format and routing semantics for agents interacting with the Whorl bus system. It prioritizes observability, strict schema enforcement, and asynchronous message delivery.

## 2. Message Format (JSON-RPC 2.0 Inspired)
Each bus message MUST contain:
- `id`: UUID (String)
- `sender_id`: String
- `receiver_id`: String (or 'broadcast')
- `timestamp`: ISO-8601 String
- `payload`: Object (Pydantic-validated)
- `type`: String (e.g., 'command', 'data', 'event', 'error')

## 3. Bus Interaction Pattern
1. Agents emit messages to `WhorlBus.emit()`.
2. Bus validates message schema.
3. Bus routes message based on `receiver_id` or broadcast rules.
4. Receiver processes, optionally emits a reply message (linked by `id`).

## 4. Error Handling
- All bus-level errors MUST be wrapped in a standard `error` payload.
- Message timeout after 5 seconds of inactivity.
- Dead letter queue (DLQ) for undeliverable messages.
