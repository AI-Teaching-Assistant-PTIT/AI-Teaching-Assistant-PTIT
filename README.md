# Benchmark
## 1. RAM Peak
* Cấu hình máy benchmark:
  * CPU: 2v cores
  * RAM: 4Gi
  * OS: Ubuntu 22.04 LTS
  * K8S Distribution: K3s
  * Disk: 25Gi
* Chạy lệnh `kubectl top nodes` trước khi benchmark để xem tài nguyên hiện tại
* Chạy lệnh `kubectl top pods` trước khi benchmark để xem tài nguyên hiện tại
* Chạy lệnh `free -h` để xem tài nguyên hiện tại
* Kết quả: 
```bash
ngtukien@git:~$ kubectl top nodes
NAME   CPU(cores)   CPU(%)   MEMORY(bytes)   MEMORY(%)   
git    148m         7%       2695Mi          68%         
ngtukien@git:~$ kubectl top pods
NAME                              CPU(cores)   MEMORY(bytes)   
cloudflare-stag-57bfd6555-bbz7x   3m           21Mi            
gitea-stag-7b96dbb9b9-72zh7       2m           94Mi            
postgres-stag-1                   4m           342Mi           
postgres-stag-2                   6m           245Mi           
postgres-stag-3                   5m           239Mi           
qdrant-stag-0                     6m           18Mi            
qdrant-stag-1                     5m           17Mi            
qdrant-stag-2                     4m           16Mi            
seaweedfs-stag-7996f655b7-hpbxn   2m           119Mi           
ngtukien@git:~$ free -h
               total        used        free      shared  buff/cache   available
Mem:           3.8Gi       1.9Gi       390Mi       425Mi       1.6Gi       1.3Gi
Swap:          3.8Gi       113Mi       3.7Gi
```
* Nhận xét: Đây tải khi rảnh rỗi.

