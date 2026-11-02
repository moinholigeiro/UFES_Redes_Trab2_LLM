#!/usr/bin/env python3
"""Valida configuração/hash e inicia uma única réplica llama-server."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import os
import sys
import tomllib
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path, *, models_root: Path | None = None) -> tuple[dict, Path]:
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    required = ("node_id", "bind_host", "bind_port", "model_file", "model_sha256", "threads", "context_tokens", "slots")
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"configuração sem campos: {', '.join(missing)}")
    if not 1 <= config["bind_port"] <= 65535 or min(config["threads"], config["context_tokens"], config["slots"]) < 1:
        raise ValueError("porta/threads/context/slots fora dos limites")
    try:
        import socket

        socket.getaddrinfo(config["bind_host"], config["bind_port"], type=socket.SOCK_STREAM)
    except (OSError, TypeError) as error:
        raise ValueError("bind_host/bind_port inválidos") from error
    if "https://" in config.get("public_url", "") and not config.get("tls_certfile"):
        raise ValueError("nó HTTPS público exige tls_certfile e tls_keyfile no host LLM")
    if bool(config.get("tls_certfile")) != bool(config.get("tls_keyfile")):
        raise ValueError("tls_certfile e tls_keyfile devem ser informados juntos")
    model_path = Path(config["model_file"])
    configured_root = models_root or Path(config.get("models_root", "models"))
    model_root = (path.parent.parent / configured_root).resolve() if not configured_root.is_absolute() else configured_root
    model = (model_root / model_path.name).resolve() if not model_path.is_absolute() else model_path
    if not model.is_file():
        raise ValueError(f"modelo ausente: {model}")
    if sha256(model) != config["model_sha256"]:
        raise ValueError(f"SHA-256 do modelo não confere: {model}")
    return config, model


def argv(config: dict, model: Path) -> list[str]:
    command = [
        "llama-server", "-m", str(model), "--host", config["bind_host"], "--port", str(config["bind_port"]),
        "-t", str(config["threads"]), "-c", str(config["context_tokens"]), "-np", str(config["slots"]), "--jinja",
        "--n-gpu-layers", str(config.get("n_gpu_layers", 0)),
    ]
    kwargs = config.get("chat_template_kwargs", {})
    if kwargs:
        command += ["--chat-template-kwargs", json.dumps(kwargs, separators=(",", ":"))]
    if config.get("tls_certfile"):
        command += ["--ssl-cert-file", config["tls_certfile"], "--ssl-key-file", config["tls_keyfile"]]
    return command


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="validar configuração e hash, sem iniciar runtime")
    parser.add_argument("--models-root", type=Path, help="sobrescreve o diretório de pesos para uma migração local")
    args = parser.parse_args()
    try:
        config, model = load(args.config, models_root=args.models_root)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"configuração inválida: {error}", file=sys.stderr)
        return 2
    command = argv(config, model)
    if args.check:
        print(f"{config['node_id']}: config/hash OK; runtime: {shutil.which('llama-server') or 'não encontrado'}")
        return 0
    if shutil.which("llama-server") is None:
        print("llama-server não encontrado; entre no ambiente devenv", file=sys.stderr)
        return 2
    print(f"iniciando {config['node_id']} em {config['bind_host']}:{config['bind_port']}", flush=True)
    os.execvp(command[0], command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
