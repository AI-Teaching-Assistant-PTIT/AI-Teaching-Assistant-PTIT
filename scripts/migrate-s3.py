"""Copy current S3 objects to a new storage server; dry-run unless --copy is set."""

import argparse
import hashlib
import os
import sys
from urllib.parse import urlsplit

from minio import Minio
from minio.error import S3Error


class HashingReader:
    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()
        self.size = 0

    def read(self, size=-1):
        chunk = self.stream.read(size)
        self.digest.update(chunk)
        self.size += len(chunk)
        return chunk


def client(endpoint, prefix):
    url = urlsplit(endpoint if "://" in endpoint else "http://" + endpoint)
    if url.scheme not in {"http", "https"} or not url.netloc or url.path not in {"", "/"}:
        raise ValueError("Endpoints must be http(s)://host:port without a path")
    if url.username or url.password or url.query or url.fragment:
        raise ValueError("Pass credentials through environment variables, not endpoint URLs")
    access_key = os.getenv(prefix + "_S3_ACCESS_KEY") or os.getenv("MINIO_ACCESS_KEY")
    secret_key = os.getenv(prefix + "_S3_SECRET_KEY") or os.getenv("MINIO_SECRET_KEY")
    if not access_key or not secret_key:
        raise ValueError(f"Set {prefix}_S3_ACCESS_KEY and {prefix}_S3_SECRET_KEY")
    return Minio(url.netloc, access_key=access_key, secret_key=secret_key, secure=url.scheme == "https")


def object_sha256(storage, bucket, key):
    response = storage.get_object(bucket, key)
    try:
        reader = HashingReader(response)
        while reader.read(1024 * 1024):
            pass
        return reader.digest.hexdigest()
    finally:
        response.close()
        response.release_conn()


def exists(storage, bucket, key):
    try:
        storage.stat_object(bucket, key)
        return True
    except S3Error as error:
        if error.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
            return False
        raise


def user_metadata(stat):
    return {
        key.lower()[11:]: value
        for key, value in stat.metadata.items()
        if key.lower().startswith("x-amz-meta-")
    }


def migrate(source, destination, buckets, copy=False, overwrite=False):
    copied = skipped = planned = 0
    for bucket in buckets:
        if copy and not destination.bucket_exists(bucket):
            destination.make_bucket(bucket)
        for item in source.list_objects(bucket, recursive=True):
            planned += 1
            if not copy:
                continue
            stat = source.stat_object(bucket, item.object_name)
            if exists(destination, bucket, item.object_name) and not overwrite:
                target_stat = destination.stat_object(bucket, item.object_name)
                if ((stat.content_type or "application/octet-stream") != (target_stat.content_type or "application/octet-stream")
                    or user_metadata(stat) != user_metadata(target_stat)
                    or object_sha256(source, bucket, item.object_name) != object_sha256(destination, bucket, item.object_name)):
                    raise RuntimeError(f"Destination object differs in bucket {bucket}; use --overwrite to replace it")
                skipped += 1
                continue
            metadata = user_metadata(stat)
            response = source.get_object(bucket, item.object_name)
            try:
                reader = HashingReader(response)
                destination.put_object(
                    bucket, item.object_name, reader, stat.size,
                    content_type=stat.content_type or "application/octet-stream",
                    metadata=metadata,
                )
                if reader.size != stat.size or object_sha256(destination, bucket, item.object_name) != reader.digest.hexdigest():
                    raise RuntimeError(f"SHA-256 verification failed in bucket {bucket}")
            finally:
                response.close()
                response.release_conn()
            copied += 1
        print(f"Bucket {bucket}: scanned", flush=True)
    print(f"Objects: {planned}; copied and verified: {copied}; identical skipped: {skipped}")
    if not copy:
        print("Dry run: destination unchanged. Add --copy to copy and verify objects.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-endpoint", required=True)
    parser.add_argument("--destination-endpoint", required=True)
    parser.add_argument("--bucket", action="append", help="Repeat for specific buckets; default: all source buckets")
    parser.add_argument("--copy", action="store_true", help="Copy objects and verify SHA-256; source is never changed")
    parser.add_argument("--overwrite", action="store_true", help="Replace destination objects whose content differs")
    args = parser.parse_args()
    if args.source_endpoint.rstrip("/") == args.destination_endpoint.rstrip("/"):
        parser.error("Source and destination must be different storage servers")
    source = client(args.source_endpoint, "SOURCE")
    destination = client(args.destination_endpoint, "DESTINATION")
    buckets = args.bucket or [bucket.name for bucket in source.list_buckets()]
    migrate(source, destination, buckets, copy=args.copy, overwrite=args.overwrite)


if __name__ == "__main__":
    try:
        main()
    except (S3Error, RuntimeError, ValueError) as error:
        print(f"Migration failed: {error}", file=sys.stderr)
        sys.exit(1)