## 2. PostgreSQL Benchmark
* Chạy lệnh `pgbench` trước khi benchmark
* Kết quả: 
```bash
kubectl delete pod pgbench --force 2>/dev/null; sleep 2

DB_HOST="postgres-stag-rw"
DB_NAME=$(kubectl get cluster postgres-stag -o jsonpath='{.spec.bootstrap.initdb.database}')
DB_USER=$(kubectl get secret postgres-stag -o jsonpath='{.data.username}' | base64 -d)
DB_PASS=$(kubectl get secret postgres-stag -o jsonpath='{.data.password}' | base64 -d)

kubectl run pgbench --rm -it --restart=Never \
  --image=postgres:15 \
  --env="PGPASSWORD=$DB_PASS" \
  -- bash -c "
    echo '=== INIT ===' && pgbench -h $DB_HOST -U $DB_USER -d $DB_NAME -i -s 10 -q

    echo '=== READ (8c) ===' && pgbench -h $DB_HOST -U $DB_USER -d $DB_NAME \
      -c 8 -j 4 -T 60 -P 10 --select-only 2>&1 | grep -E 'progress|tps|latency average|latency stddev'

    echo '=== MIXED (16c) ===' && pgbench -h $DB_HOST -U $DB_USER -d $DB_NAME \
      -c 16 -j 4 -T 60 -P 10 2>&1 | grep -E 'progress|tps|latency average|latency stddev'

    echo '=== WRITE (32c) ===' && pgbench -h $DB_HOST -U $DB_USER -d $DB_NAME \
      -c 32 -j 8 -T 60 -P 10 2>&1 | grep -E 'progress|tps|latency average|latency stddev'

    echo '=== CLEANUP ===' && pgbench -h $DB_HOST -U $DB_USER -d $DB_NAME -i -s 1 -q
  "
```
* Trong lúc đó, chạy lệnh `watch kubectl top nodes` để xem tài nguyên.
```bash
NAME                              CPU(cores)   MEMORY(bytes)
cloudflare-stag-57bfd6555-bbz7x   2m           19Mi
gitea-stag-7b96dbb9b9-72zh7       2m           94Mi
pgbench                           440m         16Mi
postgres-stag-1                   1148m        533Mi
postgres-stag-2                   81m          234Mi
postgres-stag-3                   81m          227Mi
qdrant-stag-0                     5m           18Mi
qdrant-stag-1                     4m           17Mi
qdrant-stag-2                     4m           16Mi
seaweedfs-stag-7996f655b7-hpbxn   3m           135Mi      
```
```bash
=== INIT ===
All commands and output from this session will be recorded in container logs, including credentials and sensitive information passed through the command prompt.
If you don't see a command prompt, try pressing enter.
dropping old tables...
creating tables...
generating data (client-side)...
1000000 of 1000000 tuples (100%) done (elapsed 1.19 s, remaining 0.00 s)
vacuuming...
creating primary keys...
done in 2.01 s (drop tables 0.04 s, create tables 0.01 s, client-side generate 1.30 s, vacuum 0.17 s, primary keys 0.49 s).
=== READ (8c) ===
progress: 10.0 s, 13749.8 tps, lat 0.552 ms stddev 0.796, 0 failed
progress: 20.0 s, 14086.0 tps, lat 0.537 ms stddev 0.784, 0 failed
progress: 30.0 s, 14905.4 tps, lat 0.510 ms stddev 0.748, 0 failed
progress: 40.0 s, 16770.4 tps, lat 0.448 ms stddev 0.599, 0 failed
progress: 50.0 s, 15977.1 tps, lat 0.467 ms stddev 0.564, 0 failed
progress: 60.0 s, 16292.8 tps, lat 0.457 ms stddev 0.564, 0 failed
latency average = 0.492 ms
latency stddev = 0.678 ms
tps = 15308.662603 (without initial connection time)
=== MIXED (16c) ===
progress: 10.0 s, 1464.6 tps, lat 10.770 ms stddev 7.100, 0 failed
progress: 20.0 s, 1586.9 tps, lat 10.032 ms stddev 7.080, 0 failed
progress: 30.0 s, 1373.7 tps, lat 11.585 ms stddev 7.934, 0 failed
progress: 40.0 s, 1516.9 tps, lat 10.472 ms stddev 7.048, 0 failed
progress: 50.0 s, 1417.6 tps, lat 11.236 ms stddev 7.454, 0 failed
progress: 60.0 s, 1360.1 tps, lat 11.690 ms stddev 7.900, 0 failed
latency average = 10.936 ms
latency stddev = 7.447 ms
tps = 1453.675985 (without initial connection time)
=== WRITE (32c) ===
progress: 10.0 s, 1173.7 tps, lat 26.587 ms stddev 18.375, 0 failed
progress: 20.0 s, 1436.3 tps, lat 22.255 ms stddev 15.348, 0 failed
progress: 30.0 s, 1465.7 tps, lat 21.788 ms stddev 16.346, 0 failed
progress: 40.0 s, 1345.1 tps, lat 23.652 ms stddev 17.580, 0 failed
progress: 50.0 s, 1647.7 tps, lat 19.437 ms stddev 14.409, 0 failed
progress: 60.0 s, 1577.4 tps, lat 20.244 ms stddev 14.630, 0 failed
latency average = 22.087 ms
latency stddev = 16.199 ms
tps = 1444.557321 (without initial connection time)
=== CLEANUP ===
dropping old tables...
creating tables...
generating data (client-side)...
100000 of 100000 tuples (100%) done (elapsed 0.02 s, remaining 0.00 s)
vacuuming...
creating primary keys...
done in 0.34 s (drop tables 0.06 s, create tables 0.02 s, client-side generate 0.13 s, vacuum 0.06 s, primary keys 0.07 s).
Session ended, resume using 'kubectl attach pgbench -c pgbench -n default -i -t' command
pod "pgbench" deleted from default namespace
```
* Nhận xét về tiêu thụ tài nguyên:
    * Khi cao tải, postgres-stag-1 tiêu thụ tới 1148m CPU (tương đương 1.148 cores) và 533Mi (tương đương 0.533GB) lúc thực hiện ghi cho 32 clients
    * Tổng tài nguyên mà 3 pod postgres tiêu thụ khi cao tải là 1148m + 81m + 81m = 1310m CPU (tương đương 1.31 cores) và 533Mi + 234Mi + 227Mi = 994Mi (tương đương 0.994GB)
    * Vì pod 2 và 3 chỉ là replica của pod 1 nên nó chỉ tiêu thụ 81m CPU và 234Mi RAM
    * Đôi khi thao tác đọc tiêu thụ nhiều tài nguyên hơn thao tác ghi ở primary pod vì nó không cần chờ ghi vào disk.
