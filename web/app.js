/* ==========================================================================
   听歌猜名挑战 · 网页版前端逻辑
   对应原 game.py 的 SongSelectionUI / DifficultySelectionUI / QuizUI / ResultWindow
   ========================================================================== */
"use strict";

/* ---------------- 全局状态 ---------------- */
let playlistData = null;            // /api/playlists 返回的数据
let selectedFolders = [];           // 已选中的 [ip, sub] 列表
let currentQuizId = null;           // 当前会话 id（存 sessionStorage 以便刷新恢复）
let currentState = null;            // 最近一次 /state 返回
let timerInterval = null;           // 计时器句柄
let answeredSelection = -1;         // 当前题选中的选项下标（-1 = 未选）
let audioLoadedThisQuestion = false;

const audio = document.getElementById("audio-player");

/* ---------------- 工具函数 ---------------- */
const $ = (id) => document.getElementById(id);

async function fetchJSON(url, options) {
    const resp = await fetch(url, options);
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    return resp.json();
}

/* ---------------- 视图切换 ---------------- */
function showView(name) {
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    $("view-" + name).classList.add("active");
    window.scrollTo(0, 0);
}

/* ---------------- 模态框（模拟 QMessageBox） ---------------- */
let modalResolve = null;
function showModal(title, message) {
    return new Promise((resolve) => {
        $("modal-title").textContent = title;
        $("modal-message").textContent = message || "";
        $("modal-overlay").classList.remove("hidden");
        modalResolve = resolve;
    });
}
function closeModal() {
    $("modal-overlay").classList.add("hidden");
    if (modalResolve) { modalResolve(); modalResolve = null; }
}
$("modal-ok").addEventListener("click", closeModal);
$("modal-overlay").addEventListener("click", (e) => {
    if (e.target === $("modal-overlay")) closeModal();
});

/* ==========================================================================
   一、选择歌单（对应 SongSelectionUI）
   ========================================================================== */
async function loadPlaylists() {
    try {
        playlistData = await fetchJSON("/api/playlists");
    } catch (e) {
        showModal("无法连接服务器", "请确认网页版后端已启动（运行 web_server.py）。\n" + e.message);
        return;
    }
    renderPlaylists();
}

function renderPlaylists() {
    const scroll = $("playlist-scroll");
    scroll.innerHTML = "";

    if (!playlistData.music_exists || playlistData.ips.length === 0) {
        const empty = document.createElement("div");
        empty.className = "empty-tip";
        empty.textContent = "未找到任何歌单目录，请确认 music 文件夹位于程序同级目录。";
        scroll.appendChild(empty);
        updateStartButton();
        return;
    }

    for (const ip of playlistData.ips) {
        const box = document.createElement("div");
        box.className = "ip-box";

        const header = document.createElement("div");
        header.className = "ip-header";

        const parentChk = document.createElement("input");
        parentChk.type = "checkbox";
        parentChk.dataset.ip = ip.name;
        parentChk.addEventListener("change", () => {
            toggleIp(ip.name, parentChk.checked);
        });

        const name = document.createElement("span");
        name.className = "ip-name";
        name.textContent = ip.name;

        header.appendChild(parentChk);
        header.appendChild(name);
        header.addEventListener("click", (e) => {
            if (e.target !== parentChk) parentChk.click();
        });

        box.appendChild(header);

        const subList = document.createElement("div");
        subList.className = "sub-list";
        for (const sub of ip.subdirs) {
            const item = document.createElement("label");
            item.className = "sub-item";

            const chk = document.createElement("input");
            chk.type = "checkbox";
            chk.dataset.ip = ip.name;
            chk.dataset.sub = sub.name;
            chk.addEventListener("change", () => {
                if (!chk.dataset.guard) updateParentState(ip.name);
                updateStartButton();
            });

            const subName = document.createElement("span");
            subName.textContent = sub.name;

            const count = document.createElement("span");
            count.className = "sub-count";
            count.textContent = `(简单 ${sub.easy} / 困难 ${sub.hard})`;

            item.appendChild(chk);
            item.appendChild(subName);
            item.appendChild(count);
            subList.appendChild(item);
        }

        box.appendChild(subList);
        scroll.appendChild(box);
    }

    updateStartButton();
}

