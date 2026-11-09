import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).parents[1] / "scripts" / "node.py"
spec = importlib.util.spec_from_file_location("node", MODULE)
node = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(node)


class NodeTests(unittest.TestCase):
    def test_node_certificate_script_creates_san_cert_and_never_overwrites(self):
        root = Path(__file__).parents[1]
        script = root / "scripts" / "create-node-cert.sh"
        with tempfile.TemporaryDirectory() as folder:
            env = {**os.environ, "NODE_SECRETS_DIR": folder}
            subprocess.run(
                ["bash", str(script), "node-test", "127.0.0.1", "DNS:localhost"],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            cert = Path(folder) / "node-test.crt"
            key = Path(folder) / "node-test.key"
            self.assertTrue(cert.is_file())
            if os.name != "nt":  # o Windows não representa permissões POSIX
                self.assertEqual(key.stat().st_mode & 0o777, 0o600)
            info = subprocess.run(
                ["openssl", "x509", "-in", str(cert), "-noout", "-ext", "subjectAltName"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("IP Address:127.0.0.1", info.stdout)
            self.assertIn("DNS:localhost", info.stdout)
            blocked = subprocess.run(
                ["bash", str(script), "node-test", "127.0.0.1"],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(blocked.returncode, 2)
            self.assertIn("nada foi sobrescrito", blocked.stderr)

    def test_runtime_argv_uses_slot_limit_and_separates_bind(self):
        config = {
            "node_id": "n1",
            "bind_host": "127.0.0.1",
            "bind_port": 8101,
            "tls_certfile": "node.crt",
            "tls_keyfile": "node.key",
            "threads": 2,
            "context_tokens": 4096,
            "slots": 1,
            "n_gpu_layers": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        args = node.argv(config, Path("model.gguf"))
        self.assertEqual(args[args.index("--host") + 1], "127.0.0.1")
        self.assertEqual(args[args.index("--port") + 1], "8101")
        self.assertEqual(args[args.index("-np") + 1], "1")
        self.assertEqual(args[args.index("--ssl-cert-file") + 1], "node.crt")
        self.assertEqual(json.loads(args[args.index("--chat-template-kwargs") + 1]), {"enable_thinking": False})

    def test_load_resolves_tls_paths_from_repository_and_checks_config_types(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            model = root / "tiny.gguf"
            model.write_bytes(b"tls fixture model")
            digest = node.sha256(model)
            secrets_dir = Path(__file__).parents[1] / "secrets"
            secrets_dir.mkdir(exist_ok=True)
            cert = secrets_dir / "fixture-node.crt"
            key = secrets_dir / "fixture-node.key"
            cert.write_text("cert", encoding="utf-8")
            key.write_text("key", encoding="utf-8")
            try:
                config = root / "node.toml"
                config.write_text(
                    f'''node_id = "fixture-tls"\nbind_host = "127.0.0.1"\nbind_port = 8101\npublic_url = "https://localhost:8101"\nmodel_file = "{model.as_posix()}"\nmodel_sha256 = "{digest}"\nthreads = 1\ncontext_tokens = 256\nslots = 1\ntls_certfile = "secrets/fixture-node.crt"\ntls_keyfile = "secrets/fixture-node.key"\n''',
                    encoding="utf-8",
                )
                loaded, _ = node.load(config)
                self.assertEqual(loaded["tls_certfile"], cert.resolve())
                self.assertEqual(loaded["tls_keyfile"], key.resolve())
                config.write_text(
                    f'''node_id = "fixture-tls"\nbind_host = "127.0.0.1"\nbind_port = true\nmodel_file = "{model.as_posix()}"\nmodel_sha256 = "{digest}"\nthreads = 1\ncontext_tokens = 256\nslots = 1\n''',
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "devem ser inteiros"):
                    node.load(config)
            finally:
                cert.unlink(missing_ok=True)
                key.unlink(missing_ok=True)

    def test_load_checks_manifest_hash_without_external_dependencies(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            model = root / "tiny.gguf"
            model.write_bytes(b"test fixture")
            digest = node.sha256(model)
            config = root / "node.toml"
            config.write_text(
                f'''node_id = "fixture"\nbind_host = "127.0.0.1"\nbind_port = 8101\nmodel_file = "{model.as_posix()}"\nmodel_sha256 = "{digest}"\nthreads = 1\ncontext_tokens = 256\nslots = 1\n''',
                encoding="utf-8",
            )
            loaded, path = node.load(config)
            self.assertEqual(loaded["node_id"], "fixture")
            self.assertEqual(path, model)

    def test_load_accepts_explicit_models_root_with_temporary_fixture(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            model_root = root / "weights"
            nested_root = model_root / "nested"
            nested_root.mkdir(parents=True)
            model = nested_root / "tiny.gguf"
            model.write_bytes(b"temporary model fixture")
            digest = node.sha256(model)
            config = root / "node.toml"
            config.write_text(
                f'''node_id = "fixture-root"\nbind_host = "127.0.0.1"\nbind_port = 8101\nmodel_file = "nested/tiny.gguf"\nmodel_sha256 = "{digest}"\nthreads = 1\ncontext_tokens = 256\nslots = 1\n''',
                encoding="utf-8",
            )

            loaded, resolved_model = node.load(config, models_root=model_root)

            self.assertEqual(loaded["node_id"], "fixture-root")
            self.assertEqual(resolved_model, model)

    def test_load_rejects_relative_model_path_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / "node.toml"
            config.write_text(
                '''node_id = "fixture-traversal"\nbind_host = "127.0.0.1"\nbind_port = 8101\nmodel_file = "../outside.gguf"\nmodel_sha256 = "'''
                + "0" * 64
                + '''"\nthreads = 1\ncontext_tokens = 256\nslots = 1\n''',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "não pode sair de models_root"):
                node.load(config, models_root=root / "weights")

    def test_load_accepts_absolute_model_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            model = root / "external.gguf"
            model.write_bytes(b"absolute model fixture")
            digest = node.sha256(model)
            config = root / "node.toml"
            config.write_text(
                f'''node_id = "fixture-absolute"\nbind_host = "127.0.0.1"\nbind_port = 8101\nmodel_file = "{model.as_posix()}"\nmodel_sha256 = "{digest}"\nthreads = 1\ncontext_tokens = 256\nslots = 1\n''',
                encoding="utf-8",
            )

            _, resolved_model = node.load(config)

            self.assertEqual(resolved_model, model)

    @staticmethod
    def _lan_config(root: Path, model: Path, *, api_key: Path | None, slots: int = 1) -> Path:
        lines = [
            'node_id = "lab"',
            'bind_host = "0.0.0.0"',
            "bind_port = 8101",
            'public_url = "http://10.0.0.5:8101"',
            f'model_file = "{model.as_posix()}"',
            f'model_sha256 = "{node.sha256(model)}"',
            "threads = 1",
            "context_tokens = 256",
            f"slots = {slots}",
        ]
        if api_key is not None:
            lines.append(f'api_key_file = "{api_key.as_posix()}"')
        config = root / "node.toml"
        config.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return config

    def test_api_key_file_is_passed_to_runtime_and_allows_lan_http(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            model = root / "tiny.gguf"
            model.write_bytes(b"fixture")
            key = root / "api-key"
            key.write_text("segredo", encoding="utf-8")
            loaded, path = node.load(self._lan_config(root, model, api_key=key, slots=2))
            args = node.argv(loaded, path, "/opt/llama/llama-server")
            self.assertEqual(args[0], "/opt/llama/llama-server")
            self.assertEqual(Path(args[args.index("--api-key-file") + 1]), key.resolve())
            self.assertEqual(args[args.index("-np") + 1], "2")

    def test_lan_http_without_api_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            model = root / "tiny.gguf"
            model.write_bytes(b"fixture")
            with self.assertRaisesRegex(ValueError, "api_key_file"):
                node.load(self._lan_config(root, model, api_key=None))

    def test_find_binary_prefers_explicit_path_then_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = Path(folder) / "llama-server"
            fake.write_text("", encoding="utf-8")
            self.assertEqual(node.find_binary(fake), str(fake))
            self.assertIsNone(node.find_binary(Path(folder) / "nao-existe"))
            old = os.environ.get("LLAMA_SERVER")
            os.environ["LLAMA_SERVER"] = str(fake)
            try:
                self.assertEqual(node.find_binary(None), str(fake))
            finally:
                if old is None:
                    os.environ.pop("LLAMA_SERVER")
                else:
                    os.environ["LLAMA_SERVER"] = old


if __name__ == "__main__":
    unittest.main()