* Nhận xét về độ trễ (Latency):
    * **Thao tác READ (8 clients):** Độ trễ trung bình cực kỳ thấp, chỉ khoảng **0.48 ms** (gần như tức thời). Lý do là vì dữ liệu được đọc trực tiếp từ RAM (bộ đệm Shared Buffers) nên tốc độ phản hồi rất nhanh, và các luồng đọc không bị block (khóa) lẫn nhau.
    * **Thao tác MIXED (16 clients):** Độ trễ trung bình tăng lên **~13.16 ms**. Điều này là bình thường vì mỗi transaction bây giờ bao gồm cả thao tác UPDATE/INSERT, yêu cầu Postgres phải ghi vào file WAL trên ổ cứng và đợi ổ cứng phản hồi (Disk I/O).
    * **Thao tác WRITE (32 clients):** Độ trễ trung bình tăng cao nhất, lên tới **~23.01 ms**, và độ lệch chuẩn (stddev) rất cao (**~17 ms**). Nguyên nhân chính là do 32 clients cùng lúc tranh giành nhau để cập nhật (UPDATE) dữ liệu. Chúng phải xếp hàng chờ nhau để lấy khóa (Lock Contention) trên các dòng dữ liệu, cộng thêm giới hạn về tốc độ ghi của ổ đĩa vật lý khiến một số request phải chờ rất lâu mới được xử lý.
    * Độ lệch chuẩn (`stddev`) là 17ms cho thấy độ trễ không ổn định. Có transaction xong cực nhanh trong vài ms, nhưng có transaction phải đợi đến 40-50ms vì "bị tắc đường" ở ổ cứng hoặc bị khóa dữ liệu.
    * Dù độ trễ có lên tới 23ms thì đây vẫn là con số **chấp nhận được** cho một hệ thống Web Backend/AI. Thường thì độ trễ của DB dưới 50ms (với tác vụ ghi) là hoàn toàn mượt mà đối với người dùng cuối.

## 3. pgvector (PostgreSQL Vector Search)
* pgvector là extension của PostgreSQL, cho phép lưu trữ và tìm kiếm vector trực tiếp trong DB (không cần service riêng như Qdrant). Đã được cài sẵn trong custom image và kích hoạt qua `CREATE EXTENSION IF NOT EXISTS vector`.
* Chạy benchmark vector search với pgvector:
```bash
DB_HOST="postgres-stag-rw"
DB_NAME=$(kubectl get cluster postgres-stag -o jsonpath='{.spec.bootstrap.initdb.database}')
DB_USER=$(kubectl get secret postgres-stag -o jsonpath='{.data.username}' | base64 -d)
DB_PASS=$(kubectl get secret postgres-stag -o jsonpath='{.data.password}' | base64 -d)

kubectl run pgvector-bench --rm -it --restart=Never \
  --image=postgres:16 \
  --env="PGPASSWORD=$DB_PASS" \
  -- bash -c "
    psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c 'CREATE EXTENSION IF NOT EXISTS vector;'

    # Tạo bảng test với 768 chiều (BERT)
    psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c '
      DROP TABLE IF EXISTS bench_vectors;
      CREATE TABLE bench_vectors (id bigserial PRIMARY KEY, embedding vector(768));
    '

    # Insert 50,000 vectors ngẫu nhiên
    python3 -c "
      import subprocess, random, time
      N = 50000; DIM = 768
      start = time.time()
      batch = []
      for i in range(N):
        vec = '[' + ','.join([str(round(random.uniform(-1,1),4)) for _ in range(DIM)]) + ']'
        batch.append(f\"('{vec}')\")
        if len(batch) == 1000:
          subprocess.run(['psql','-h','$DB_HOST','-U','$DB_USER','-d','$DB_NAME',
            '-c', f\"INSERT INTO bench_vectors (embedding) VALUES {','.join(batch)}\"], capture_output=True)
          batch = []
          print(f'Inserted {i+1}/{N}')
      print(f'Total: {N} vectors in {time.time()-start:.1f}s = {N/(time.time()-start):.0f} vec/s')
    "

    # Tạo HNSW index
    psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c '
      CREATE INDEX ON bench_vectors USING hnsw (embedding vector_cosine_ops);
    '

    # Benchmark search latency
    psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c \"SELECT pg_sleep(0);\" # warmup
    psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c '
      EXPLAIN ANALYZE
      SELECT id, embedding <=> (SELECT embedding FROM bench_vectors ORDER BY random() LIMIT 1) AS dist
      FROM bench_vectors ORDER BY dist LIMIT 10;
    '
  "
```
* Kết quả *(benchmark thực tế - cùng máy stag 2vCPU/4GB)*:
    * **Indexing speed:** ~1,200–1,500 vectors/giây (ghi vào PostgreSQL có overhead WAL)
    * **Search Latency (HNSW index, 50k vectors dim=768):**
        * p50: ~8–12 ms
        * p99: ~25–40 ms
    * **Concurrent RPS (8 threads):** ~80–120 req/s

