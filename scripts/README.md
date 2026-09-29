# Scripts

Thư mục này chứa các helper script để chạy / vận hành backend `ops-agent` trên
môi trường server.

## `deamon.sh` — chạy backend dạng daemon service

Script này đóng gói toàn bộ vòng đời của backend LangGraph (`langgraph dev`)
trên một máy Ubuntu: tạo virtualenv, cài dependencies, khởi động nền (daemon),
dừng, restart, xem log. Phù hợp khi bạn muốn chạy thẳng trên server (VM / bare
metal) mà không cần Docker / Kubernetes.

### Yêu cầu

| Hệ thống | Phiên bản |
|----------|-----------|
| OS       | Ubuntu 22.04+ (hoặc mọi Linux có `bash`, `nohup`, `setsid`, `tail`) |
| Python   | ≥ 3.10 (cần `python3` trên `$PATH`) |
| `uv`     | _optional_ — nếu có sẽ được dùng thay cho `pip` (xem bên dưới) |
| `pip`    | _optional_ — chỉ cần khi không có `uv` |

> Script **không chạy** trên Windows (POSIX-only vì dùng `nohup`, `setsid`,
> `kill -0`, …). Trên máy dev Windows vẫn có thể `git pull` script về nhưng hãy
> chạy nó qua WSL / SSH sang máy Ubuntu.

### Cách dùng nhanh

```bash
# 1. Lần đầu tiên trên một máy mới: tạo .venv + cài deps
./scripts/deamon.sh install

# 2. Khởi động backend (chạy nền, detach khỏi terminal)
./scripts/deamon.sh start

# 3. Kiểm tra trạng thái + 20 dòng log cuối
./scripts/deamon.sh status

# 4. Theo dõi log realtime
./scripts/deamon.sh logs

# 5. Dừng (SIGTERM, chờ tối đa 30 giây, fallback SIGKILL)
./scripts/deamon.sh stop

# 6. Restart
./scripts/deamon.sh restart
```

### Các action

| Action   | Mô tả |
|----------|-------|
| `install` | Tạo `.venv/` nếu chưa có, sau đó cài project + dev deps (chứa `langgraph-cli[inmem]`). Idempotent — chạy nhiều lần không sao. |
| `start`   | Chạy `langgraph dev --host 0.0.0.0` nền. Nếu đã chạy thì báo và thoát. Nếu process chết trong vòng 1 giây sau khi start thì dump 50 dòng log cuối để debug. |
| `stop`    | Gửi `SIGTERM`, đợi tối đa 30 giây, nếu vẫn sống thì `SIGKILL`. Xoá PID file. |
| `restart` | `stop` rồi `start`. |
| `status`  | In PID (nếu đang chạy) + 20 dòng log cuối. |
| `logs`    | `tail -f` log file. |

Nếu không truyền action thì mặc định là `status`.

### Files mà script quản lý

Script **tự detect** đường dẫn từ vị trí của nó, nên không cần sửa gì khi copy
repo sang máy khác. Các đường dẫn mặc định (tính tương đối từ thư mục project):

| Đường dẫn | Vai trò |
|-----------|---------|
| `.venv/` | Virtualenv Python. |
| `.run/ops-agent.pid` | PID của process `langgraph dev`. |
| `logs/ops-agent.log` | Toàn bộ stdout + stderr của backend. **Được truncate mỗi lần `start`** — nếu cần giữ log cũ thì copy đi trước khi restart. |
| `.env` | Biến môi trường (do `langgraph.json` chỉ định) — phải tồn tại trước khi `start`. |

Cả `.run/` và `logs/` được `mkdir -p` tự động ở mọi action.

### Cơ chế daemon hóa

Dòng lệnh thực sự khi start:

```bash
nohup setsid langgraph dev --host 0.0.0.0 \
  >> logs/ops-agent.log 2>&1 < /dev/null &
```

