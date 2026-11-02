import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).parents[1] / "scripts" / "node.py"
spec = importlib.util.spec_from_file_location("node", MODULE)
node = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(node)


class NodeTests(unittest.TestCase):
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

    def test_load_checks_manifest_hash_without_external_dependencies(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            model = root / "tiny.gguf"
            model.write_bytes(b"test fixture")
            digest = node.sha256(model)
            config = root / "node.toml"
            config.write_text(
                f'''node_id = "fixture"\nbind_host = "127.0.0.1"\nbind_port = 8101\nmodel_file = "{model}"\nmodel_sha256 = "{digest}"\nthreads = 1\ncontext_tokens = 256\nslots = 1\n''',
                encoding="utf-8",
            )
            loaded, path = node.load(config)
            self.assertEqual(loaded["node_id"], "fixture")
            self.assertEqual(path, model)

    def test_load_accepts_explicit_local_models_root(self):
        root = Path(__file__).parents[1]
        loaded, model = node.load(root / "configs/qwen3-small.toml", models_root=root.parent / "Tudo Junto/models")
        self.assertEqual(loaded["node_id"], "llm-small-a")
        self.assertTrue(model.is_file())


if __name__ == "__main__":
    unittest.main()
