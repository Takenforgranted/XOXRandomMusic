# -*- coding: utf-8 -*-
"""
听歌猜名挑战 —— 网页版后端服务（waitress 多线程 WSGI 部署）
============================================================
本文件保留原 game.py 的全部游戏逻辑（歌单扫描 / 难度 / XD模式 / 出题 / 计分 / 计时 / 结果判定），
仅将 PyQt5 界面替换为 web/ 目录下的网页前端，并额外提供音乐文件的 HTTP 流式播放（支持 Range）。

运行方式（任选其一）：
    python web_server.py
    或双击 启动网页游戏.bat

启动后会自动打开浏览器访问 http://127.0.0.1:8000/

部署到服务器（多玩家并发）：
    - 使用 waitress（线程化 WSGI 服务器）承载并发请求，多个玩家可同时答题；
    - 默认监听 0.0.0.0:8000，服务器上的其他玩家通过 http://<服务器IP>:8000/ 访问；
    - 共享状态（全局 XD 开关 / 会话表 / 每个会话的答题进度）均已加锁保护，避免并发读写竞态。

可用环境变量覆盖默认配置：
    XOX_WEB_HOST=0.0.0.0     监听地址（仅本机访问可设为 127.0.0.1）
    XOX_WEB_PORT=8000        端口
    XOX_WEB_THREADS=8        waitress 工作线程数
    XOX_WEB_OPEN_BROWSER=1   是否启动时自动打开浏览器（0 关闭）
"""
import json
import logging
import os
import random
import sys
import threading
import time
import uuid
import webbrowser
from waitress import serve

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MUSIC_ROOT = os.path.join(BASE_DIR, "music")
WEB_DIR = os.path.join(BASE_DIR, "web")
HOST = os.environ.get("XOX_WEB_HOST", "0.0.0.0")  # 服务器部署需监听所有网卡，多玩家才能访问
PORT = int(os.environ.get("XOX_WEB_PORT", "8000"))
THREADS = int(os.environ.get("XOX_WEB_THREADS", "8"))  # waitress 并发工作线程数
MAX_SESSIONS = 64

# Windows 控制台统一使用 UTF-8，避免中文日志乱码
for _stream in (sys.stdout, sys.stderr):
    if _stream and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("xox-web")

# ----------------------------- 全局状态 -----------------------------
global_xd_mode = False          # 对应原 game.py 的 global_xd_mode
_sessions = {}                  # quiz_id -> QuizSession
_session_order = []             # 用于按序清理旧会话
_global_lock = threading.RLock()  # 保护全局状态（xd开关 / 会话表 / 会话清理顺序）

AUDIO_EXT_CONTENT_TYPE = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
}

DIFF_SCORE = {"简单": 1.0, "普通": 1.2, "困难": 1.5}
DIFF_DESIRED = {"简单": 10, "普通": 8, "困难": 5}


def get_song_name(path):
    """从路径中提取歌曲名（不含扩展名），对应 game.py QuizUI.get_song_name"""
    return os.path.splitext(os.path.basename(path))[0]