/* 切换父级（IP）勾选状态：全选/全不选其子歌单 */
function toggleIp(ipName, checked) {
    const subList = document.querySelector(`.ip-box .ip-header input[data-ip="${CSS.escape(ipName)}"]`)
        .closest(".ip-box").querySelector(".sub-list");
    const chks = subList.querySelectorAll('input[type="checkbox"]');
    chks.forEach((c) => {
        c.dataset.guard = "1";
        c.checked = checked;
        delete c.dataset.guard;
    });
    updateStartButton();
}

/* 根据子歌单状态更新父级：全选=勾选，全不选=取消，部分=半选（indeterminate） */
function updateParentState(ipName) {
    const box = document.querySelector(`.ip-box .ip-header input[data-ip="${CSS.escape(ipName)}"]`)
        .closest(".ip-box");
    const chks = box.querySelectorAll('.sub-list input[type="checkbox"]');
    const parentChk = box.querySelector('.ip-header input[type="checkbox"]');
    const checked = [...chks].filter((c) => c.checked).length;
    parentChk.checked = checked === chks.length && chks.length > 0;
    parentChk.indeterminate = checked > 0 && checked < chks.length;
}

/* 汇总已选歌单，更新开始按钮计数 */
function updateStartButton() {
    const chks = document.querySelectorAll('#playlist-scroll .sub-list input[type="checkbox"]:checked');
    selectedFolders = [...chks].map((c) => [c.dataset.ip, c.dataset.sub]);
    const n = selectedFolders.length;
    const btn = $("btn-start");
    btn.disabled = n === 0;
    btn.textContent = `开始挑战 (${n})`;
}

$("btn-start").addEventListener("click", () => {
    if (selectedFolders.length === 0) return;
    // 读取上次保存的 XD 状态，并显示难度选择
    loadXDMode().then(() => {
        // 默认选中第一个难度
        const firstRadio = document.querySelector('input[name="difficulty"]');
        if (firstRadio && !document.querySelector('input[name="difficulty"]:checked')) {
            firstRadio.checked = true;
        }
        showView("difficulty");
    });
});

/* ==========================================================================
   二、选择难度（对应 DifficultySelectionUI）
   ========================================================================== */
async function loadXDMode() {
    try {
        const data = await fetchJSON("/api/state");
        $("xd-checkbox").checked = !!data.xd_mode;
    } catch (e) {
        $("xd-checkbox").checked = false;
    }
}

$("btn-confirm-difficulty").addEventListener("click", async () => {
    const difficulty = document.querySelector('input[name="difficulty"]:checked');
    if (!difficulty) {
        showModal("提示", "请先选择一个难度。");
        return;
    }
    const xdMode = $("xd-checkbox").checked;

    const payload = {
        folders: selectedFolders,
        difficulty: difficulty.value,
        xd_mode: xdMode,
    };

    $("btn-confirm-difficulty").disabled = true;
    try {
        const resp = await fetchJSON("/api/game/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (!resp.ok) {
            await showModal("无法开始挑战", resp.message || resp.error || "未知错误");
            return;
        }

        if (resp.message) {
            await showModal("提示", resp.message);
        }

        currentQuizId = resp.quiz_id;
        sessionStorage.setItem("xox_quiz_id", resp.quiz_id);
        currentState = null;
        enterQuiz();
    } catch (e) {
        showModal("错误", "请求失败：" + e.message);
    } finally {
        $("btn-confirm-difficulty").disabled = false;
    }
});

/* ==========================================================================
   三、答题（对应 QuizUI）
   ========================================================================== */
async function enterQuiz() {
    showView("quiz");
    await refreshState();
    bindAudio();
}

/* 拉取最新状态并渲染 */
async function refreshState() {
    if (!currentQuizId) return;
    try {
        const data = await fetchJSON(`/api/game/${currentQuizId}/state`);
        currentState = data;
        renderQuiz(data);
    } catch (e) {
        showModal("会话已过期", "本局会话已失效，请返回重新开始。\n" + e.message);
    }
}

