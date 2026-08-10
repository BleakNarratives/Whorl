"""
whorl.tools.model_spirit — Model invocation driver.

Supports four routing modes:
  1. STATE (preferred) — reads server config from SharedState, so
     local devices never hold weights. The state layer (JaneBox/
     Supabase) is the single source of truth for where models live.
  2. GROQ — free-tier cloud inference via api.groq.com (email signup only)
  3. REMOTE — HTTP client hitting a llama-server instance (direct)
  4. LOCAL (fallback) — subprocess invocation of llama-cli

The state-aware mode is the primary path for Track 2 (Oracle Cloud A1)
where model weights live on the A1 and local devices route through state.
Groq provides free Llama 3.3 70B inference — no credit card required.
"""

import json
import os
import subprocess
import urllib.request
import urllib.error
import time
from typing import Any, Tuple, Optional

from ..core.state import SharedState


# ─── Configuration ───────────────────────────────────────────────────

# Env vars (fallback if not in state):
#   WHORL_MODEL_HOST  — llama-server hostname/IP
#   WHORL_MODEL_PORT  — llama-server port (default: 8080)
#   WHORL_MODEL_NAME  — model name for API calls (default: tinyllama)
#   WHORL_MODEL_MODE  — "state", "remote", or "local" (default: auto)

DEFAULT_HOST = os.environ.get("WHORL_MODEL_HOST", "localhost")
DEFAULT_PORT = int(os.environ.get("WHORL_MODEL_PORT", "8080"))
DEFAULT_MODEL_NAME = os.environ.get("WHORL_MODEL_NAME", "tinyllama")
STATE_KEY_PREFIX = "model:spirit"

# Groq free-tier config (lazy-loaded to avoid stale env caching)
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"

def _groq_key() -> str:
    """Read GROQ_API_KEY lazily from env (avoids stale import-time cache)."""
    return os.environ.get("GROQ_API_KEY", "")


# ─── State-aware Routing ────────────────────────────────────────────

def _get_state() -> Optional[SharedState]:
    """Get the shared state store (returns None if unavailable)."""
    try:
        return SharedState()
    except Exception:
        return None


def register_server(
    host: str,
    port: int = DEFAULT_PORT,
    model_name: str = DEFAULT_MODEL_NAME,
    agent_id: str = "spirit-registry",
    status: str = "active",
) -> None:
    """
    Register a model server in shared state.

    Call this when a llama-server comes online. All devices reading
    from state will discover it automatically — no weights on local.

    State keys written:
      model:spirit:server     — {host, port, model, status, registered_at}
      model:spirit:heartbeat  — timestamp of last health check
    """
    state = _get_state()
    if state is None:
        return

    server_info = {
        "host": host,
        "port": port,
        "model": model_name,
        "status": status,
        "registered_at": time.time(),
    }
    state.write(f"{STATE_KEY_PREFIX}:server", server_info, agent_id)
    state.write(f"{STATE_KEY_PREFIX}:heartbeat", time.time(), agent_id)


def unregister_server(agent_id: str = "spirit-registry") -> None:
    """Remove the model server from shared state."""
    state = _get_state()
    if state is None:
        return
    state.delete(f"{STATE_KEY_PREFIX}:server", agent_id)
    state.delete(f"{STATE_KEY_PREFIX}:heartbeat", agent_id)


def heartbeat(agent_id: str = "spirit-heartbeat") -> None:
    """Update the heartbeat timestamp. Call periodically to signal liveness."""
    state = _get_state()
    if state is None:
        return
    state.write(f"{STATE_KEY_PREFIX}:heartbeat", time.time(), agent_id)


def get_server_from_state() -> Optional[dict]:
    """Read the current model server config from shared state.

    Returns None if no server is registered or state is unavailable.
    Returns dict with keys: host, port, model, status.
    """
    state = _get_state()
    if state is None:
        return None

    server = state.read(f"{STATE_KEY_PREFIX}:server")
    if server is None:
        return None

    # Validate it's a dict with required keys
    if not isinstance(server, dict):
        return None
    if "host" not in server or "port" not in server:
        return None

    # Check if heartbeat is stale (>5 min old)
    heartbeat_ts = state.read(f"{STATE_KEY_PREFIX}:heartbeat")
    if heartbeat_ts and isinstance(heartbeat_ts, (int, float)):
        age = time.time() - heartbeat_ts
        if age > 300:  # 5 minutes
            server["status"] = "stale"
            server["heartbeat_age"] = round(age)

    return server


