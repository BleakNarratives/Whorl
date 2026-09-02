# [DNA_TAG]
# ORIGIN: Moto4_A9
# PILLAR: cli
# DEPS: none
# ROLE: Whorl CLI — shared runtime helpers (banner, DB boot)
# LAST_SYNC: 2026-09-02T04:00:00Z
# [/DNA_TAG]

"""Shared runtime helpers for the whorl CLI package."""


def banner():
    print("""
 ██╗    ██╗██╗  ██╗ ██████╗ ██████╗ ██╗
 ██║    ██║██║  ██║██╔═══██╗██╔══██╗██║
 ██║ █╗ ██║███████║██║   ██║██████╔╝██║
 ██║███╗██║██╔══██║██║   ██║██╔══██╗██║
 ╚███╔███╔╝██║  ██║╚██████╔╝██║  ██║███████╗
  ╚══╝╚══╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝
  Field Intelligence & Agent Deployment Workbench
""")


def boot():
    """Initialize DB on first run."""
    from whorl.core import db as _db
    _db.migrate()
