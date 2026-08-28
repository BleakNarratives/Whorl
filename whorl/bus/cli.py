from __future__ import annotations

import json

from . import acknowledge, dead_letters, expire, read, register, registry_status, retry_dead_letter, send, status


def cmd_status(_args):
    print(json.dumps(status(), indent=2, sort_keys=True))


def cmd_send(args):
    payload = json.loads(args.payload)
    message = send(args.sender, args.recipient, args.type, payload,
                   priority=args.priority, ttl_s=args.ttl, reply_to=args.reply_to,
                   message_id=args.message_id)
    print(json.dumps(message, indent=2, sort_keys=True))


def cmd_read(args):
    print(json.dumps(read(args.recipient, limit=args.limit,
                          include_expired=args.include_expired), indent=2))


def cmd_ack(args):
    if not acknowledge(args.recipient, args.message_id):
        raise SystemExit(f"message not found: {args.message_id}")
    print(f"acknowledged {args.message_id}")


def cmd_expire(args):
    expired = expire(args.recipient)
    print(json.dumps({"expired": len(expired), "message_ids": [m.get("id") for m in expired]}, indent=2))


def cmd_dead(args):
    print(json.dumps(dead_letters(reason=args.reason, limit=args.limit), indent=2, sort_keys=True))


def cmd_retry(args):
    result = retry_dead_letter(args.message_id)
    if result is None:
        raise SystemExit(f"dead letter not found: {args.message_id}")
    print(json.dumps(result, indent=2, sort_keys=True))


def cmd_registry(args):
    if args.name:
        entry = register(args.name, args.version, capabilities=args.capability,
                         heartbeat_s=args.heartbeat or 60)
        print(json.dumps(entry, indent=2, sort_keys=True))
    elif args.heartbeat:
        raise SystemExit("--heartbeat requires --name")
    else:
        print(json.dumps(registry_status(), indent=2, sort_keys=True))


def add_parser(sub):
    bus = sub.add_parser("bus", help="Filesystem-backed agent bus")
    bus_sub = bus.add_subparsers(dest="bus_cmd")
    bus_sub.add_parser("status", help="Show bus, inbox, and registry status")

    send_parser = bus_sub.add_parser("send", help="Send a JSON message")
    send_parser.add_argument("--sender", required=True)
    send_parser.add_argument("--recipient", required=True)
    send_parser.add_argument("--type", required=True)
    send_parser.add_argument("--payload", required=True, help="JSON object")
    send_parser.add_argument("--priority", choices=("normal", "urgent"), default="normal")
    send_parser.add_argument("--ttl", type=int, default=300)
    send_parser.add_argument("--reply-to")
    send_parser.add_argument("--message-id")

    read_parser = bus_sub.add_parser("read", help="Read an inbox")
    read_parser.add_argument("recipient")
    read_parser.add_argument("--limit", type=int, default=100)
    read_parser.add_argument("--include-expired", action="store_true")

    ack_parser = bus_sub.add_parser("ack", help="Archive an inbox message")
    ack_parser.add_argument("recipient")
    ack_parser.add_argument("message_id")

    expire_parser = bus_sub.add_parser("expire", help="Move expired messages to dead letters")
    expire_parser.add_argument("recipient", nargs="?")

    dead_parser = bus_sub.add_parser("dead", help="Inspect dead letters")
    dead_parser.add_argument("--reason")
    dead_parser.add_argument("--limit", type=int, default=100)

    retry_parser = bus_sub.add_parser("retry", help="Retry one dead letter")
    retry_parser.add_argument("message_id")

    registry_parser = bus_sub.add_parser("registry", help="List or register agents")
    registry_parser.add_argument("--name")
    registry_parser.add_argument("--version", default="0.1.0")
    registry_parser.add_argument("--capability", action="append", default=[])
    registry_parser.add_argument("--heartbeat", type=int, default=None)

    return {
        ("bus", "status"): cmd_status,
        ("bus", "send"): cmd_send,
        ("bus", "read"): cmd_read,
        ("bus", "ack"): cmd_ack,
        ("bus", "expire"): cmd_expire,
        ("bus", "dead"): cmd_dead,
        ("bus", "retry"): cmd_retry,
        ("bus", "registry"): cmd_registry,
    }
