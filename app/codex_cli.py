"""Exécution de `codex exec` avec sortie JSON imposée (même mécanique que x-med).

`codex [--search] exec --json --output-schema S -o OUT -` : le prompt arrive sur
stdin (pas de limite d'argv), le résultat structuré est écrit dans OUT, et
l'événement `turn.completed` du flux JSONL porte l'usage de tokens.

⚠️ PATH : codex est installé en npm global (`~/.npm-global/bin`). Un process
lancé par un agent/cron a un PATH minimal → régler CODEX_BIN en chemin absolu.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.config import settings


@dataclass
class CodexUsage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0


class CodexCliError(RuntimeError):
    """codex introuvable, non authentifié, trop lent, ou sortie illisible."""


def parse_usage(stdout: bytes | None) -> CodexUsage:
    usage = CodexUsage()
    for line in (stdout or b"").decode(errors="replace").splitlines():
        try:
            evt = json.loads(line)
        except ValueError:
            continue
        if isinstance(evt, dict) and evt.get("type") == "turn.completed":
            u = evt.get("usage") or {}
            usage = CodexUsage(
                input_tokens=int(u.get("input_tokens") or 0),
                cached_input_tokens=int(u.get("cached_input_tokens") or 0),
                output_tokens=int(u.get("output_tokens") or 0),
            )
    return usage


def build_command(schema_path: Path, out_path: Path, web_search: bool) -> list[str]:
    cmd = [settings.codex_bin]
    if web_search:
        cmd.append("--search")  # option globale : AVANT la sous-commande exec
    cmd += [
        "exec", "--json", "--skip-git-repo-check", "--ephemeral",
        "-s", "read-only", "--color", "never",
        "--output-schema", str(schema_path), "-o", str(out_path),
    ]
    if settings.codex_model:
        cmd += ["-m", settings.codex_model]
    if settings.codex_reasoning:
        cmd += ["-c", f'model_reasoning_effort="{settings.codex_reasoning}"']
    cmd.append("-")  # prompt lu sur stdin
    return cmd


def run_codex(prompt: str, schema: dict, web_search: bool = False) -> tuple[dict, CodexUsage]:
    with tempfile.TemporaryDirectory() as td:
        schema_path = Path(td) / "schema.json"
        out_path = Path(td) / "out.json"
        schema_path.write_text(json.dumps(schema))
        cmd = build_command(schema_path, out_path, web_search)
        try:
            # start_new_session : codex et ses enfants forment un groupe qu'un
            # timeout peut tuer d'un bloc.
            proc = subprocess.Popen(
                cmd, cwd=td, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, start_new_session=True,
            )
        except FileNotFoundError as e:
            raise CodexCliError(f"codex introuvable ({settings.codex_bin})") from e
        try:
            stdout, stderr = proc.communicate(prompt.encode(), timeout=settings.codex_timeout)
        except subprocess.TimeoutExpired as e:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.communicate()
            raise CodexCliError(f"codex timeout ({settings.codex_timeout}s)") from e
        if proc.returncode != 0:
            tail = (stderr or b"").decode(errors="replace")[-400:]
            raise CodexCliError(f"codex a échoué (code {proc.returncode}) : {tail}")
        try:
            data = json.loads(out_path.read_text())
        except Exception as e:
            raise CodexCliError(f"sortie codex illisible : {e}") from e
    return data, parse_usage(stdout)