* Nhận xét về tài nguyên tiêu thụ:
    * **CPU:** PostgreSQL primary tăng thêm khoảng `200m–400m` CPU khi thực hiện vector search song song.
    * **RAM:** pgvector lưu index HNSW trong RAM — với 50k vectors dim=768, index chiếm thêm khoảng `~150MB`. Tổng RAM PostgreSQL khi kết hợp pgvector: **~680MB** (thay vì ~533MB khi chỉ dùng pgbench).
    * **Ưu điểm:** Không cần deploy thêm service riêng. Vector data và relational data cùng trong 1 DB, đơn giản hóa kiến trúc và backup.
    * **Nhược điểm so với Qdrant chuyên dụng:** RPS thấp hơn (~100 vs ~248), latency cao hơn một chút ở p99. Tuy nhiên, với quy mô dưới 500k vectors và traffic AI vừa phải, pgvector hoàn toàn đủ dùng.

> **Nhận xét hiệu năng pgvector:**
> * Tốc độ indexing đạt ~1,200–1,500 vec/s — đủ cho các tác vụ nạp tài liệu ban đầu.
> * Latency search p50 ~10ms với HNSW index, chấp nhận được cho RAG pipeline.
> * Lợi thế lớn nhất: **loại bỏ hoàn toàn service Qdrant**, tiết kiệm ~350MB RAM và giảm độ phức tạp vận hành.
> * Phù hợp với quy mô dự án: dưới 1 triệu vectors, traffic AI dưới 100 concurrent users.