function renderQuiz(state) {
    // 难度 / XD 提示
    const xdWarn = $("xd-warning");
    if (state.xd_mode) {
        xdWarn.classList.remove("hidden");
        xdWarn.textContent = `⚠️ XD模式：正确率低于50%时得分将归零！（当前难度：${state.difficulty}）`;
    } else {
        xdWarn.classList.add("hidden");
    }

    // 顶部信息
    $("quiz-remaining").textContent = `剩余题目: ${state.remaining}/${state.total}`;
    $("quiz-score").textContent = `当前得分: ${state.score.toFixed(1)}`;

    // 选项渲染
    const optionsBox = $("quiz-options");
    optionsBox.innerHTML = "";
    answeredSelection = state.answered ? (state.result ? state.result.selected_index : -1) : -1;

    state.options.forEach((opt, idx) => {
        const row = document.createElement("div");
        row.className = "option-row";

        const num = document.createElement("span");
        num.className = "num-label";
        num.textContent = `[${idx + 1}]`;

        const btn = document.createElement("button");
        btn.className = "option-btn";
        btn.type = "button";
        btn.textContent = opt;
        btn.dataset.index = idx;
        btn.addEventListener("click", () => {
            if (currentState && currentState.answered) return;
            selectOption(idx);
        });

        row.appendChild(num);
        row.appendChild(btn);
        optionsBox.appendChild(row);
    });

    if (state.answered) {
        applyAnswerVisual(state);
    }

    // 确认按钮
    const confirmBtn = $("btn-confirm-answer");
    if (state.answered) {
        confirmBtn.disabled = false;
        confirmBtn.textContent = state.remaining <= 1 ? "查看结果 (Enter)" : "下一题 (Enter)";
        if (state.remaining > 1) confirmBtn.classList.add("next-mode");
    } else {
        confirmBtn.disabled = true;
        confirmBtn.textContent = "确认 (Enter)";
        confirmBtn.classList.remove("next-mode");
    }

    // 音频
    audioLoadedThisQuestion = false;
    const src = state.audio_url + "?t=" + Date.now();
    if (audio.src !== src) audio.src = src;
    stopTimer();
    startTimer();

    // 新题加载后 500ms 播放正确歌曲（对应原版 QTimer.singleShot(500, ...)）
    if (!state.answered && !state.finished) {
        playCurrentSongDelayed();
    }
}

/* 选中某个选项（答题前高亮） */
function selectOption(idx) {
    if (currentState && currentState.answered) return;
    answeredSelection = idx;
    const nums = document.querySelectorAll("#quiz-options .num-label");
    nums.forEach((n, i) => {
        n.classList.toggle("selected", i === idx);
    });
    const btns = document.querySelectorAll("#quiz-options .option-btn");
    btns.forEach((b, i) => {
        b.classList.toggle("selected", i === idx);
    });
    $("btn-confirm-answer").disabled = false;
}

/* 提交答案 */
async function submitAnswer() {
    if (!currentState || currentState.answered || answeredSelection < 0) return;
    $("btn-confirm-answer").disabled = true;
    try {
        const data = await fetchJSON(`/api/game/${currentQuizId}/answer`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ index: answeredSelection }),
        });
        currentState = data;
        stopTimer();
        // 作答后冻结计时显示为服务器累计值
        $("quiz-timer").textContent = formatTime(data.base_elapsed);
        applyAnswerVisual(data);
        $("btn-confirm-answer").disabled = false;
        $("btn-confirm-answer").textContent = data.remaining <= 1 ? "查看结果 (Enter)" : "下一题 (Enter)";
        audio.pause();
    } catch (e) {
        showModal("错误", "提交答案失败：" + e.message);
        $("btn-confirm-answer").disabled = false;
    }
}

/* 答题后高亮：正确=绿，错误=红（与原版一致，同名选项都标绿） */
function applyAnswerVisual(state) {
    const result = state.result;
    if (!result) return;
    const nums = document.querySelectorAll("#quiz-options .num-label");
    const btns = document.querySelectorAll("#quiz-options .option-btn");
    state.options.forEach((_, i) => {
        if (result.correct_indices.includes(i)) {
            nums[i].classList.add("correct");
            btns[i].classList.add("correct");
        } else if (i === result.selected_index) {
            nums[i].classList.add("wrong");
            btns[i].classList.add("wrong");
        }
    });
}

