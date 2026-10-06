# AI-Teaching-Assistant-PTIT (NITS)

Repo tổng của hệ thống **NITS**, một nền tảng học tập theo dự án (Project-Based Learning) có hỗ trợ AI dành cho các môn Khoa học Máy tính tại PTIT.

Repo này không chứa code. Nó gom các repo thành phần dưới dạng **git submodule** và ghim mỗi repo vào một commit cụ thể, nên một commit ở đây ứng với một tổ hợp phiên bản đồng bộ của cả hệ thống.

## Thành phần

| Thư mục | Repo | Vai trò |
|---|---|---|
| [`web/`](web/) | [codebase-platform](https://github.com/AI-Teaching-Assistant-PTIT/codebase-platform) | Webapp PBL: backend FastAPI, các worker (knowledge, code-intelligence, defense), frontend, embedding service |
| [`kubernetes/`](kubernetes/) | [git-platform](https://github.com/AI-Teaching-Assistant-PTIT/git-platform) | Hạ tầng: GitPTIT (Gitea tùy biến + Microsoft SSO), PostgreSQL/pgvector, SeaweedFS S3, Docling, Cloudflare Tunnel; Docker Compose cho demo, `infra/` (Terraform, Ansible, Argo CD) cho K3s |
| [`config/`](config/) | [config-repo](https://github.com/AI-Teaching-Assistant-PTIT/config-repo) | GitOps source of truth: Helm values theo `<service>/<môi trường>`, được Argo CD đồng bộ xuống cluster |

```text
 web ──CI build──▶ GHCR image ──CI cập nhật tag──▶ config ──Argo CD──▶ K3s cluster
                                                     ▲
 kubernetes ── Ansible cài K3s, Helm, Argo CD ───────┘
```

## Bắt đầu

Clone kèm toàn bộ submodule:

```bash
git clone --recurse-submodules git@github.com:AI-Teaching-Assistant-PTIT/AI-Teaching-Assistant-PTIT.git NITS
```

Nếu đã clone mà chưa có submodule:

```bash
git submodule update --init --recursive
```

Các image ứng dụng của dự án nằm trên GHCR ở chế độ private, nên cần đăng nhập bằng token có quyền `read:packages` trước khi pull:

```bash
gh auth refresh -h github.com -s read:packages
gh auth token | docker login ghcr.io -u <github-user> --password-stdin
```

Object storage dùng image công khai `chrislusf/seaweedfs:4.48`. Tên service `minio`, port S3 `9000`, tên bucket và các biến `MINIO_*` của backend được giữ để tương thích với image ứng dụng hiện có. Port `9001` là SeaweedFS Admin UI, đăng nhập bằng `S3_ACCESS_KEY` / `S3_SECRET_KEY`.

Máy cài mới chạy `docker compose up --build`. Nếu đã có dữ liệu MinIO, thực hiện [hướng dẫn chuyển sang SeaweedFS](docs/seaweedfs-migration.md) trước khi cho ứng dụng ghi vào storage mới. SeaweedFS dùng volume mới `platform_seaweedfs_data`; volume MinIO cũ không được tái sử dụng hay tự xóa.

Cách chạy từng phần xem trong README của repo tương ứng:

- Chạy demo cả stack bằng Docker Compose, hoặc triển khai lên K3s: [kubernetes/README.md](kubernetes/README.md)
- Phát triển webapp: [web/README.md](web/README.md)
- Cấu trúc GitOps và môi trường `stag`/`prod`: [config/README.md](config/README.md)

## Làm việc với submodule

| Việc cần làm | Lệnh |
|---|---|
| Cập nhật mọi submodule lên commit mà repo tổng đang ghim | `git submodule update --init --recursive` |
| Kéo commit mới nhất của nhánh `main` cho mọi submodule | `git submodule update --remote` |
| Xem mỗi submodule đang ở commit nào | `git submodule status` |
| Chạy một lệnh trong mọi submodule | `git submodule foreach 'git status --short'` |

Quy trình cập nhật một thành phần:

1. Commit và push thay đổi **bên trong** submodule, ví dụ `web/`, lên repo của nó.
2. Quay về repo tổng, rồi `git add web` để ghim commit mới.
3. Commit ở repo tổng, ví dụ `chore: bump web to <sha>`.

> Commit ở repo tổng phải trỏ tới commit đã được push lên remote của submodule. Nếu chưa push, người khác clone về sẽ không checkout được.
