# SeaweedFS S3 cho NITS

Stack dùng image công khai `chrislusf/seaweedfs:4.48`, chế độ `weed mini` một node. Image hỗ trợ Linux AMD64 và ARM64. S3 API ở port `9000`, Admin UI ở port `9001`. Credentials lấy từ `S3_ACCESS_KEY` / `S3_SECRET_KEY`; Compose phát triển trong `web/` dùng `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`.

Tên service `minio`, endpoint `minio:9000` / `minio-demo:9000`, secret và biến backend `MINIO_*` được giữ để các image ứng dụng hiện có tiếp tục kết nối. Thư viện Python `minio` làm S3 client, không yêu cầu server MinIO. SeaweedFS tự tạo bucket lúc khởi động; healthcheck là `GET /healthz`, không cần `mc`.

Nguồn upstream: [SeaweedFS](https://github.com/seaweedfs/seaweedfs), [release 4.48](https://github.com/seaweedfs/seaweedfs/releases/tag/4.48).

## Máy cài mới

Điền `.env`, đăng nhập GHCR để tải image ứng dụng private rồi chạy:

```bash
docker compose up --build
```

Compose tổng không publish port ra host. Trong mạng Docker, S3: `http://minio:9000`; Admin: `http://minio:9001`, đăng nhập bằng `S3_ACCESS_KEY` / `S3_SECRET_KEY`. Cloudflared cùng mạng Docker có thể dùng các endpoint này làm origin nếu cần truy cập qua tunnel. Compose phát triển trong `web/` dùng port host `9010` / `9011`.

Volume mới là `platform_seaweedfs_data`, hoặc `<web-project>_app-seaweedfs-data` cho Compose của web. Volume/PVC MinIO có định dạng khác và không được mount vào SeaweedFS.

## Chuyển dữ liệu Compose tổng

Thực hiện trong cửa sổ bảo trì và sao lưu dữ liệu trước khi chuyển. Giữ file Compose cũ để rollback. Tạm dừng các job backup khác đang ghi S3 nếu có. Các bước dưới đây không xóa volume cũ.

1. Xác nhận volume cũ và image MinIO đã có trên máy. Overlay dùng `pull_policy: never`, không cần tải lại image từ registry. Nếu tên volume/image khác, đặt `MINIO_LEGACY_VOLUME` / `MINIO_LEGACY_IMAGE` bằng tên thực tế trước khi chạy.

```bash
docker volume inspect platform_minio_data
docker image inspect minio/minio:RELEASE.2025-04-22T22-12-26Z
```

2. Dừng các thành phần ghi dữ liệu, rồi khởi động SeaweedFS và MinIO tạm đọc volume cũ. Volume cũ được khai báo `external`, nên Compose báo lỗi nếu không tồn tại thay vì tạo một volume rỗng.

```bash
docker compose stop api knowledge-worker code-intelligence-worker defense-worker minio
docker compose -f docker-compose.yaml -f compose.storage-migration.yaml up -d --no-deps minio minio-legacy
```

3. Liệt kê phạm vi chuyển bằng dry-run. Script chạy trong image backend, dùng S3 credentials từ môi trường của service `api`; credentials source/destination khác nhau có thể truyền qua `SOURCE_S3_ACCESS_KEY`, `SOURCE_S3_SECRET_KEY`, `DESTINATION_S3_ACCESS_KEY`, `DESTINATION_S3_SECRET_KEY`.

```bash
docker compose -f docker-compose.yaml -f compose.storage-migration.yaml run --rm --no-deps --entrypoint python -v "$PWD/scripts:/migration:ro" api /migration/migrate-s3.py --source-endpoint http://minio-legacy:9000 --destination-endpoint http://minio:9000
```

4. Chạy lại lệnh với `--copy` để tạo bucket, copy object và kiểm tra SHA-256 sau mỗi object:

```bash
docker compose -f docker-compose.yaml -f compose.storage-migration.yaml run --rm --no-deps --entrypoint python -v "$PWD/scripts:/migration:ro" api /migration/migrate-s3.py --source-endpoint http://minio-legacy:9000 --destination-endpoint http://minio:9000 --copy
```

Mặc định chuyển tất cả bucket source; dùng `--bucket TEN_BUCKET` nhiều lần để giới hạn. Script copy object hiện tại, content type và user metadata; không copy lịch sử version, bucket policy, ACL hay cấu hình lifecycle. Nó không thay đổi source và không xóa object destination. Object destination giống nhau được bỏ qua; object khác nội dung làm script dừng, trừ khi thêm `--overwrite`. Giữ các writer dừng trong suốt quá trình copy.

5. Sau khi copy thành công, khởi động ứng dụng, kiểm tra tải tài liệu cũ và upload/download mới. Với nơi dùng backup PostgreSQL, thử tạo một backup vào SeaweedFS và restore vào database thử nghiệm trước khi đóng đợt chuyển đổi.

```bash
docker compose up -d api knowledge-worker code-intelligence-worker defense-worker frontend
docker compose -f docker-compose.yaml -f compose.storage-migration.yaml stop minio-legacy
```

Giữ volume MinIO và bản sao lưu cho đến khi dữ liệu mới được kiểm chứng. Rollback bằng Compose cũ và volume MinIO cũ; dữ liệu mới phát sinh sau cutover cần được copy ngược qua S3 trước khi rollback.

## Compose phát triển trong web

Volume cũ là `<web-project>_app-minio-data`, volume mới là `<web-project>_app-seaweedfs-data`. Tìm tên thật bằng `docker volume ls --filter name=app-minio-data`. Dừng backend/worker trước khi thay storage. Dùng cached image `minio/minio:RELEASE.2025-09-07T16-13-09Z` với volume cũ để mở endpoint source, rồi dùng cùng script chuyển S3 sang endpoint mới. Credentials có thể khác ví dụ Compose tổng; dùng các biến `SOURCE_S3_*` / `DESTINATION_S3_*` khi cần.

## Helm / K3s

Giữ đường dẫn chart `kubernetes/minio/helm-chart` và values `config/minio/demo/values.yaml` để không đổi ApplicationSet, service DNS và các cấu hình backup hiện có. Chart chạy một replica, strategy `Recreate`; nhiều replica hoặc bật HPA sẽ bị từ chối vì `mini` không phải topology phân tán.

PVC mới: `<fullname>-seaweedfs`. Mặc định `persistence.retainLegacyMinioClaim=true` tiếp tục khai báo PVC MinIO `<fullname>` với `helm.sh/resource-policy: keep` và `argocd.argoproj.io/sync-options: Prune=false`. PVC cũ không được gắn vào SeaweedFS. Cài mới có thể đặt cờ này thành `false`; với cluster đang có dữ liệu, giữ cờ trong lần nâng cấp và suốt thời gian bảo trì.

Chart ánh xạ secret key `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` sang `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` và `WEED_ADMIN_USER` / `WEED_ADMIN_PASSWORD`, nên không cần thay runtime secret. NetworkPolicy cho pod cùng namespace vào port S3/Admin; CNI phải thực thi NetworkPolicy. Các API master, volume và filer không được đưa vào Service. Client ở namespace khác cần bổ sung rule ingress trước khi chuyển.

Manifest được kiểm tra schema offline theo Kubernetes `1.36.3` mà infra repo ghim qua K3s `v1.36.3+k3s1`. Cluster đích, admission policy và storage thực tế cần được kiểm tra bằng server dry-run/diff dưới đây trước khi triển khai. PVC mới cũng có bảo vệ prune để dữ liệu SeaweedFS được giữ khi rollback.

Trước khi sync, tạm dừng writer/backup và auto-sync của app storage trong cửa sổ bảo trì. Chạy MinIO tạm với PVC cũ trên node đang giữ dữ liệu, sử dụng đúng cached image trước đó. Sau khi SeaweedFS có PVC mới, copy qua hai endpoint S3 và kiểm chứng như phần Compose. `kubectl port-forward` có thể đưa hai endpoint về máy chạy script. Chỉ mở lại writer/backup sau khi xác minh xong; giữ PVC cũ để rollback. Tài liệu này không tự triển khai hay chuyển dữ liệu cluster.

Kiểm tra chart và diff trên cluster đích trước khi sync:

```bash
helm lint kubernetes/minio/helm-chart -f config/minio/demo/values.yaml
helm template minio-demo kubernetes/minio/helm-chart --namespace demo -f config/minio/demo/values.yaml > /tmp/seaweedfs-demo.yaml
kubectl apply --dry-run=server -f /tmp/seaweedfs-demo.yaml
kubectl diff -f /tmp/seaweedfs-demo.yaml
```

Rollback bằng revision/chart MinIO cũ và PVC cũ. Giữ tên release/namespace và credentials; dữ liệu phát sinh sau cutover phải được chuyển ngược trước khi quay lại storage cũ.

## Kiểm tra tích hợp cục bộ

Với Python environment của web đã có dependency `minio`:

```bash
web/.venv/bin/python scripts/check-seaweedfs.py
```

Script tạo hai container/volume riêng, chỉ publish port ngẫu nhiên trên loopback, thử code storage thật của backend (gồm multipart 11 MB, key Unicode, object rỗng và dữ liệu sau restart), xác thực sai và migration. Tài nguyên thử nghiệm được tự xóa. Nó không dùng database hay volume của ứng dụng.