/* 下一题 / 查看结果 */
async function nextQuestion() {
    if (!currentState || !currentState.answered) return;
    $("btn-confirm-answer").disabled = true;
    try {
        const data = await fetchJSON(`/api/game/${currentQuizId}/next`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: "{}",
        });
        currentState = data.state;
        if (currentState.finished) {
            stopTimer();
            sessionStorage.removeItem("xox_quiz_id");
            await showResult();
        } else {
            renderQuiz(currentState);
        }
    } catch (e) {
        showModal("错误", "切换题目失败：" + e.message);
        $("btn-confirm-answer").disabled = false;
    }
}

$("btn-confirm-answer").addEventListener("click", () => {
    if (!currentState) return;
    if (currentState.answered) nextQuestion();
    else submitAnswer();
});

/* 退出本局（放弃） */
$("btn-quit").addEventListener("click", async () => {
    await showModal("退出挑战", "确定要退出本局并返回歌单选择吗？\n本局进度将不会保存。");
    currentQuizId = null;
    sessionStorage.removeItem("xox_quiz_id");
    stopTimer();
    audio.pause();
    audio.removeAttribute("src");
    loadPlaylists();
    showView("playlists");
});

/* ---------------- 计时器（对应原版 100ms 刷新） ---------------- */
function startTimer() {
    stopTimer();
    const base = currentState ? currentState.base_elapsed : 0;
    const startWall = currentState ? currentState.start_wall : Date.now() / 1000;
    const update = () => {
        if (currentState && currentState.answered) {
            $("quiz-timer").textContent = formatTime(currentState.base_elapsed);
            return;
        }
        const elapsed = base + (Date.now() / 1000 - startWall);
        $("quiz-timer").textContent = formatTime(elapsed);
    };
    update();
    timerInterval = setInterval(update, 100);
}
function stopTimer() {
    if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
}