def _resolve_mode() -> str:
    """Auto-detect: state → groq → remote → local."""
    mode = os.environ.get("WHORL_MODEL_MODE", "auto")
    if mode in ("state", "groq", "remote", "local"):
        return mode

    # Auto-detect order: state → groq → remote → local
    server = get_server_from_state()
    if server and server.get("status") == "active":
        return "state"
    if _groq_key():
        return "groq"
    if _remote_health():
        return "remote"
    return "local"


# ─── Remote Mode (HTTP Client) ──────────────────────────────────────

def _remote_health(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
    """Check if llama-server is reachable."""
    try:
        url = f"http://{host}:{port}/health"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            return data.get("status") == "ok"
    except Exception:
        return False


def _remote_invoke(
    prompt: str,
    model_name: str = DEFAULT_MODEL_NAME,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    max_tokens: int = 128,
    temperature: float = 0.7,
    messages: Optional[list] = None,
) -> Tuple[str, dict]:
    """
    Invoke a model via llama-server HTTP API (OpenAI-compatible).
    Uses POST /v1/chat/completions endpoint.

    When `messages` is given (a conversation already compressed by the
    TokenStretcher), it is sent as-is instead of the single prompt.
    """
    url = f"http://{host}:{port}/v1/chat/completions"
    if messages is not None:
        payload_messages = _sanitize_messages(messages)
    else:
        payload_messages = [{"role": "user", "content": prompt}]
    payload = {
        "model": model_name,
        "messages": payload_messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())

        # Extract text from OpenAI-compatible response
        text = result["choices"][0]["message"]["content"]

        # Spirit metadata
        spirit_meta = {
            "spirit_source": model_name,
            "spirit_version": "0.1-remote",
            "spirit_capability": "reasoning",
            "spirit_backend": "llama-server",
            "spirit_host": f"{host}:{port}",
        }

        return text.strip(), spirit_meta

    except urllib.error.URLError as e:
        return f"Remote Error: {e}", {"error": "remote_unreachable", "host": host}
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        return f"Parse Error: {e}", {"error": "response_malformed"}
    except Exception as e:
        return f"Model Error: {str(e)}", {"error": "invocation_failed"}


# ─── Groq Mode (Free Cloud Inference) ─────────────────────────────

def _groq_health() -> bool:
    """Check if Groq API is reachable."""
    key = _groq_key()
    if not key:
        return False
    try:
        url = f"{GROQ_BASE_URL}/models"
        req = urllib.request.Request(url, method="GET")
        req.add_header("Authorization", f"Bearer {key}")
        req.add_header("User-Agent", "Whorl/0.1.0 model-spirit")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _groq_invoke(
    prompt: str,
    model_name: str = GROQ_DEFAULT_MODEL,
    max_tokens: int = 128,
    temperature: float = 0.7,
    messages: Optional[list] = None,
) -> Tuple[str, dict]:
    """
    Invoke a model via Groq's OpenAI-compatible API.
    Free tier: 30 RPM, 14k RPD, Llama 3.3 70B.

    When `messages` is given (a conversation already compressed by the
    TokenStretcher), it is sent as-is instead of the single prompt.
    """
    url = f"{GROQ_BASE_URL}/chat/completions"
    if messages is not None:
        payload_messages = _sanitize_messages(messages)
    else:
        payload_messages = [{"role": "user", "content": prompt}]
    payload = {
        "model": model_name,
        "messages": payload_messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }

    key = _groq_key()
    if not key:
        return "Model Error: GROQ_API_KEY not set", {"error": "no_groq_key"}

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                "User-Agent": "Whorl/0.1.0 model-spirit",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())

        text = result["choices"][0]["message"]["content"]

        spirit_meta = {
            "spirit_source": model_name,
            "spirit_version": "0.1-groq",
            "spirit_capability": "reasoning",
            "spirit_backend": "groq",
            "spirit_host": "api.groq.com",
        }

        return text.strip(), spirit_meta

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        return f"Groq Error {e.code}: {body}", {"error": "groq_http_error", "code": e.code}
    except urllib.error.URLError as e:
        return f"Groq Error: {e}", {"error": "groq_unreachable"}
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        return f"Parse Error: {e}", {"error": "response_malformed"}
    except Exception as e:
        return f"Model Error: {str(e)}", {"error": "invocation_failed"}