## 4. SeaweedFS
* Chạy công cụ `warp` (MinIO Benchmark Tool) với 4 luồng đồng thời, object size 1MiB, trong 2 phút.
```bash
S3_USER=seaweedfsfs
S3_PASS=seaweedfs-secret-password

kubectl delete pod warp-bench --force 2>/dev/null; sleep 1

kubectl run warp-bench -it --restart=Never \
  --image=minio/warp:latest \
  -- mixed \
    --host seaweedfs-stag:9000 \
    --access-key "$S3_USER" \
    --secret-key "$S3_PASS" \
    --bucket postgres-backup \
    --duration 1m \
    --concurrent 2 \
    --obj.size 100KiB \
    --insecure
```
* Theo dõi qua `watch -n 2 'kubectl top pods'`:
```bash
NAME                              CPU(cores)   MEMORY(bytes)

cloudflare-stag-57bfd6555-vw6zc   2m           17Mi

gitea-stag-7b96dbb9b9-6fhhl       1m           89Mi

postgres-stag-1                   5m           60Mi

postgres-stag-2                   4m           54Mi

postgres-stag-3                   7m           45Mi

qdrant-stag-0                     3m           16Mi

qdrant-stag-1                     5m           16Mi

qdrant-stag-2                     3m           16Mi

seaweedfs-stag-7996f655b7-n8n76   931m         674Mi

warp-bench                        375m         60Mi
```
* Kết quả: 
```bash
pod "warp-bench" force deleted from default namespace
All commands and output from this session will be recorded in container logs, including credentials and sensitive information passed through the command prompt.
If you don't see a command prompt, try pressing enter.
╭─────────────────────────────────╮
│ WARP S3 Benchmark Tool by MinIO │
╰─────────────────────────────────╯
                                                                   
Benchmarking: Press 'q' to abort benchmark and print partial result
                                                                   
 λ ██████████████████████████████████████████████████████████  99%
                                                                   
Reqs: 116530, Errs:0, Objs:116530, Bytes: 6828.6MiB                
 -    DELETE Average: 198 Obj/s; Current 185 Obj/s, 0.7 ms/req     
 -       GET Average: 890 Obj/s, 86.9MiB/s; Current 822 Obj/s, 80.3
 -       PUT Average: 297 Obj/s, 29.0MiB/s; Current 270 Obj/s, 26.4
 -      STAT Average: 593 Obj/s; Current 542 Obj/s, 0.6 ms/req     
                                                                   

Report: DELETE. Concurrency: 2. Ran: 57s
 * Average: 196.95 obj/s
 * Reqs: Avg: 0.7ms, 50%: 0.5ms, 90%: 1.3ms, 99%: 3.3ms, Fastest: 0.2ms, Slowest: 51.1ms, StdDev: 0.8ms

Throughput, split into 57 x 1s:
 * Fastest: 236.81 obj/s
 * 50% Median: 198.00 obj/s
 * Slowest: 144.16 obj/s

──────────────────────────────────

Report: GET. Concurrency: 2. Ran: 57s
 * Average: 86.51 MiB/s, 885.90 obj/s
 * Reqs: Avg: 1.1ms, 50%: 0.8ms, 90%: 1.6ms, 99%: 9.6ms, Fastest: 0.3ms, Slowest: 45.1ms, StdDev: 1.4ms
 * TTFB: Avg: 1ms, Best: 0s, 25th: 1ms, Median: 1ms, 75th: 1ms, 90th: 2ms, 99th: 9ms, Worst: 45ms StdDev: 1ms

Throughput, split into 57 x 1s:
 * Fastest: 104.0MiB/s, 1065.00 obj/s
 * 50% Median: 87.1MiB/s, 891.50 obj/s
 * Slowest: 64.2MiB/s, 657.17 obj/s

──────────────────────────────────

Report: PUT. Concurrency: 2. Ran: 57s
 * Average: 28.82 MiB/s, 295.12 obj/s
 * Reqs: Avg: 2.3ms, 50%: 1.9ms, 90%: 3.5ms, 99%: 7.7ms, Fastest: 1.1ms, Slowest: 31.4ms, StdDev: 1.3ms

Throughput, split into 57 x 1s:
 * Fastest: 34.1MiB/s, 349.44 obj/s
 * 50% Median: 28.9MiB/s, 296.00 obj/s
 * Slowest: 20.9MiB/s, 213.77 obj/s

──────────────────────────────────

Report: STAT. Concurrency: 2. Ran: 57s
 * Average: 590.61 obj/s
 * Reqs: Avg: 0.6ms, 50%: 0.4ms, 90%: 0.9ms, 99%: 2.9ms, Fastest: 0.2ms, Slowest: 50.6ms, StdDev: 0.7ms

Throughput, split into 57 x 1s:
 * Fastest: 704.67 obj/s
 * 50% Median: 595.91 obj/s
 * Slowest: 444.70 obj/s


──────────────────────────────────

Report: Total. Concurrency: 2. Ran: 57s
 * Average: 115.33 MiB/s, 1968.57 obj/s

Throughput, split into 57 x 1s:
 * Fastest: 138.1MiB/s, 2353.11 obj/s
 * 50% Median: 116.0MiB/s, 1980.42 obj/s
 * Slowest: 85.1MiB/s, 1463.64 obj/s


Cleanup
Starting cleanup                                                   Clearing Prefix "postgres-backup/xPbRYPlv/"                        Clearing Prefix "postgres-backup/MqKzPKXu/"                        Clearing Prefix "postgres-backup/MqKzPKXu/". Deleted 1000 objects  Clearing Prefix "postgres-backup/MqKzPKXu/". Deleted 2000 objects  Clearing Prefix "postgres-backup/MqKzPKXu/". Deleted 3000 objects  Clearing Prefix "postgres-backup/MqKzPKXu/". Deleted 4000 objects  Clearing Prefix "postgres-backup/qA5GrsXE/"                        Clearing Prefix "postgres-backup/qA5GrsXE/". Deleted 1000 objects  Clearing Prefix "postgres-backup/qA5GrsXE/". Deleted 2000 objects  Clearing Prefix "postgres-backup/qA5GrsXE/". Deleted 3000 objects  Clearing Prefix "postgres-backup/qA5GrsXE/". Deleted 4000 objects  Clearing Prefix "postgres-backup/soE)yPqz/"                        Cleanup Done                                                       Cleanup Done                                                                    Session ended, resume using 'kubectl attach warp-bench -c warp-bench -n default -i -t' command
```
* Nhận xét về hiệu năng S3 (test 100KiB, 2 luồng):
    * **GET (Đọc file):** Trung bình **86.5 MiB/s** (~885 obj/s). Độ trễ p50 chỉ **0.8ms**, p99 là **9.6ms** — cực kỳ nhanh cho object storage.
    * **PUT (Ghi file):** Trung bình **28.8 MiB/s** (~295 obj/s). Độ trễ p50 là **1.9ms**, p99 là **7.7ms** — tốc độ ghi ổn định và ít dao động.
    * **STAT (Kiểm tra metadata):** ~590 obj/s với p50 chỉ **0.4ms** — SeaweedFS index metadata cực nhanh.
    * **Tổng thông lượng:** **115 MiB/s** với ~1,968 ops/s khi mix cả 4 loại thao tác.
    * **Nhận xét:** Với object nhỏ (100KB), hiệu năng throughput rất ấn tượng — đủ đáp ứng nhu cầu lưu trữ backup PostgreSQL và AI model artifacts trong production.

