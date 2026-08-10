"""
whorl.core.vault
────────────────
Unified API key vault. Local → Remote → Nostr fallback.
"""

from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional

import requests

from .config import WHORL_DIR, cfg


def load_api_keys() -> Dict[str, str]:
    """Load keys from env → local → remote → nostr. First hit wins."""
    
    # 1. Environment variables (highest priority, no files needed)
    env_keys = _from_env()
    if env_keys:
        return env_keys
    
    # 2. Local secrets.toml (fast, offline capable)
    local_keys = _from_local()
    
    # 3. Remote vault (GitHub gist or private repo raw URL)
    if not local_keys or _are_placeholders(local_keys):
        remote_keys = _from_remote()
        if remote_keys:
            local_keys.update(remote_keys)
            _save_local(local_keys)  # Cache remote for offline
    
    # 4. Nostr relay (decentralized fallback)
    if not local_keys:
        nostr_keys = _from_nostr()
        if nostr_keys:
            local_keys.update(nostr_keys)
            _save_local(local_keys)
    
    if not local_keys:
        raise RuntimeError(
            "No API keys found. Tried: env, ~/.whorl/secrets.toml, "
            "remote vault, Nostr relay. Run: whorl vault init"
        )
    
    return local_keys


def _from_env() -> Dict[str, str]:
    keys = {}
    for name in ["OPENAI", "GROQ", "MISTRAL", "GEMINI", "ANTHROPIC", "KIMI"]:
        val = os.getenv(f"{name}_API_KEY")
        if val and not val.startswith("sk-...") and val != "...":
            keys[name.lower()] = val
    return keys


def _from_local() -> Dict[str, str]:
    path = WHORL_DIR / "secrets.toml"
    if not path.exists():
        return {}
    try:
        import toml
        return toml.loads(path.read_text()).get("api_keys", {})
    except Exception:
        return {}


def _save_local(keys: Dict[str, str]) -> None:
    WHORL_DIR.mkdir(parents=True, exist_ok=True)
    path = WHORL_DIR / "secrets.toml"
    try:
        import toml
        path.write_text(toml.dumps({"api_keys": keys}))
        os.chmod(path, 0o600)
    except Exception as e:
        print(f"[vault] Failed to cache keys locally: {e}")


def _are_placeholders(keys: Dict[str, str]) -> bool:
    if not keys:
        return True
    bad = {"sk-...", "gsk-...", "...", "", "YOUR_KEY_HERE", "placeholder"}
    return all(v in bad for v in keys.values())


def _from_remote() -> Optional[Dict[str, str]]:
    url = cfg().raw.get("vault", {}).get("url")
    if not url:
        return None
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        import toml
        return toml.loads(r.text).get("api_keys", {})
    except Exception as e:
        print(f"[vault] Remote fetch failed: {e}")
        return None


def _from_nostr() -> Optional[Dict[str, str]]:
    # Stub: implement when pynostr available
    return None


def init_interactive() -> None:
    """First-time setup. Collect keys, save locally, offer remote sync."""
    print("\n[whorl vault init]")
    print("Enter API keys (press Enter to skip):\n")
    
    keys = {}
    for name in ["openai", "groq", "mistral", "gemini", "anthropic", "kimi"]:
        val = input(f"  {name.upper()}: ").strip()
        if val and val not in ("...", "sk-..."):
            keys[name] = val
    
    if keys:
        _save_local(keys)
        print(f"\n[✓] Saved {len(keys)} keys to {WHORL_DIR / 'secrets.toml'}")
        
        gist = input("\nGist/raw URL for remote sync (optional): ").strip()
        if gist:
            cfg().raw["vault"] = {"url": gist}
            # Update config.toml
            import toml
            config_path = WHORL_DIR / "config.toml"
            current = toml.loads(config_path.read_text()) if config_path.exists() else {}
            current["vault"] = {"url": gist}
            config_path.write_text(toml.dumps(current))
            print(f"[✓] Remote vault configured")
    else:
        print("[!] No keys entered. Tailor will use Ollama local only.")


def sync_push(gist_url: str) -> None:
    """Push local keys to GitHub gist. Requires gist URL with token."""
    keys = _from_local()
    if not keys:
        print("[vault] No local keys to push.")
        return
    
    try:
        r = requests.patch(
            gist_url,
            headers={"Authorization": f"token {os.getenv('GITHUB_TOKEN', '')}"},
            json={"files": {"secrets.toml": {"content": _keys_to_toml(keys)}}},
            timeout=15
        )
        r.raise_for_status()
        print("[✓] Keys pushed to remote vault.")
    except Exception as e:
        print(f"[vault] Push failed: {e}")
        print("        Create gist manually, paste raw URL in config.toml")


def _keys_to_toml(keys: Dict[str, str]) -> str:
    import toml
    return toml.dumps({"api_keys": keys})


def status() -> None:
    """Show which key sources are available."""
    print("\n[whorl vault status]")
    print(f"  Env vars:     {'✓' if _from_env() else '✗'}")
    print(f"  Local file:   {'✓' if _from_local() else '✗'} ({WHORL_DIR / 'secrets.toml'})")
    url = cfg().raw.get("vault", {}).get("url")
    print(f"  Remote vault: {'✓' if url else '✗'} ({url or 'not configured'})")
    
    keys = load_api_keys()
    print(f"\n  Active keys:  {len(keys)} providers")
    for k in keys:
        masked = keys[k][:8] + "..." + keys[k][-4:] if len(keys[k]) > 12 else "***"
        print(f"    • {k}: {masked}")