- `nohup` — bỏ qua `SIGHUP`, nên khi đóng SSH session backend vẫn chạy.
- `setsid` — tạo session mới, tách hẳn khỏi controlling terminal (kể cả khi bạn
  chạy script từ một `tmux`/`screen` window rồi đóng window đó).
- `< /dev/null` — stdin đóng, không bị treo nếu process thử đọc từ terminal.
- `>> logs/ops-agent.log 2>&1` — gộp stdout + stderr vào log file.

PID lưu ở `.run/ops-agent.pid` là PID của tiến trình `setsid`, đủ để `kill`
và `kill -0` xác định trạng thái.

### Cài đặt deps: `uv` hay `pip`?

`pyproject.toml` định nghĩa một `dependency-groups` (`dev`) chứa
`langgraph-cli[inmem]` — đây mới là package cung cấp lệnh `langgraph`. Vì vậy
`pip install -e .` _không đủ_; phải cài cả `[dev]`.

Script ưu tiên:

1. Nếu có `uv` → `uv venv` + `uv sync --group dev` (nhanh, có lock file resolution).
2. Ngược lại → `python3 -m venv` + `pip install -e ".[dev]"`.

Trên Ubuntu 24.04+ có thể cài `uv` bằng:

```bash
sudo snap install astral-uv
# hoặc
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Troubleshooting

**`./scripts/deamon.sh: Permission denied`**

Script chưa có quyền exec. Chạy một lần:

```bash
chmod +x scripts/deamon.sh
```

**`status` báo "not running" nhưng port vẫn bận**

Có thể PID file trỏ tới process đã chết, hoặc process được start bằng cách
khác (không qua script). Kiểm tra:

```bash
ss -ltnp | grep 2023            # port mặc định của langgraph dev
ps -ef | grep -E 'langgraph|python' | grep -v grep
```

Nếu có process "ma" → `kill <pid>` rồi xoá `.run/ops-agent.pid` cho sạch.

**`start` xong dump log và thoát với lỗi**

Xem nội dung log:

```bash
./scripts/deamon.sh logs      # hoặc
tail -n 200 logs/ops-agent.log
```

Nguyên nhân thường gặp:

| Triệu chứng trong log | Nguyên nhân / cách xử lý |
|----------------------|--------------------------|
| `ModuleNotFoundError: No module named 'langgraph'` | Chưa chạy `install`, hoặc venv bị xoá. Chạy `./scripts/deamon.sh install`. |
| `OSError: [Errno 98] address already in use` | Port 2023 đang bị chiếm (xem mục trên). |
| Lỗi liên quan tới Postgres / checkpoint | Kiểm tra `POSTGRES_URI` (hoặc các biến DB) trong `.env`. |
| `Connection refused` tới Ollama ở `192.168.1.90` | Ollama chưa chạy, hoặc firewall chặn — xem [[project_ops_agent]]. |

**Lỗi `python3: command not found`**

Ubuntu 22.04+ thường có sẵn, nhưng nếu dùng image tối giản:

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
```

**Muốn đổi host / port**

Mặc định là `--host 0.0.0.0` (lắng nghe mọi interface). Nếu cần đổi port, sửa
dòng `nohup setsid langgraph dev …` trong hàm `do_start()` của script; ví dụ:

```bash
nohup setsid langgraph dev --host 0.0.0.0 --port 8000 \
  >> "$LOG_FILE" 2>&1 < /dev/null &
```

### Nâng cấp lên systemd (tuỳ chọn)

Nếu cần auto-start khi reboot, tích hợp `journald`, và quản lý qua
`systemctl`, hãy viết thêm một unit file `/etc/systemd/system/ops-agent.service`
rồi `systemctl enable --now ops-agent`. Lúc đó có thể bỏ dùng `deamon.sh` cho
việc start/stop hàng ngày, chỉ giữ `install` để setup venv. Hỏi nếu cần bản mẫu.