# ─── Local Mode (Subprocess) ────────────────────────────────────────

def _local_invoke(
    prompt: str,
    model_path: str,
    model_name: str,
    max_tokens: int = 128,
) -> Tuple[str, dict]:
    """
    Invoke a local GGUF model via llama-cli subprocess.
    Fallback when no remote server is available.
    """
    cmd = [
        "llama-cli", "-m", model_path, "-p", prompt,
        "-n", str(max_tokens), "--silent-prompt"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        spirit_meta = {
            "spirit_source": model_name,
            "spirit_version": "0.1-local",
            "spirit_capability": "reasoning",
            "spirit_backend": "llama-cli",
        }

        return result.stdout.strip(), spirit_meta
    except FileNotFoundError:
        return (
            "Model Error: llama-cli not found. Install llama.cpp or set WHORL_MODEL_HOST.",
            {"error": "llama_cli_not_found"},
        )
    except Exception as e:
        return f"Model Error: {str(e)}", {"error": "invocation_failed"}


# ─── Conversation Compression (TokenStretcher) ─────────────────────


def _sanitize_messages(messages: list) -> list:
    """
    Map the TokenStretcher's internal roles onto OpenAI-compatible ones
    so a compressed conversation is a valid chat payload.

      summary → system   (a folded summary is standing context)
      any unknown role → user
    """
    out = []
    for m in messages:
        role = m.get("role", "user") if isinstance(m, dict) else "user"
        content = m.get("content", "") if isinstance(m, dict) else str(m)
        if role not in ("system", "user", "assistant"):
            role = "system" if role == "summary" else "user"
        out.append({"role": role, "content": str(content)})
    return out


def _flatten_messages(messages: list) -> str:
    """Serialize a compressed conversation for backends that only take a
    single prompt string (llama-cli subprocess)."""
    lines = []
    for m in messages:
        role = m.get("role", "user") if isinstance(m, dict) else "user"
        content = m.get("content", "") if isinstance(m, dict) else str(m)
        label = {"system": "System", "summary": "Summary", "assistant": "Assistant"}.get(role, "User")
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def _compress_history(
    prompt: str,
    messages: list,
    max_context: Optional[int],
    stretch_name: Optional[str],
) -> Tuple[list, dict]:
    """
    Run a conversation through the TokenStretcher's sliding window.

    The `messages` list is the prior conversation; `prompt` is the new
    user message, appended last so it is always in the active context.
    Every message that does not fit under the budget is folded into a
    summary (model-backed when reachable, extractive offline) and moved
    to the archive — no message is silently dropped.

    When `stretch_name` is given the window persists to SharedState, so
    history accumulates and compresses progressively across calls.

    Returns (compressed_context, telemetry_dict).
    """
    from ..memory.stretcher import TokenStretcher
    from ..memory.tokens import count_tokens

    state = _get_state() if stretch_name else None
    stretch = TokenStretcher(
        max_context=max_context or 8000,
        state=state,
        name=stretch_name or "spirit",
    )
    if stretch_name and state is not None:
        stretch.load()

    before = 0
    for m in messages:
        content = m.get("content", "") if isinstance(m, dict) else str(m)
        before += count_tokens(str(content))
        role = m.get("role", "user") if isinstance(m, dict) else "user"
        stretch.add_message(str(content), role=role)
    before += count_tokens(prompt)
    stretch.add_message(prompt, role="user")

    if stretch_name and state is not None:
        stretch.save()

    telemetry = {
        "compressed": bool(stretch.summaries or stretch.archived),
        "tokens_before": before,
        "tokens_after": stretch.active_tokens,
        "saved_tokens": max(0, before - stretch.active_tokens),
        "folds": len(stretch.summaries),
        "archived": len(stretch.archived),
        "budget": stretch.max_context,
        "window": stretch_name or "spirit",
    }
    return stretch.context(), telemetry


# ─── Public API ──────────────────────────────────────────────────────

def invoke_model(
    prompt: str = "",
    model_path: str = "",
    model_name: str = DEFAULT_MODEL_NAME,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    max_tokens: int = 128,
    temperature: float = 0.7,
    messages: Optional[list] = None,
    max_context: Optional[int] = None,
    stretch_name: Optional[str] = None,
) -> Tuple[str, dict]:
    """
    Invoke a model. Routes through state, remote, or local.

    Routing priority:
      1. STATE — reads server config from SharedState (no local weights)
      2. REMOTE — direct HTTP to llama-server
      3. LOCAL — subprocess llama-cli (fallback)

    Local devices never hold weights — state tells us where the model lives.

    Conversation compression:
      Pass `messages=` (a list of {"role", "content"} dicts) to have the
      conversation history automatically run through the TokenStretcher
      before the call. History that exceeds the budget is folded into
      summaries (never dropped) and the compressed context is sent as a
      proper chat payload. `prompt` is appended as the latest user
      message and always stays in the window. `max_context` sets the
      token budget (default 8000); `stretch_name` persists the sliding
      window to SharedState so it accumulates across calls. Compression
      telemetry is reported under spirit_meta["stretch"].

      When `messages` is None the behaviour is unchanged: the prompt is
      sent as a single user message. This is what keeps the Summarizer's
      own folding recursion-free — it calls invoke_model without
      messages.

    Args:
        prompt: The input text (or the latest user message when messages=)
        model_path: Path to .gguf file (only needed for local mode)
        model_name: Model identifier for API calls
        host: llama-server hostname (env: WHORL_MODEL_HOST)
        port: llama-server port (env: WHORL_MODEL_PORT)
        max_tokens: Max generation tokens
        temperature: Sampling temperature (0.0-1.0)
        messages: Prior conversation [{role, content}, ...] to compress
        max_context: Token budget for the compressed window
        stretch_name: Optional persistent window id in SharedState

    Returns:
        (output_text, spirit_metadata) tuple
    """
    prompt = "" if prompt is None else str(prompt)
    mode = _resolve_mode()

    payload = None
    stretch_meta = {}
    if messages is not None:
        payload, stretch_meta = _compress_history(
            prompt, messages, max_context, stretch_name,
        )

    if mode == "groq":
        text, meta = _groq_invoke(
            prompt, model_name=model_name,
            max_tokens=max_tokens, temperature=temperature,
            messages=payload,
        )
    elif mode == "state":
        # Route through state — local device never sees weights
        server = get_server_from_state()
        if server:
            text, meta = _remote_invoke(
                prompt, model_name=model_name,
                host=server["host"], port=server["port"],
                max_tokens=max_tokens, temperature=temperature,
                messages=payload,
            )
        else:
            # State said state-mode but no server found — fall through
            text, meta = _local_invoke(
                _flatten_messages(payload) if payload is not None else prompt,
                model_path=model_path,
                model_name=model_name, max_tokens=max_tokens,
            )
    elif mode == "remote":
        text, meta = _remote_invoke(
            prompt, model_name=model_name,
            host=host, port=port,
            max_tokens=max_tokens, temperature=temperature,
            messages=payload,
        )
    else:
        text, meta = _local_invoke(
            _flatten_messages(payload) if payload is not None else prompt,
            model_path=model_path,
            model_name=model_name, max_tokens=max_tokens,
        )

    if stretch_meta:
        meta["stretch"] = stretch_meta
    return text, meta


def server_status(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> dict:
    """Check the remote server status."""
    try:
        url = f"http://{host}:{port}/health"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            health = json.loads(resp.read())

        # Also fetch model list
        url2 = f"http://{host}:{port}/v1/models"
        req2 = urllib.request.Request(url2, method="GET")
        with urllib.request.urlopen(req2, timeout=5) as resp2:
            models = json.loads(resp2.read())

        return {
            "status": "healthy",
            "health": health,
            "models": models.get("data", []),
            "host": host,
            "port": port,
        }
    except Exception as e:
        return {
            "status": "unreachable",
            "error": str(e),
            "host": host,
            "port": port,
        }


def model_info() -> dict:
    """Get full model routing info: state config + server health + mode."""
    mode = _resolve_mode()
    server = get_server_from_state()
    status = None

    if server and server.get("host"):
        status = server_status(server["host"], server["port"])
    elif mode == "remote":
        status = server_status()

    return {
        "mode": mode,
        "state_server": server,
        "env_host": DEFAULT_HOST,
        "env_port": DEFAULT_PORT,
        "server_health": status,
    }