class QuizSession:
    """一场答题会话，对应原 game.py 中 QuizUI / ResultWindow 的全部状态"""

    def __init__(self, quiz_id, difficulty, xd_mode, easy_range, hard_range,
                 total_questions, adjusted_message=None):
        self.quiz_id = quiz_id
        self.difficulty = difficulty
        self.xd_mode = xd_mode
        self.easy_range = set(easy_range)
        self.hard_range = set(hard_range)
        self.total_questions = total_questions
        self.remaining = total_questions
        self.accumulated_time = 0.0
        self.score = 0.0
        self.correct_count = 0
        self.total_answered = 0
        self.adjusted_message = adjusted_message
        self.question_start_wall = time.time()
        self.current_options = []
        self.current_correct_path = None
        self.correct_name = ""
        self.answered = False
        self.answer_result = None   # {"selected_index","correct_indices","is_correct"}
        self.finished = False
        self.lock = threading.RLock()  # 保护本会话的答题状态，避免并发请求竞态
        self._generate_question()

    # ---------- 出题（对应 game.py QuizUI.load_question） ----------
    def _generate_question(self):
        diff = self.difficulty
        if diff == "简单":
            if len(self.easy_range) < 4:
                raise ValueError(f"简单难度至少需要4首可用歌曲，当前剩余{len(self.easy_range)}首")
            easy_list = list(self.easy_range)
            correct_index = random.randint(0, len(easy_list) - 1)
            correct_song = easy_list[correct_index]
            wrong_list = list(self.easy_range)
            wrong_list.pop(correct_index)
            wrong_list = random.sample(wrong_list, 3)
            self.easy_range = {s for s in self.easy_range if s != correct_song}

        elif diff == "普通":
            easy_list = list(self.easy_range)
            hard_list = list(self.hard_range)
            all_songs = easy_list + hard_list
            if len(all_songs) < 4:
                raise ValueError(f"普通难度至少需要4首可用歌曲，当前剩余{len(all_songs)}首")
            correct_song = random.choice(all_songs)
            wrong_list = random.sample([s for s in all_songs if s != correct_song], 3)
            if correct_song in self.easy_range:
                self.easy_range = {s for s in self.easy_range if s != correct_song}
            else:
                self.hard_range = {s for s in self.hard_range if s != correct_song}

        else:  # 困难
            if len(self.hard_range) < 4:
                raise ValueError(f"困难难度至少需要4首可用歌曲，当前剩余{len(self.hard_range)}首")
            hard_list = list(self.hard_range)
            correct_index = random.randint(0, len(hard_list) - 1)
            correct_song = hard_list[correct_index]
            wrong_list = list(self.hard_range)
            wrong_list.pop(correct_index)
            wrong_list = random.sample(wrong_list, 3)
            self.hard_range = {s for s in self.hard_range if s != correct_song}

        correct_name = get_song_name(correct_song)
        wrong_names = [get_song_name(s) for s in wrong_list]
        options = [correct_name] + wrong_names
        random.shuffle(options)

        self.current_options = options
        self.current_correct_path = correct_song
        self.correct_name = correct_name
        self.question_start_wall = time.time()
        self.answered = False
        self.answer_result = None
        log.info("出题[%s] 剩余=%d/%d 正确歌曲=%s", diff, self.remaining,
                 self.total_questions, os.path.basename(correct_song))

    # ---------- 判定（对应 game.py QuizUI.confirm_answer） ----------
    def confirm(self, selected_index):
        with self.lock:
            if self.answered or self.finished:
                return False
            if not isinstance(selected_index, int) or not (0 <= selected_index < len(self.current_options)):
                return False

            self.answered = True
            self.total_answered += 1
            elapsed = time.time() - self.question_start_wall
            self.accumulated_time += elapsed

            # 与原版一致：同名选项视为正确（可能有多于一个“正确”按钮）
            correct_indices = [i for i, name in enumerate(self.current_options) if name == self.correct_name]
            is_correct = selected_index in correct_indices
            self.answer_result = {
                "selected_index": selected_index,
                "correct_indices": correct_indices,
                "is_correct": is_correct,
            }
            if is_correct:
                self.correct_count += 1
                self.score += DIFF_SCORE.get(self.difficulty, 1.0)
            log.info("答题[%s] 第%d题 选中=%d %s (得分=%.2f 正确=%d/%d)",
                     self.difficulty, self.total_answered, selected_index,
                     "答对" if is_correct else "答错", self.score,
                     self.correct_count, self.total_answered)
            return True

    # ---------- 切题（对应 game.py QuizUI.next_question） ----------
    def advance(self):
        with self.lock:
            if not self.answered:
                return False
            if self.remaining <= 1:
                self.finished = True
                return True
            self.remaining -= 1
            self._generate_question()
            return True

    # ---------- 结果（对应 game.py ResultWindow.initUI 的判定） ----------
    def result(self):
        with self.lock:
            total = self.total_questions
            accuracy = (self.correct_count / total * 100) if total > 0 else 0
            xd_failed = False
            score = self.score
            if self.xd_mode and accuracy < 50:
                xd_failed = True
                score = 0
            minutes = int(self.accumulated_time // 60)
            seconds = int(self.accumulated_time % 60)
            milliseconds = int((self.accumulated_time % 1) * 100)
            time_str = f"{minutes:02d}:{seconds:02d}.{milliseconds:02d}"
            return {
                "xd_mode": self.xd_mode,
                "xd_failed": xd_failed,
                "score": round(score, 2),
                "raw_score": round(self.score, 2),
                "correct_count": self.correct_count,
                "total": total,
                "accuracy": round(accuracy, 1),
                "total_time": round(self.accumulated_time, 3),
                "time_str": time_str,
                "xd_message": (f"XD模式：正确率 {accuracy:.1f}% < 50%，你已被斩杀！"
                               if xd_failed else None),
            }

    # ---------- 当前题目状态（供前端渲染） ----------
    def state(self):
        with self.lock:
            data = {
                "quiz_id": self.quiz_id,
                "options": list(self.current_options),
                "answered": self.answered,
                "remaining": self.remaining,
                "total": self.total_questions,
                "score": round(self.score, 2),
                "correct_count": self.correct_count,
                "total_answered": self.total_answered,
                # 尚未作答时等于累计时间；作答后包含当前题用时（用于冻结计时显示）
                "base_elapsed": round(self.accumulated_time, 3),
                "start_wall": self.question_start_wall,
                "xd_mode": self.xd_mode,
                "difficulty": self.difficulty,
                "finished": self.finished,
                "audio_url": f"/api/game/{self.quiz_id}/audio",
            }
            if self.answered and self.answer_result:
                data["result"] = self.answer_result
            return data


# ----------------------------- 游戏逻辑（对应 game.py 各 UI 的方法） -----------------------------

def list_playlists():
    """列出 music 目录结构（对应 SongSelectionUI.initUI 的目录遍历）"""
    ips = []
    if not os.path.isdir(MUSIC_ROOT):
        return {"ips": [], "music_exists": False}
    for ip in sorted(os.listdir(MUSIC_ROOT)):
        ip_path = os.path.join(MUSIC_ROOT, ip)
        if not os.path.isdir(ip_path):
            continue
        subdirs = []
        for sub in sorted(os.listdir(ip_path)):
            sub_path = os.path.join(ip_path, sub)
            if os.path.isdir(sub_path):
                easy, hard = count_songs(sub_path)
                subdirs.append({"name": sub, "easy": easy, "hard": hard})
        ips.append({"name": ip, "subdirs": subdirs})
    return {"ips": ips, "music_exists": True}


def count_songs(path):
    """统计某个歌单目录下 easy / hard 的音频数量（与出题扫描口径一致）"""
    easy = hard = 0
    for root, _dirs, files in os.walk(path):
        rl = root.lower()
        n = sum(1 for f in files if f.lower().endswith((".mp3", ".wav")))
        if "easy" in rl:
            easy += n
        elif "hard" in rl:
            hard += n
    return easy, hard


def start_game(folders, difficulty, xd_mode):
    """开始一局（对应 DifficultySelectionUI.start_quiz）"""
    global global_xd_mode
    with _global_lock:
        global_xd_mode = bool(xd_mode)

    if not difficulty:
        return {"ok": False, "error": "请选择难度", "message": "请先选择一个难度。"}

    easy_range = set()
    hard_range = set()
    for ip, sub_dir in folders:
        base_path = os.path.join(MUSIC_ROOT, ip, sub_dir)
        if not os.path.isdir(base_path):
            log.warning("歌单目录不存在，已跳过: %s", base_path)
            continue
        for root, _dirs, files in os.walk(base_path):
            for file in files:
                if file.lower().endswith((".mp3", ".wav")):
                    rl = root.lower()
                    if "easy" in rl:
                        easy_range.add(os.path.join(root, file))
                    elif "hard" in rl:
                        hard_range.add(os.path.join(root, file))

    if difficulty == "简单":
        quiz_easy, quiz_hard, desired = easy_range, set(), DIFF_DESIRED["简单"]
    elif difficulty == "困难":
        quiz_easy, quiz_hard, desired = set(), hard_range, DIFF_DESIRED["困难"]
    else:
        quiz_easy, quiz_hard, desired = easy_range, hard_range, DIFF_DESIRED["普通"]

    available_count = len(quiz_easy) + len(quiz_hard)
    max_question_count = max(0, available_count - 3)
    question_count = min(desired, max_question_count)
    log.info("选择难度: %s, easy=%d, hard=%d, 可出题=%d, 实际题数=%d, 已选歌单=%s",
             difficulty, len(quiz_easy), len(quiz_hard), max_question_count,
             question_count, sorted([f"{i}/{s}" for i, s in folders]))

    if question_count <= 0:
        return {"ok": False, "error": "歌曲数量不足",
                "message": f"{difficulty}难度至少需要4首可用歌曲，当前只有{available_count}首。"}

    adjusted = None
    if question_count < desired:
        adjusted = f"当前歌单数量不足以生成{desired}题，本轮将生成{question_count}题。"

    quiz_id = uuid.uuid4().hex[:12]
    session = QuizSession(quiz_id, difficulty, global_xd_mode, quiz_easy, quiz_hard,
                          question_count, adjusted_message=adjusted)
    with _global_lock:
        _sessions[quiz_id] = session
        _session_order.append(quiz_id)
        while len(_session_order) > MAX_SESSIONS:
            old = _session_order.pop(0)
            _sessions.pop(old, None)

    resp = {"ok": True, "quiz_id": quiz_id, "total": question_count,
            "difficulty": difficulty, "xd_mode": global_xd_mode}
    if adjusted:
        resp["message"] = adjusted
    return resp


def get_session(quiz_id):
    with _global_lock:
        return _sessions.get(quiz_id)


# ----------------------------- WSGI 应用 -----------------------------

STATUS_TEXT = {
    200: "200 OK",
    204: "204 No Content",
    404: "404 Not Found",
    405: "405 Method Not Allowed",
    416: "416 Range Not Satisfiable",
    500: "500 Internal Server Error",
}


def _wsgi_json(start_response, data, status=200):
    """以 JSON 响应（等价于原 http.server 的 _send_json）"""
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
    ]
    start_response(STATUS_TEXT.get(status, "200 OK"), headers)
    return [body]


