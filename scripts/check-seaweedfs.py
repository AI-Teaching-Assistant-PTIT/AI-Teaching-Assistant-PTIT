"""Exercise backend S3 operations, persistence and migration using isolated Docker storage."""

import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import types
import uuid
from urllib.error import HTTPError
from urllib.request import urlopen

from minio import Minio
from minio.error import S3Error

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
ACCESS_KEY = "s3-compatibility-test"
SECRET_KEY = "s3-compatibility-test-password"


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True, timeout=60).strip()


def wait_ready(endpoint):
    for _ in range(60):
        try:
            with urlopen(f"http://{endpoint}/healthz", timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, HTTPError):
            time.sleep(0.5)
    raise RuntimeError("SeaweedFS did not become ready")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    compose = json.loads(docker(
        "compose", "--env-file", "/dev/null", "-f", str(ROOT / "docker-compose.yaml"),
        "config", "--no-interpolate", "--no-env-resolution", "--format", "json",
    ))["services"]["minio"]
    servers, volumes, clients, endpoints = [], [], [], []
    try:
        for _ in range(2):
            name = "nits-seaweed-check-" + uuid.uuid4().hex[:10]
            volume = name + "-data"
            docker("volume", "create", "--label", "purpose=nits-seaweed-check", volume)
            volumes.append(volume)
            docker(
                "run", "--detach", "--name", name, "--label", "purpose=nits-seaweed-check",
                "--memory", "1g", "--cpus", "1",
                "--publish", "127.0.0.1::9000", "--publish", "127.0.0.1::9001",
                "--mount", f"type=volume,src={volume},dst=/data",
                "--env", "AWS_ACCESS_KEY_ID=" + ACCESS_KEY,
                "--env", "AWS_SECRET_ACCESS_KEY=" + SECRET_KEY,
                "--env", "WEED_ADMIN_USER=" + ACCESS_KEY,
                "--env", "WEED_ADMIN_PASSWORD=" + SECRET_KEY,
                compose["image"], *compose["command"],
            )
            servers.append(name)
            endpoint = docker("port", name, "9000/tcp")
            endpoints.append(endpoint)
            wait_ready(endpoint)
            docker("exec", name, *compose["healthcheck"]["test"][1:])
            clients.append(Minio(endpoint, access_key=ACCESS_KEY, secret_key=SECRET_KEY, secure=False))

        source, destination = clients
        for bucket in ("course-knowledge", "gitea-backup", "postgres-backup", "postgres-backups"):
            assert source.bucket_exists(bucket), bucket
        source.make_bucket("new-bucket-check")
        bad_client = Minio(endpoints[0], access_key="wrong-key", secret_key="wrong-password", secure=False)
        try:
            bad_client.bucket_exists("course-knowledge")
        except S3Error:
            pass
        else:
            raise AssertionError("Invalid S3 credentials were accepted")

        # Use the real backend storage functions without loading database/AI settings.
        config = types.ModuleType("app.core.config")
        config.settings = types.SimpleNamespace(
            MINIO_ENDPOINT=endpoints[0], MINIO_ACCESS_KEY=ACCESS_KEY,
            MINIO_SECRET_KEY=SECRET_KEY, MINIO_SECURE=False, MINIO_BUCKET="course-knowledge",
        )
        sys.modules["app.core.config"] = config
        storage = load_module("backend_storage", ROOT / "web/backend/app/knowledge/storage.py")
        data = os.urandom(11 * 1024 * 1024)
        uri = storage.put_bytes("imports/week 1/đề bài + tài liệu.pdf", data, "application/pdf")
        assert storage.object_exists(uri)
        assert storage.get_bytes(uri) == data
        assert not storage.object_exists("s3://course-knowledge/does-not-exist")
        empty_uri = storage.put_bytes("empty-file", b"", "application/octet-stream")
        assert storage.get_bytes(empty_uri) == b""
        docker("restart", servers[0])
        # Docker can assign a new ephemeral host port after restart.
        endpoints[0] = docker("port", servers[0], "9000/tcp")
        config.settings.MINIO_ENDPOINT = endpoints[0]
        source = Minio(endpoints[0], access_key=ACCESS_KEY, secret_key=SECRET_KEY, secure=False)
        wait_ready(endpoints[0])
        assert storage.get_bytes(uri) == data
        print("PASS: bootstrap, authentication, backend upload/download/HEAD, multipart, empty objects, restart persistence", flush=True)

        migration = load_module("s3_migration", ROOT / "scripts/migrate-s3.py")
        source.make_bucket("migration-check")
        source.put_object("migration-check", "file.pdf", io.BytesIO(b"original"), 8,
                          content_type="application/pdf", metadata={"course": "CS101"})
        migration_env = dict(os.environ)
        for prefix in ("SOURCE", "DESTINATION"):
            migration_env[prefix + "_S3_ACCESS_KEY"] = ACCESS_KEY
            migration_env[prefix + "_S3_SECRET_KEY"] = SECRET_KEY
        subprocess.run([
            sys.executable, str(ROOT / "scripts/migrate-s3.py"),
            "--source-endpoint", "http://" + endpoints[0],
            "--destination-endpoint", "http://" + endpoints[1],
            "--bucket", "migration-check",
        ], env=migration_env, check=True, timeout=30)
        assert not destination.bucket_exists("migration-check")
        migration.migrate(source, destination, ["migration-check"], copy=True)
        stat = destination.stat_object("migration-check", "file.pdf")
        assert stat.content_type == "application/pdf"
        assert stat.metadata.get("X-Amz-Meta-Course") == "CS101"
        migration.migrate(source, destination, ["migration-check"], copy=True)
        destination.put_object("migration-check", "file.pdf", io.BytesIO(b"original"), 8,
                               content_type="application/pdf", metadata={"course": "CS102"})
        try:
            migration.migrate(source, destination, ["migration-check"], copy=True)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Migration ignored conflicting user metadata")
        destination.put_object("migration-check", "file.pdf", io.BytesIO(b"different"), 9,
                               content_type="application/pdf", metadata={"course": "CS101"})
        try:
            migration.migrate(source, destination, ["migration-check"], copy=True)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Migration overwrote a conflicting destination without permission")
        migration.migrate(source, destination, ["migration-check"], copy=True, overwrite=True)
        assert migration.object_sha256(source, "migration-check", "file.pdf") == migration.object_sha256(destination, "migration-check", "file.pdf")
        print("PASS: migration dry-run, SHA-256, content type/metadata, resume and conflict protection", flush=True)
    except Exception:
        for name in servers:
            print(docker("logs", "--tail", "40", name), file=sys.stderr)
        raise
    finally:
        for name in servers:
            docker("rm", "--force", name)
        for volume in volumes:
            docker("volume", "rm", volume)


if __name__ == "__main__":
    main()
