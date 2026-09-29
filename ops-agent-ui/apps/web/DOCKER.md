# Triển khai Next.js UI với Docker

Tài liệu này mô tả cách build và chạy `apps/web` dưới dạng Docker container
thông qua `docker-compose.yml`. Container chạy production server (Next.js
`standalone`) và proxy sang LangGraph backend đang chạy trên host.

## Yêu cầu

| Tool              | Phiên bản                                          |
| ----------------- | -------------------------------------------------- |
| Docker Engine     | ≥ 20.10 (cần cho `host.docker.internal`)           |
| Docker Compose    | v2 (`docker compose`, không phải `docker-compose`) |
| Backend LangGraph | Đang chạy và listen được từ container              |

## Files

```
apps/web/
├── Dockerfile              # multi-stage build (deps → builder → runner)
├── docker-compose.yml      # port 3002:3002, build args + runtime env
├── .dockerignore           # loại node_modules, .next, .git, .env, ...
├── next.config.mjs         # output: "standalone", compress: false, rewrites
└── DOCKER.md               # file này
```

## Build & run

```bash
cd ops-agent-ui/apps/web

# Build image (lần đầu ~2-3 phút, sau đó cache các layer)
docker compose build

# Chạy nền
docker compose up -d

# Xem log
docker compose logs -f

# Dừng + xoá container (giữ image)
docker compose down

# Build lại từ đầu (khi đổi base image, Dockerfile, next.config.mjs)
docker compose build --no-cache
```

Sau khi `up -d`, mở **http://localhost:3002**.

## Cấu hình

### Build-time args (inline vào client bundle)

`docker-compose.yml`:

```yaml
build:
  args:
    NEXT_PUBLIC_API_URL: http://localhost:3002/api/langgraph
    NEXT_PUBLIC_ASSISTANT_ID: agent
```

- `NEXT_PUBLIC_API_URL` — URL browser sẽ gọi. **Phải dùng host public** (`localhost:3002` khi dev local, hoặc domain thật khi deploy prod).
- `NEXT_PUBLIC_ASSISTANT_ID` — graph/assistant ID mặc định (trong `langgraph.json` đang là `agent`).

### Runtime env (server-side, không lộ ra client)

```yaml
environment:
  NODE_ENV: production
  LANGGRAPH_BACKEND_URL: http://host.docker.internal:2024
```

- `LANGGRAPH_BACKEND_URL` — URL Next.js dùng để proxy. Container cần **truy cập được** từ bên trong namespace của nó. Các tuỳ chọn:

  | Backend ở đâu                                 | Giá trị                            |
  | --------------------------------------------- | ---------------------------------- |
  | Trên Docker host (cùng máy với container)     | `http://host.docker.internal:2024` |
  | Máy khác trong LAN                            | `http://192.168.x.x:2024`          |
  | Backend cũng chạy trong Docker (cùng compose) | `http://service-name:2024`         |

> **`host.docker.internal`** chỉ work mặc định trên Docker Desktop (Win/Mac)
> và Linux Docker ≥ 20.10. Nếu Linux cũ hơn, uncomment block `extra_hosts`
> trong `docker-compose.yml`.

## Networking

```
Browser
  │  http://localhost:3002
  ▼
Docker host :3002
  │
  │  docker-proxy (docker-proxy trong engine)
  ▼
Container :3002 (Next.js server)
  │  /api/langgraph/* → rewrite → ${LANGGRAPH_BACKEND_URL}
  ▼
Backend LangGraph (host.docker.internal:2024 hoặc LAN IP)
```

- Browser chỉ thấy `localhost:3002` — không lộ backend.
- Container listen port `3002` (set bằng `ENV PORT=3002` trong Dockerfile).
- Next.js `compress: false` + rewrite trong `next.config.mjs` đảm bảo **SSE stream không bị buffer**.

## Multi-stage build

```
deps      → pnpm install (chỉ apps/web, --ignore-scripts)
builder  → pnpm --filter web build (next build → .next/standalone)
runner   → chỉ copy .next/standalone + static + public vào node:24-alpine
```

Lý do tách 3 stage:

- **Cache reuse**: layer `pnpm install` cache lại — sửa source code không phải install lại.
- **Image nhỏ**: stage `runner` không chứa source code, devDeps, build tools.
- **Security**: stage `runner` không có `pnpm`, `gcc`, `python`, ... → giảm attack surface.

Image cuối thường ~150-200 MB với `node:24-alpine`.

## Troubleshooting

### `host.docker.internal` không resolve được

Triệu chứng: log container báo `fetch failed`, hoặc browser báo `Failed to connect to LangGraph server`.