def _wsgi_static(start_response, name, content_type):
    """返回 web/ 下的静态前端文件（等价于原 _serve_static）"""
    file_path = os.path.join(WEB_DIR, name)
    if not os.path.isfile(file_path):
        return _wsgi_json(start_response, {"ok": False, "error": f"缺少前端文件: {name}"}, 404)
    with open(file_path, "rb") as fh:
        body = fh.read()
    start_response("200 OK", [
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
    ])
    return [body]


def _wsgi_read_json(environ):
    """读取并解析请求体 JSON（等价于原 _read_json_body）"""
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        return {}
    if length <= 0:
        return {}
    try:
        return json.loads(environ["wsgi.input"].read(length).decode("utf-8"))
    except Exception:
        return {}


def _wsgi_file_range(environ, start_response, file_path, content_type):
    """流式返回文件，支持 HTTP Range（浏览器音频拖动进度需要）"""
    if not os.path.isfile(file_path):
        body = b"audio file not found"
        start_response("404 Not Found", [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ])
        return [body]

    file_size = os.path.getsize(file_path)
    range_header = environ.get("HTTP_RANGE")
    start, end = 0, file_size - 1
    status = "200 OK"

    if range_header and range_header.startswith("bytes="):
        try:
            spec = range_header[6:].strip()
            if spec.startswith("-"):            # bytes=-N 后缀范围
                start = max(0, file_size - int(spec[1:]))
            else:
                parts = spec.split("-", 1)
                start = int(parts[0])
                if len(parts) > 1 and parts[1].strip():
                    end = min(int(parts[1].strip()), file_size - 1)
            if start > end or start >= file_size:
                start_response("416 Range Not Satisfiable", [
                    ("Content-Range", f"bytes */{file_size}"),
                    ("Content-Length", "0"),
                ])
                return [b""]
            status = "206 Partial Content"
        except (ValueError, IndexError):
            pass

    length = end - start + 1
    headers = [
        ("Content-Type", content_type),
        ("Accept-Ranges", "bytes"),
        ("Content-Length", str(length)),
        ("Cache-Control", "no-store"),
    ]
    if status == "206 Partial Content":
        headers.append(("Content-Range", f"bytes {start}-{end}/{file_size}"))
    start_response(status, headers)

    def stream():
        try:
            with open(file_path, "rb") as fh:
                fh.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = fh.read(min(65536, remaining))
                    if not chunk:
                        break
                    yield chunk
                    remaining -= len(chunk)
        except Exception:
            return

    return stream()


