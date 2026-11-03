#!/usr/bin/env python3
"""Valida configuração/hash e inicia uma única réplica llama-server."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import shutil
import os
import re
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
    path = path.expanduser().resolve()
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    required = ("node_id", "bind_host", "bind_port", "model_file", "model_sha256", "threads", "context_tokens", "slots")
    optional = {
        "models_root", "public_url", "tls_certfile", "tls_keyfile", "n_gpu_layers", "chat_template_kwargs"
    }
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"configuração sem campos: {', '.join(missing)}")
    unknown = set(config) - set(required) - optional
    if unknown:
        raise ValueError(f"campos desconhecidos: {', '.join(sorted(unknown))}")
    integer_fields = ("bind_port", "threads", "context_tokens", "slots")
    if any(type(config[key]) is not int for key in integer_fields):
        raise ValueError("porta/threads/context/slots devem ser inteiros")
    if "n_gpu_layers" in config and type(config["n_gpu_layers"]) is not int:
        raise ValueError("n_gpu_layers deve ser inteiro")
    if "n_gpu_layers" in config and config["n_gpu_layers"] < 0:
        raise ValueError("n_gpu_layers não pode ser negativo")
    if "chat_template_kwargs" in config and not isinstance(config["chat_template_kwargs"], dict):
        raise ValueError("chat_template_kwargs deve ser tabela")
    if not 1 <= config["bind_port"] <= 65535 or min(config["threads"], config["context_tokens"], config["slots"]) < 1:
        raise ValueError("porta/threads/context/slots fora dos limites")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", config["node_id"]):
        raise ValueError("node_id inválido")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", config["model_sha256"]):
        raise ValueError("model_sha256 deve conter 64 caracteres hexadecimais")
    if not isinstance(config["bind_host"], str) or not config["bind_host"]:
        raise ValueError("bind_host inválido")
    try:
        import socket

        socket.getaddrinfo(config["bind_host"], config["bind_port"], type=socket.SOCK_STREAM)
    except (OSError, TypeError) as error:
        raise ValueError("bind_host/bind_port inválidos") from error
    public_url = config.get("public_url", "")
    if public_url:
        from urllib.parse import urlsplit

        parsed_url = urlsplit(public_url)
        try:
            url_port = parsed_url.port
        except ValueError as error:
            raise ValueError("public_url tem porta inválida") from error
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.hostname
            or parsed_url.username is not None
            or parsed_url.password is not None
            or parsed_url.path not in {"", "/"}
            or parsed_url.query
            or parsed_url.fragment
            or url_port != config["bind_port"]
        ):
            raise ValueError("public_url deve ser http(s) com host e porta iguais a bind_port")
        loopback = parsed_url.hostname == "localhost"
        if not loopback:
            try:
                loopback = ipaddress.ip_address(parsed_url.hostname).is_loopback
            except ValueError:
                loopback = False
        if parsed_url.scheme == "http" and not loopback:
            raise ValueError("HTTP público só é permitido para loopback; use HTTPS remoto")
    if public_url.startswith("https://") and not config.get("tls_certfile"):
        raise ValueError("nó HTTPS público exige tls_certfile e tls_keyfile no host LLM")
    if bool(config.get("tls_certfile")) != bool(config.get("tls_keyfile")):
        raise ValueError("tls_certfile e tls_keyfile devem ser informados juntos")
    repo_root = Path(__file__).resolve().parents[1]
    for key in ("tls_certfile", "tls_keyfile"):
        if config.get(key):
            tls_path = Path(config[key]).expanduser()
            config[key] = (tls_path if tls_path.is_absolute() else repo_root / tls_path).resolve()
            if not config[key].is_file():
                raise ValueError(f"arquivo TLS ausente: {config[key]}")
    model_path = Path(config["model_file"]).expanduser()
    if model_path.is_absolute():
        model = model_path.resolve()
    else:
        configured_root = models_root or Path(config.get("models_root", "models"))
        if configured_root.is_absolute():
            model_root = configured_root.resolve()
        elif models_root is not None:
            model_root = configured_root.resolve()
        elif "models_root" in config:
            model_root = (path.resolve().parent / configured_root).resolve()
        else:
            model_root = (Path(__file__).resolve().parents[1] / configured_root).resolve()
        model = (model_root / model_path).resolve()
        if not model.is_relative_to(model_root):
            raise ValueError("model_file relativo não pode sair de models_root")
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
    parser.add_argument("--models-root", type=Path, help="sobrescreve a raiz dos pesos GGUF")
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