Fix:

1. **Linux Docker < 20.10** — uncomment block `extra_hosts` trong `docker-compose.yml`:

   ```yaml
   extra_hosts:
     - "host.docker.internal:host-gateway"
   ```

   Rồi `docker compose up -d --force-recreate`.

2. **Backend không trên cùng máy** — đổi `LANGGRAPH_BACKEND_URL` sang IP LAN:

   ```yaml
   LANGGRAPH_BACKEND_URL: http://192.168.1.111:2024
   ```

3. **Backend cũng trong Docker** — dùng service name:
   ```yaml
   LANGGRAPH_BACKEND_URL: http://langgraph-backend:2024
   ```

### Port `3002` đã bị chiếm

Triệu chứng: `docker compose up` fail với `bind: address already in use`.

```bash
# Tìm process đang dùng port 3002
ss -ltnp | grep 3002       # Linux
netstat -ano | findstr 3002 # Windows

# Hoặc đổi port trong docker-compose.yml
ports:
  - "3003:3002"            # host:3003 → container:3002
```

Nếu đổi host port, **cũng phải đổi `NEXT_PUBLIC_API_URL`** ở build args cho khớp, rồi rebuild:

```yaml
args:
  NEXT_PUBLIC_API_URL: http://localhost:3003/api/langgraph
```

### Streaming bị đứng (chờ hết rồi trả 1 phát)

Nguyên nhân thường gặp:

1. **Backend không thực sự stream** — test trực tiếp:

   ```bash
   curl -N http://localhost:2024/threads/<id>/runs/stream \
     -H "Content-Type: application/json" \
     -d '{"assistant_id":"agent","input":{},"stream_mode":"values"}'
   ```

   Nếu curl cũng bị "đợi hết" → vấn đề ở backend, không phải container.

2. **Frontend dev override** — đảm bảo `NEXT_PUBLIC_API_URL` **không trỏ thẳng** về `localhost:2024`. Phải qua proxy `/api/langgraph`.

3. **`compress: false`** bị xoá khỏi `next.config.mjs` — cần thiết để Next.js không gzip-buffer response.

### Container restart liên tục

Xem log:

```bash
docker compose logs --tail=100 web
```

Nguyên nhân thường gặp:

| Log                                     | Nguyên nhân                                         |
| --------------------------------------- | --------------------------------------------------- |
| `Cannot find module 'next'`             | Build fail — check `docker compose build` output    |
| `EADDRINUSE :::3002`                    | Có thứ khác trong container đã chiếm port (hiếm)    |
| `Error: connect ECONNREFUSED ... :2024` | Backend chưa chạy, hoặc `LANGGRAPH_BACKEND_URL` sai |

### Build fail: prebuilt binary không có cho Node 24

Triệu chứng: `Could not find any Python or prebuilt binary` hoặc tương tự trong `pnpm install`.

Fix nhanh — đổi base image sang Node 22 LTS (hầu hết prebuilt đều có):

```diff
- ARG NODE_VERSION=24-alpine
+ ARG NODE_VERSION=22-alpine
```

Sau đó `docker compose build --no-cache`.

## Sau khi sửa

| Sửa gì                            | Cần rebuild?                                        |
| --------------------------------- | --------------------------------------------------- |
| Source `.tsx` / `.ts` / `.css`    | ✅ `docker compose up -d --build`                   |
| `package.json` / `pnpm-lock.yaml` | ✅ `docker compose build --no-cache`                |
| `next.config.mjs`                 | ✅ `docker compose build --no-cache`                |
| `Dockerfile`                      | ✅ `docker compose build --no-cache`                |
| `docker-compose.yml` (env, ports) | ❌ Chỉ cần `docker compose up -d --force-recreate`  |
| Backend code (LangGraph)          | ❌ Chỉ restart backend, container không cần rebuild |

## Production checklist (khi deploy thật)

- [ ] Đổi `NEXT_PUBLIC_API_URL` sang domain thật (vd `https://chat.example.com/api/langgraph`)
- [ ] Đổi `LANGGRAPH_BACKEND_URL` sang URL backend nội bộ
- [ ] Bật HTTPS (terminate ở nginx/Caddy trước container, hoặc đổi port mapping)
- [ ] Không publish port 3002 ra public — để reverse proxy xử lý
- [ ] Bật log driver (`json-file` với rotation, hoặc gửi về Loki/CloudWatch)
- [ ] Set `restart: always` (đang là `unless-stopped`)
- [ ] Bật resource limit (`mem_limit`, `cpus`) nếu chạy nhiều container trên 1 host