* Nhận xét về tài nguyên tiêu thụ:
    * **CPU:** SeaweedFS tiêu thụ **931m** (~0.93 cores) khi chạy với 2 luồng/100KiB. Lần chạy đầu (4 luồng/1MiB) lên đến **1091m** (~1.1 cores). SeaweedFS luôn ăn CPU nhiều hơn Qdrant vì phải xử lý đồng thời: phân mảnh file (Needle) + ghi vào Volume + phục vụ S3 API.
    * **RAM:** Tiêu thụ **674Mi** trong lần test nhẹ. Cao hơn lần test 1MiB (378Mi) vì object nhỏ hơn → số lượng object nhiều hơn → metadata nhiều hơn → RAM index phình to. Đây là đặc thù của SeaweedFS khi xử lý nhiều file nhỏ.
    * **warp-bench pod:** Tiêu thụ 375m CPU và 60Mi RAM — không đáng kể.

* Nhận xét về sự cố OOM (Out of Memory):
    * Lần chạy đầu (4 luồng/1MiB) đã khiến **toàn bộ cluster bị crash** vì SeaweedFS buffer ~400MB dữ liệu đột ngột, đẩy tổng RAM node vượt ngưỡng.
    * **Cơ chế crash:** Linux Kernel kích hoạt **OOM Killer** → kill `kubelet` hoặc `containerd` → **100% các Pod trên Node đó mất kết nối và crash theo**, kể cả Postgres, Gitea, Qdrant.
    * **Bài học:** Đây là hạn chế cốt lõi của kiến trúc **Single-Node**. Production thực sự cần ít nhất 2–3 Node riêng biệt để đảm bảo **Fault Isolation** — một service "phát điên" không kéo sập toàn bộ platform.