/* 与后端同款 MM:SS.cc 格式 */
function formatTime(seconds) {
    if (typeof seconds !== "number" || isNaN(seconds)) seconds = 0;
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    const cs = Math.floor((seconds % 1) * 100);
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(cs).padStart(2, "0")}`;
}

/* ---------------- 音频播放（对应原版 500ms 后自动播放） ---------------- */
function bindAudio() {
    // 浏览器自动播放策略可能拦截，需要用户先与页面交互一次
    if (!audio.dataset.bound) {
        audio.dataset.bound = "1";
        audio.addEventListener("canplaythrough", tryAutoPlay);
        document.addEventListener("click", () => {
            if (audioLoadedThisQuestion && audio.paused && currentState && !currentState.answered) {
                const p = audio.play();
                if (p) p.catch(() => {});
            }
        });
    }
}

function tryAutoPlay() {
    if (!audioLoadedThisQuestion) return;
    const p = audio.play();
    if (p) {
        p.catch(() => {
            showPlayHint();
        });
    }
}

function showPlayHint() {
    const hint = $("play-hint");
    hint.classList.remove("hidden");
    hint.textContent = "🔇 浏览器拦截了自动播放，请点击「🔁 重听」播放本曲";
}

$("btn-play-toggle").addEventListener("click", () => {
    if (audio.paused) {
        audio.play().catch(() => showPlayHint());
    } else {
        audio.pause();
    }
});

$("btn-replay").addEventListener("click", () => {
    $("play-hint").classList.add("hidden");
    audio.currentTime = 0;
    audio.play().catch(() => showPlayHint());
});

audio.addEventListener("play", () => {
    $("play-hint").classList.add("hidden");
    $("btn-play-toggle").textContent = "⏸ 暂停";
});
audio.addEventListener("pause", () => {
    $("btn-play-toggle").textContent = "▶ 播放";
});

/* 新题加载后 500ms 播放正确歌曲（对应原版 QTimer.singleShot(500, ...)） */
function playCurrentSongDelayed() {
    if (!currentState) return;
    audioLoadedThisQuestion = true;
    $("play-hint").classList.add("hidden");
    setTimeout(() => {
        if (currentState && !currentState.answered) {
            const p = audio.play();
            if (p) p.catch(() => showPlayHint());
        }
    }, 500);
}

/* ---------------- 键盘快捷键（对应原版 1/2/3/4 + Enter） ---------------- */
document.addEventListener("keydown", (e) => {
    if (!currentQuizId) return;
    if (document.activeElement && document.activeElement.tagName === "INPUT") return;
    const activeView = document.querySelector(".view.active");
    if (activeView && activeView.id !== "view-quiz") return;
    if (!$("modal-overlay").classList.contains("hidden")) return;

    if (e.key === "Enter") {
        e.preventDefault();
        $("btn-confirm-answer").click();
        return;
    }
    if (/^[1-4]$/.test(e.key)) {
        const idx = parseInt(e.key, 10) - 1;
        if (currentState && currentState.answered) return;
        if (currentState && idx < currentState.options.length) {
            selectOption(idx);
        }
    }
});

/* ==========================================================================
   四、结果页（对应 ResultWindow）
   ========================================================================== */
async function showResult() {
    if (!currentQuizId) return;
    try {
        const r = await fetchJSON(`/api/game/${currentQuizId}/result`);
        const content = $("result-content");
        content.innerHTML = "";

        const title = document.createElement("div");
        title.className = "result-title";
        title.textContent = "挑战结束！";
        content.appendChild(title);

        if (r.xd_mode) {
            const xdLabel = document.createElement("div");
            xdLabel.className = "result-xd-label";
            xdLabel.textContent = "😈 XD模式挑战";
            content.appendChild(xdLabel);
        }

        const scoreBox = document.createElement("div");
        if (r.xd_failed) {
            scoreBox.className = "result-score-fail";
            scoreBox.textContent = `最终得分：${r.score.toFixed(1)}`;
        } else {
            scoreBox.className = "result-score-ok";
            scoreBox.textContent = `最终得分：${r.score.toFixed(1)}`;
        }
        content.appendChild(scoreBox);

        if (r.xd_failed) {
            const fail = document.createElement("div");
            fail.className = "result-xd-fail";
            fail.textContent = `❌ ${r.xd_message}（原始得分 ${r.raw_score.toFixed(1)}）`;
            content.appendChild(fail);
        }

        const accuracy = document.createElement("div");
        accuracy.className = "result-accuracy";
        accuracy.textContent = `正确率：${r.correct_count}/${r.total} (${r.accuracy}%)`;
        content.appendChild(accuracy);

        const time = document.createElement("div");
        time.className = "result-time";
        time.textContent = `⏱ 答题用时：${r.time_str}`;
        content.appendChild(time);

        const divider = document.createElement("hr");
        divider.className = "result-divider";
        content.appendChild(divider);

        const btnRow = document.createElement("div");
        btnRow.className = "footer-bar";

        const again = document.createElement("button");
        again.className = "primary-btn";
        again.textContent = "重新答题";
        again.addEventListener("click", () => {
            // 回到歌单选择重新开始
            currentQuizId = null;
            sessionStorage.removeItem("xox_quiz_id");
            loadPlaylists();
            showView("playlists");
        });
        btnRow.appendChild(again);

        const close = document.createElement("button");
        close.className = "primary-btn";
        close.style.background = "#78909C";
        close.addEventListener("mouseenter", () => { close.style.background = "#607D8B"; });
        close.addEventListener("mouseleave", () => { close.style.background = "#78909C"; });
        close.textContent = "关闭窗口";
        close.addEventListener("click", () => {
            currentQuizId = null;
            sessionStorage.removeItem("xox_quiz_id");
            loadPlaylists();
            showView("playlists");
        });
        btnRow.appendChild(close);

        content.appendChild(btnRow);

        showView("result");
    } catch (e) {
        showModal("错误", "获取结果失败：" + e.message);
    }
}

/* ==========================================================================
   启动：刷新恢复 / 初始化
   ========================================================================== */
async function init() {
    await loadPlaylists();

    const savedId = sessionStorage.getItem("xox_quiz_id");
    if (savedId) {
        // 尝试恢复被中断的会话
        try {
            const data = await fetchJSON(`/api/game/${savedId}/state`);
            if (data && !data.finished) {
                currentQuizId = savedId;
                currentState = data;
                enterQuiz();
                return;
            }
            sessionStorage.removeItem("xox_quiz_id");
        } catch (e) {
            sessionStorage.removeItem("xox_quiz_id");
        }
    }

    showView("playlists");
}

init();