def _wsgi_audio(environ, start_response, session):
    """在会话锁内取当前题音频路径，再流式返回（等价于原 _serve_audio）"""
    with session.lock:
        file_path = session.current_correct_path
    if not file_path or not os.path.isfile(file_path):
        body = b"audio file not found"
        start_response("404 Not Found", [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ])
        return [body]
    ext = os.path.splitext(file_path)[1].lower()
    content_type = AUDIO_EXT_CONTENT_TYPE.get(ext, "application/octet-stream")
    return _wsgi_file_range(environ, start_response, file_path, content_type)


def get_global_state():
    with _global_lock:
        return {"xd_mode": global_xd_mode}


def _handle_get(environ, start_response, path):
    if path in ("/", "/index.html"):
        return _wsgi_static(start_response, "index.html", "text/html; charset=utf-8")
    if path == "/style.css":
        return _wsgi_static(start_response, "style.css", "text/css; charset=utf-8")
    if path == "/app.js":
        return _wsgi_static(start_response, "app.js", "application/javascript; charset=utf-8")
    if path == "/api/playlists":
        return _wsgi_json(start_response, list_playlists())
    if path == "/api/state":
        return _wsgi_json(start_response, get_global_state())
    if path.startswith("/api/game/"):
        parts = path[len("/api/game/"):].split("/")
        if len(parts) != 2:
            return _wsgi_json(start_response, {"ok": False, "error": "未找到"}, 404)
        quiz_id, action = parts
        session = get_session(quiz_id)
        if not session:
            return _wsgi_json(start_response, {"ok": False, "error": "会话不存在或已过期"}, 404)
        if action == "state":
            return _wsgi_json(start_response, session.state())
        if action == "audio":
            return _wsgi_audio(environ, start_response, session)
        if action == "result":
            return _wsgi_json(start_response, session.result())
        return _wsgi_json(start_response, {"ok": False, "error": "未找到"}, 404)
    return _wsgi_json(start_response, {"ok": False, "error": "未找到"}, 404)

