# [DNA_TAG]
# ORIGIN: Moto4_A9
# PILLAR: cli
# DEPS: whorl.bus.cli
# ROLE: Whorl CLI — bus command shims
# LAST_SYNC: 2026-09-02T04:00:00Z
# [/DNA_TAG]

"""Bus whorl commands — thin shims over whorl.bus.cli."""

from __future__ import annotations


def cmd_bus_status(args):
    from whorl.bus.cli import cmd_status
    cmd_status(args)


def cmd_bus_send(args):
    from whorl.bus.cli import cmd_send
    cmd_send(args)


def cmd_bus_read(args):
    from whorl.bus.cli import cmd_read
    cmd_read(args)


def cmd_bus_registry(args):
    from whorl.bus.cli import cmd_registry
    cmd_registry(args)


def cmd_bus_ack(args):
    from whorl.bus.cli import cmd_ack
    cmd_ack(args)


def cmd_bus_expire(args):
    from whorl.bus.cli import cmd_expire
    cmd_expire(args)


def cmd_bus_dead(args):
    from whorl.bus.cli import cmd_dead
    cmd_dead(args)


def cmd_bus_retry(args):
    from whorl.bus.cli import cmd_retry
    cmd_retry(args)