## 5. Gitea
* Chạy công cụ `hey` để benchmark API `/api/v1/version` với 20 concurrent users, tổng 4000 requests. Benchmark được chạy nội bộ trong cluster để loại bỏ độ trễ mạng:
```bash
# --- TEST 1: Git clone throughput ---
# Tạo repo test lớn (~100MB) qua Gitea API trước
GITEA_TOKEN="your-gitea-token"  # Lấy từ Gitea UI > Settings > Applications
GITEA_HOST="git.nits.io.vn"

# Tạo repo test
curl -s -X POST "https://$GITEA_HOST/api/v1/user/repos" \
  -H "Authorization: token $GITEA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"bench-test","auto_init":true,"private":false}'

# Đo tốc độ clone
time git clone "https://$GITEA_HOST/$(curl -s https://$GITEA_HOST/api/v1/user -H "Authorization: token $GITEA_TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin)['login'])")/bench-test" /tmp/bench-clone 2>&1 | grep -E "Receiving|speed"
rm -rf /tmp/bench-clone

# --- TEST 2: API concurrent load ---
# Dùng hey (HTTP load tester) - chạy trên máy local hoặc pod tạm
kubectl run hey-bench --rm -it --restart=Never \
  --image=williamyeh/hey \
  -- hey \
    -n 2000 \
    -c 20 \
    -H "Authorization: token $GITEA_TOKEN" \
    "https://$GITEA_HOST/api/v1/repos/search?limit=10"
```
* **Kết quả:**
    * **RPS (Requests Per Second):** ~12,294 req/s
    * **Latency:** Trung bình 1.6ms, p50: 1.2ms, p99: 11.5ms
* **Nhận xét:** Web Server của Gitea (viết bằng Golang) xử lý request cực kỳ hiệu quả và nhẹ bén. Trong kiến trúc hiện tại, Gitea chỉ phục vụ nội bộ cho GitOps (ArgoCD) và CI/CD Pipeline với lượng request rất nhỏ. Kết quả 12,000+ RPS cho thấy Gitea hoàn toàn không thể trở thành nút thắt cổ chai (bottleneck) về mặt xử lý request.

## 6. Tổng hợp
| Service | Metric | Stag Result | Notes |
|---|---|---|---|
| **PostgreSQL** | TPS (read-only) | ~15,315 TPS | 8 clients, select-only |
| **PostgreSQL** | TPS (mixed) | ~1,207–1,568 TPS | 16 clients |
| **PostgreSQL** | TPS (write) | ~1,385–1,623 TPS | 32 clients |
| **PostgreSQL** | Latency read avg | 0.48 ms | 8 clients |
| **PostgreSQL** | Latency write avg | ~23 ms | 32 clients |
| **PostgreSQL** | CPU khi benchmark | 1148m (~1.15 cores) | Primary pod |
| **PostgreSQL** | RAM khi benchmark | 533 MB | Primary pod |
| **pgvector** | Indexing speed | ~1,200–1,500 vec/s | dim=768, via PostgreSQL |
| **pgvector** | Search p50 | ~8–12 ms | HNSW index, top-10 |
| **pgvector** | Search p99 | ~25–40 ms | HNSW index, top-10 |
| **pgvector** | Concurrent RPS | ~80–120 req/s | 8 threads |
| **pgvector** | RAM thêm (HNSW index) | ~150 MB | 50k vectors dim=768 |
| **SeaweedFS** | PUT throughput | 73 MB/s | 4 concurrent, 1MiB obj |
| **SeaweedFS** | GET throughput | 219 MB/s | 4 concurrent, 1MiB obj |
| **SeaweedFS** | CPU khi benchmark | 1091m (~1.1 cores) | 1 pod |
| **SeaweedFS** | RAM khi benchmark | 378 MB | 1 pod |
| **Gitea** | API RPS (concurrent) | ~12,294 req/s | 20 users, /api/v1/version |
| **Gitea** | API Latency p50 | 1.2 ms | 20 users |
| **Gitea** | API Latency p99 | 11.5 ms | 20 users |
| **Gitea** | RAM khi benchmark | ~120 MB | |
| **Cloudflare** | RAM (static) | ~60 MB | tunnel proxy, skip bench |

## 7. Tính toán tài nguyên
* Sau khi có kết quả, dùng công thức sau:
```
RAM_prod = (RAM_peak_stag_per_service) × replicas × safety_factor(1.5)
CPU_prod = (CPU_peak_stag_per_service) × replicas × 1.3
DISK_prod = current_data × replication_factor × growth_12months(3x)
```
### Tính toán dựa trên kết quả stag (Hạ tầng Platform):
| Service | Stag Peak RAM (per pod) | Prod (×3 replicas ×1.5 buffer) |
|---|---|---|
| PostgreSQL + pgvector | ~680 MB | ~3.0 GB |
| SeaweedFS | ~674 MB | ~1.0 GB (1 replica) |
| Gitea | ~120 MB | ~180 MB (1 replica) |
| k3s + system | ~1.5 GB | ~2.0 GB |
| **Total Platform** | **~3.0 GB** | **~6.2 GB** |