def _handle_post(environ, start_response, path):
    body = _wsgi_read_json(environ)
    if path == "/api/game/start":
        folders = body.get("folders") or []
        folders = [[str(f[0]), str(f[1])] for f in folders
                   if isinstance(f, (list, tuple)) and len(f) >= 2]
        difficulty = body.get("difficulty")
        xd_mode = bool(body.get("xd_mode"))
        return _wsgi_json(start_response, start_game(folders, difficulty, xd_mode))
    if path.startswith("/api/game/"):
        parts = path[len("/api/game/"):].split("/")
        if len(parts) != 2:
            return _wsgi_json(start_response, {"ok": False, "error": "未找到"}, 404)
        quiz_id, action = parts
        session = get_session(quiz_id)
        if not session:
            return _wsgi_json(start_response, {"ok": False, "error": "会话不存在或已过期"}, 404)
        if action == "answer":
            index = body.get("index")
            session.confirm(index if isinstance(index, int) else -1)
            return _wsgi_json(start_response, session.state())
        if action == "next":
            session.advance()
            return _wsgi_json(start_response, {"ok": True, "state": session.state()})
        return _wsgi_json(start_response, {"ok": False, "error": "未找到"}, 404)
    return _wsgi_json(start_response, {"ok": False, "error": "未找到"}, 404)


def application(environ, start_response):
    """waitress 调用的 WSGI 入口"""
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "") or "/"
    try:
        if path == "/favicon.ico":
            start_response("204 No Content", [("Content-Length", "0")])
            return [b""]
        if method == "GET":
            return _handle_get(environ, start_response, path)
        if method == "POST":
            return _handle_post(environ, start_response, path)
        body = b"method not allowed"
        start_response("405 Method Not Allowed", [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ])
        return [body]
    except Exception:
        log.exception("请求处理异常: %s %s", method, path)
        return _wsgi_json(start_response, {"ok": False, "error": "服务器内部错误"}, 500)


def find_free_port(host, port, tries=20):
    import socket
    for p in range(port, port + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, p))
                return p
            except OSError:
                continue
    raise OSError(f"端口 {port}~{port + tries - 1} 均被占用")


def main():
    global PORT
    if not os.path.isdir(WEB_DIR):
        print("错误：找不到 web 前端目录，请确认与 web_server.py 位于同一目录。")
        sys.exit(1)
    if not os.path.isdir(MUSIC_ROOT):
        print("警告：找不到 music 目录，请确认音乐文件夹位于本脚本同级目录。")

    PORT = find_free_port(HOST, PORT)
    url = f"http://127.0.0.1:{PORT}/"
    log.info("听歌猜名挑战 · 网页版已启动：%s", url)
    log.info("监听地址: %s:%d（waitress 线程数=%d），按 Ctrl+C 停止服务器", HOST, PORT, THREADS)

    def _open_browser():
        try:
            webbrowser.open(url)
        except Exception:
            pass

    if os.environ.get("XOX_WEB_OPEN_BROWSER", "1") != "0":
        threading.Timer(0.8, _open_browser).start()
    try:
        serve(application, host=HOST, port=PORT, threads=THREADS)
    except KeyboardInterrupt:
        log.info("收到退出信号，正在关闭...")
    finally:
        log.info("服务器已关闭")


if __name__ == "__main__":
    main()
