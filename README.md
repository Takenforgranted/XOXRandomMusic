# 晒你纪偶研摊位二偶猜歌小游戏

🎵 这是一个为西电晒你纪偶研摊位设计的猜歌小游戏，基于Python 3.10+开发。玩家需要从播放的歌曲片段中猜出正确的歌曲名称，挑战自己的二偶厨力 or 抽查好厚米的成分！([2025年现场盛况](https://www.bilibili.com/video/BV1VJj5z9ESN?p=3)/[2026年现场盛况](https://www.bilibili.com/video/BV1q5GJ6mEnW))

本项目提供两种运行方式：

- 🖥️ **桌面版**（`game.py` / `game.pyw`）：基于 PyQt5 的本地窗口程序
- 🌐 **网页版**（`web_server.py` + `web\`）：基于 Python 标准库 HTTP 服务的本地网页程序，无需安装 PyQt5，双击 `启动网页游戏.bat` 即可在浏览器中游玩



## 功能特点

- 🎮 完整游戏流程：歌单选择 → 难度选择 → 答题 → 结果显示
- 📁 灵活的歌单管理系统：支持多 IP 分类和子目录管理，歌单可混杂多选
- 🎚️ 三种难度模式：

  - 简单：只使用简单歌单（easy），共 10 道题目，每题 1 分
  - 普通：混合简单和困难歌单（easy + hard），共 8 道题目，每题 1.2 分
  - 困难：只使用困难歌单（hard），共 5 道题目，每题 1.5 分

- 😈 新增**XD 模式**（向死而生）：**正确率低于 50%** 时最终得分**直接斩杀！！！**

- ⌨️ 全键盘操作支持：1/2/3/4 选择选项，Enter 键确认 / 下一题，操作更便捷

- 🎧 实时音频播放功能

- 📊 完善的分数系统：

  - 实时显示当前得分和剩余题目数
  - 答题结束展示最终得分、正确率、答题用时
  - 不同难度对应不同得分（简单 1 分，普通 1.2 分，困难 1.5 分）

- ⏱ 精准计时：记录答题总用时，精确到毫秒

- 🔁 游戏结束后可选择重新开始或退出

- 🌐 **网页版**：除桌面版外，另提供本地网页版（`web_server.py` + `web\`），仅需 Python 标准库即可运行，启动后自动打开浏览器访问 `http://127.0.0.1:8000/`

## 文件说明

| 文件名                 | 描述                                                 |
| ---------------------- | ---------------------------------------------------- |
| `game.py`              | 桌面版主游戏程序（完整版，含日志/崩溃处理/XD模式）   |
| `game.pyw`             | 桌面版启动脚本（PyQt5 无控制台窗口运行）             |
| `web_server.py`        | 网页版后端服务（保留全部游戏逻辑，支持音频流式播放） |
| `web\`                 | 网页版前端（`index.html` / `app.js` / `style.css`）  |
| `启动网页游戏.bat`     | 一键启动网页版并自动打开浏览器                       |
| `tools\clean.py`       | 清理文本中书名号的工具                               |
| `tools\clear_name.py`  | 批量重命名文件的工具（移除文件名前17个字符）         |
| `tools\flac2mp3.py`    | 将FLAC转换为MP3的工具（节省存储空间）                |
| `tools\music_test.py`  | 音乐播放测试脚本                                     |
| `music_num.py`         | 歌单统计脚本（生成歌单统计表）                       |
| `歌单统计表.xlsx`       | 由 `music_num.py` 生成的歌单统计表                   |
| `music`                | 待播放音乐MP3歌单文件夹(度盘下载)                    |

## 运行环境要求

- Python 3.10+
- 桌面版：PyQt5 + PyQt5多媒体组件（用于音频播放）
- 网页版：仅需 Python 标准库（`http.server`），无需额外依赖
- 可选：pydub（用于FLAC转换工具）
- 可选：pandas + openpyxl（用于 `music_num.py` 生成歌单统计表）

## 安装步骤

1. 克隆仓库：
```bash
git clone https://github.com/Takenforgranted/XOXRandomMusic.git
cd XOXRandomMusic
```

2. 创建虚拟环境（可选）：
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate    # Windows
```

3. 安装依赖
桌面版
```bash
pip install PyQt5 PyQt5-Qt5 PyQt5-sip
```
网页版
```bash
pip install waitress
```

4. 运行游戏（任选其一）：

   - 桌面版：
   ```bash
   python game.py
   ```
   - 网页版（启动后自动打开浏览器访问 `http://127.0.0.1:8000/`，关闭窗口即停止服务）：
   ```bash
   python web_server.py
   ```
   或在 Windows 下直接双击 `启动网页游戏.bat` 一键启动网页版。
   
   或在 Linux/macOS 下使用 `bash start.sh` 一键启动网页版（激活虚拟环境+启动服务器）。

## 游戏使用说明

桌面版与网页版的操作流程一致，均支持键盘快捷键 1/2/3/4 选择、Enter 确认/下一题。

1. **选择歌单**：
   
   - 在歌单选择界面，勾选你想要挑战的歌单
   - 支持多级目录选择（IP 分类 → 子目录），IP 分类支持全选 / 部分选择
   - 底部按钮显示已选歌单数量，点击 "开始挑战" 按钮进入下一步
   
2. **选择难度**：
   
   - 简单：只使用简单歌单，共 10 题，每题 1 分
   - 普通：混合简单和困难歌单，共 8 题，每题 1.2 分
   - 困难：只使用困难歌单，共 5 题，每题 1.5 分
   - 可选启用 XD 模式：正确率低于 50% 时最终得分归零
   
3. **开始答题**：
   
   - 游戏会自动播放歌曲片段
   - 从四个选项中选择你认为正确的歌曲名称（支持键盘 1/2/3/4 选择）
   - 点击 "确认" 或按 Enter 键提交答案
   - 答题过程中实时显示剩余题目数、当前得分和用时
   
4. **查看结果**：
   - 完成所有题目后显示最终得分、正确率、答题用时
   - XD 模式下正确率低于 50% 会显示斩杀提示且得分归零
   - 可选择 "重新答题" 或 "关闭窗口"
   

## 工具脚本使用

### 清理文本中的书名号
```bash
python clean.py input.txt [output.txt]
```

### 批量重命名文件（移除前17个字符）
```bash
python clear_name.py target_dir [-r] [-d]
```

### FLAC转MP3（节省存储空间）
```bash
python flac2mp3.py target_dir [-o output_dir] [-b bitrate] [-r] [-d] [-t threads]
```

### 生成歌单统计表（Excel）
```bash
python music_num.py
```
扫描 `music\` 目录下的所有 IP、歌单、easy/hard 歌曲，生成带样式的 `歌单统计表.xlsx`（需安装 pandas 与 openpyxl）。

## 歌曲资源

晒你纪上使用的歌曲已上传到[网盘](https://pan.baidu.com/s/1f8DEFuX7457QLa44Mytlag?pwd=vn7i)，下载后请放在`music/`目录下，按以下结构组织：
```
music/
├── BangDream/
│   ├── 01.Poppin'Party/
│   │   ├── easy/
│   │   └── hard/
│   └── ...（共10个乐队歌单）
├── Girls Band Cry/
│   └── TOGENASHITOGEARI(no easy)/
├── LoveLive/
│   └── 1.μ's & A-Rise/ ... 5.莲之空/ ...（含 4273.合法女声优专区（附+））
├── Revue StarLight/
│   └── 99组/
├── TheIdolMaster/
│   └── 765PRO ALLSTARS/ ... SHINY COLORS/（含 876(hard)、961(hard)、GAKUEN(easy)）
├── 赛马娘/
│   └── ALL/
└── 超级无敌简单歌单/
    └── 只有简单模式/
```

当前 `music\` 目录包含 7 个 IP 分类、27 个歌单，共 1166 首歌曲（约 595 首 easy + 571 首 hard）。

说明：

- 目录结构统一为「IP分类 → 歌单 → easy / hard 子目录」
- 部分歌单仅在文件夹名中标注 `(easy)` / `(hard)` / `(no easy)`，表示只含对应难度的歌曲
- 出题逻辑按路径中是否包含 `easy` / `hard` 自动归类歌曲

## 贡献指南

欢迎提交Issue和Pull Request！

---

🎉 祝你在西电晒你纪玩得开心！记得来偶研摊位挑战一下你的音乐知识哦！（[部分nsy写真](https://pan.baidu.com/s/16JqrUhif_tIqg5qSf8GIYA?pwd=vwcu)）