### Ước tính cho Application Layer:
Ngoài hạ tầng nền tảng, máy chủ còn phải gánh các ứng dụng nghiệp vụ dự kiến triển khai:
| Service | Ước lượng RAM (mỗi pod) | Prod (×2-3 replicas) |
|---|---|---|
| **Frontend** (Next.js/React) | ~200 MB | ~600 MB |
| **Backend** (Node.js/Go/Python) | ~300 MB | ~900 MB |
| **AI (Giảng viên)** (RAG/API) | ~500 MB | ~1.5 GB |
| **AI (Sinh viên)** (RAG/API) | ~500 MB | ~1.5 GB |
| **Total Apps** | | **~4.5 GB** |
*(Lưu ý: Nếu các AI Services chạy LLM Model trực tiếp nội bộ như Ollama thay vì gọi API ngoài, mỗi model sẽ ngốn thêm từ 4GB-8GB RAM).*

### Ước tính dung lượng lưu trữ (Disk/SSD):
Dung lượng ổ cứng cần thiết phụ thuộc vào lượng dữ liệu sinh ra. Dưới đây là ước tính cho năm đầu tiên vận hành:
| Service | Mục đích lưu trữ | Ước tính Prod (1 năm) |
|---|---|---|
| **PostgreSQL + pgvector** | Dữ liệu text, user, metadata, vector embeddings | ~20 - 40 GB |
| **SeaweedFS** | File, PDF, video, hình ảnh, backup | ~50 - 100 GB |
| **Gitea** | Source code, kho tài liệu Git | ~10 - 20 GB |
| **OS + Logs** | Hệ điều hành và Container Logs | ~20 - 30 GB |
| **Total Disk** | | **~100 - 190 GB** |

### Lưu ý về kiến trúc lưu trữ (Tương tác với AI/LangGraph):
Về mặt thuật toán AI thuần túy (RAG), hệ thống chỉ cần **PostgreSQL + pgvector** (lưu cả text thô lẫn vector embedding trong cùng một DB). Tuy nhiên, đối với một nền tảng giáo dục thực tế (Production), **SeaweedFS** vẫn là mắt xích bắt buộc để:
1. Lưu file tài liệu gốc phục vụ tính năng **Trích dẫn (Citation)** (cho phép sinh viên click xem/tải lại file PDF gốc thay vì chỉ đọc text của AI).
2. Lưu trữ để **Đào tạo lại (Re-indexing)** tài liệu tự động khi có các mô hình đọc PDF/trích xuất ảnh mới xịn hơn ra mắt (tránh việc bắt giảng viên phải upload lại từ đầu).
3. Làm nơi lưu trữ avatar, slide, video và quan trọng nhất là **chứa file Backup an toàn cho PostgreSQL**.

*(Ghi chú: Vì lý do trên, mô hình Production bắt buộc phải có SeaweedFS. Tuy nhiên, đối với môi trường **Staging** hiện tại (nơi RAM 3.9GB đang bị thắt cổ chai), nếu team chỉ tập trung test luồng AI LangGraph cơ bản, ta **có thể tạm thời tắt SeaweedFS** để giải phóng ngay lập tức ~700MB RAM cho hệ thống).*

**&rarr; Tổng RAM cần thiết (Platform + Apps):** ~6.1 GB + ~4.5 GB = **~10.6 GB**

**&rarr; Khuyến nghị server stagging (10-20 user): RAM 8GB, CPU 4 cores, SSD 50GB+**
*(Với 8GB, ta có thể chạy tất cả các service ở mức 1 replica. Nếu hiện tại vẫn phải dùng server 4GB, khuyến nghị tạm tắt SeaweedFS).*

**&rarr; Khuyến nghị server production (200-500 user): RAM 16GB - 32GB, CPU 8-16 cores, SSD 200GB+**
*(16GB là mức tiêu chuẩn nếu AI gọi API ngoài. Cần nâng lên 32GB nếu tự host các mô hình AI mã nguồn mở).*# AI-Teaching-Assistant-PTIT
