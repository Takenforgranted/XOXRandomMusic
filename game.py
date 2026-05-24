from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QCheckBox, QPushButton, QScrollArea, QHBoxLayout,
                             QLabel, QFrame, QRadioButton, QGridLayout, QButtonGroup, QMessageBox)
from PyQt5.QtCore import Qt, QTimer, QUrl, QTime
from PyQt5.QtGui import QKeyEvent

import os
import subprocess
import logging
import faulthandler
import atexit
import signal
import random
import sys
import time

os.environ["QT_MULTIMEDIA_PREFERRED_PLUGINS"] = "ffmpeg"

global_score = 0.0
global_start_time = 0
global_xd_mode = False
global_correct_count = 0
global_total_answered = 0

LOG_ENABLED = 1
LOG_OUTPUT_MODE = 1  # 0 = log to file only, 1 = log to console only
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game.log")
_fault_log = None


def setup_logging():
    global _fault_log

    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    if not LOG_ENABLED:
        root_logger.setLevel(logging.CRITICAL + 1)
        root_logger.addHandler(logging.NullHandler())
        return

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    if LOG_OUTPUT_MODE == 1:
        handler = logging.StreamHandler(sys.stderr)
        fault_output = sys.stderr
    else:
        handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        _fault_log = open(LOG_FILE, "a", encoding="utf-8")
        fault_output = _fault_log

    handler.setFormatter(formatter)
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    faulthandler.enable(file=fault_output, all_threads=True)


def log_destination_text():
    if not LOG_ENABLED:
        return "日志当前已关闭"
    if LOG_OUTPUT_MODE == 1:
        return "错误详情已输出到终端"
    return f"错误详情已写入日志：\n{LOG_FILE}"


setup_logging()


def log_unhandled_exception(exc_type, exc_value, exc_traceback):
    logging.critical(
        "未捕获异常",
        exc_info=(exc_type, exc_value, exc_traceback)
    )
    if QApplication.instance():
        QMessageBox.critical(
            None,
            "程序错误",
            f"程序遇到错误，{log_destination_text()}\n\n{exc_value}"
        )


sys.excepthook = log_unhandled_exception

_active_windows = []
_music_players = []
_is_switching_window = False


def keep_window(window):
    if window not in _active_windows:
        _active_windows.append(window)
    logging.info("保留窗口引用: %s, active=%d", window.__class__.__name__, len(_active_windows))


def release_window(window):
    try:
        _active_windows.remove(window)
        logging.info("释放窗口引用: %s, active=%d", window.__class__.__name__, len(_active_windows))
    except ValueError:
        pass


def switch_window(next_window, previous_window=None):
    global _is_switching_window

    keep_window(next_window)
    if previous_window:
        _is_switching_window = True
        try:
            previous_window.close()
            release_window(previous_window)
        finally:
            _is_switching_window = False

    next_window._ignore_unexpected_close_until = time.monotonic() + 0.8
    next_window.show()
    next_window.raise_()
    next_window.activateWindow()
    logging.info("显示窗口: %s, active=%d", next_window.__class__.__name__, len(_active_windows))


def ignore_unexpected_close(window, event):
    ignore_until = getattr(window, "_ignore_unexpected_close_until", 0)
    if not _is_switching_window and time.monotonic() < ignore_until:
        logging.info("忽略窗口刚显示后的异常关闭请求: %s", window.__class__.__name__)
        event.ignore()
        window.show()
        window.raise_()
        window.activateWindow()
        return True
    return False


def quit_application():
    logging.info("用户请求退出应用")
    stop_all_music_players()
    app = QApplication.instance()
    if app:
        app.quit()


OPTION_BUTTON_STYLE = """
    QPushButton {
        font-size: 18px;
        padding: 15px;
        border-radius: 8px;
        background: #f0f0f0;
        border: 2px solid #ccc;
    }
    QPushButton:hover {
        background: #e0e0e0;
        border: 2px solid #aaa;
    }
    QPushButton:checked {
        background: #d0e8f2;
        border: 2px solid #79a3b1;
    }
"""

OPTION_LABEL_STYLE = """
    font-size: 16px;
    font-weight: bold;
    color: #666;
    background: #e0e0e0;
    padding: 5px 10px;
    border-radius: 4px;
    min-width: 30px;
"""


class MusicPlayer:
    def __init__(self, volume=100):
        self.volume = volume
        self.process = None
        self.qt_player = None
        self.closed = False
        _music_players.append(self)
        if sys.platform != "darwin":
            self.qt_player = QMediaPlayer()
            self.qt_player.setVolume(volume)

    def play(self, path):
        if self.closed:
            logging.info("忽略已关闭播放器的播放请求: %s", path)
            return

        self.stop()
        absolute_path = os.path.abspath(path)
        logging.info("播放音乐: %s", absolute_path)
        if sys.platform == "darwin":
            volume = max(0.0, min(self.volume / 100.0, 1.0))
            self.process = subprocess.Popen(
                ["afplay", "-v", str(volume), absolute_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            return

        media_content = QMediaContent(QUrl.fromLocalFile(absolute_path))
        self.qt_player.setMedia(media_content)
        self.qt_player.play()

    def stop(self):
        if self.process:
            process = self.process
            self.process = None
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            except ProcessLookupError:
                pass

        if self.qt_player:
            self.qt_player.stop()

    def close(self):
        self.closed = True
        self.stop()
        try:
            _music_players.remove(self)
        except ValueError:
            pass

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


def stop_all_music_players():
    for player in list(_music_players):
        player.close()


atexit.register(stop_all_music_players)


class ResultWindow(QMainWindow):
    def __init__(self, total_time_seconds, total_questions):
        super().__init__()
        self.total_time = total_time_seconds
        self.total_questions = total_questions
        self.is_restarting = False
        self.initUI()

    def initUI(self):
        global global_score, global_correct_count, global_xd_mode

        self.setWindowTitle("答题结果")
        self.setGeometry(400, 400, 400, 350)
        self.setCentralWidget(QWidget())

        layout = QVBoxLayout(self.centralWidget())
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(15)

        if global_xd_mode:
            xd_label = QLabel("😈 XD模式已启用", self)
            xd_label.setStyleSheet("font-size: 14px; color: #d32f2f; font-weight: bold;")
            xd_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(xd_label)

        title_label = QLabel("🎉 答题结束！", self)
        title_label.setStyleSheet("font-size: 26px; font-weight: bold; color: #333;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        accuracy = (global_correct_count / self.total_questions * 100) if self.total_questions > 0 else 0
        xd_failed = False
        if global_xd_mode and accuracy < 50:
            xd_failed = True
            global_score = 0

        rounded_score = round(global_score, 2)

        if xd_failed:
            self.score_label = QLabel(f"❌ 最终得分：{rounded_score} 分", self)
            self.score_label.setStyleSheet("font-size: 22px; color: #d32f2f; font-weight: bold;")
            xd_fail_label = QLabel(f"XD模式：正确率 {accuracy:.1f}% < 50%，你已被斩杀！", self)
            xd_fail_label.setStyleSheet("font-size: 14px; color: #d32f2f; font-weight: bold; background: #ffebee; padding: 8px; border-radius: 4px;")
            xd_fail_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(xd_fail_label)
        else:
            self.score_label = QLabel(f"✅ 最终得分：{rounded_score} 分", self)
            self.score_label.setStyleSheet("font-size: 22px; color: #2e7d32; font-weight: bold;")

        self.score_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.score_label)

        self.accuracy_label = QLabel(f"正确率：{global_correct_count}/{self.total_questions} ({accuracy:.1f}%)", self)
        self.accuracy_label.setStyleSheet("font-size: 16px; color: #555;")
        self.accuracy_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.accuracy_label)

        minutes = int(self.total_time // 60)
        seconds = int(self.total_time % 60)
        milliseconds = int((self.total_time % 1) * 100)
        time_str = f"{minutes:02d}:{seconds:02d}.{milliseconds:02d}"

        self.time_label = QLabel(f"⏱ 答题用时：{time_str}", self)
        self.time_label.setStyleSheet("font-size: 16px; color: #1565c0;")
        self.time_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.time_label)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #ccc; margin: 10px 0;")
        layout.addWidget(line)

        btn_layout = QHBoxLayout()

        close_btn = QPushButton("关闭窗口", self)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        close_btn.clicked.connect(quit_application)
        btn_layout.addWidget(close_btn)

        restart_btn = QPushButton("重新答题", self)
        restart_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        restart_btn.clicked.connect(self.restart)
        btn_layout.addWidget(restart_btn)

        layout.addLayout(btn_layout)
        layout.addStretch(1)

        self.setWindowModality(Qt.ApplicationModal)

    def restart(self):
        global global_score, global_start_time, global_correct_count, global_total_answered
        global_score = 0
        global_start_time = time.time()
        global_correct_count = 0
        global_total_answered = 0
        self.is_restarting = True
        logging.info("从结果页重新答题")
        self.next_window = SongSelectionUI()
        switch_window(self.next_window, self)

    def closeEvent(self, event):
        if ignore_unexpected_close(self, event):
            return
        release_window(self)
        if not self.is_restarting and not _is_switching_window:
            quit_application()
        super().closeEvent(event)


class QuizUI(QMainWindow):
    def __init__(self, easy_music_range, hard_music_range, selected_difficulty, remaining_questions,
                 total_questions=None, accumulated_time=0):
        super().__init__()
        logging.info(
            "初始化答题窗口: difficulty=%s, easy=%d, hard=%d, remaining=%d",
            selected_difficulty,
            len(easy_music_range),
            len(hard_music_range),
            remaining_questions
        )
        self.easy_music_range = easy_music_range
        self.hard_music_range = hard_music_range
        self.selected_difficulty = selected_difficulty
        self.remaining_questions = remaining_questions
        self.total_questions = total_questions if total_questions is not None else remaining_questions
        self.accumulated_time = accumulated_time
        self.selected_option = None
        self.question_start_time = time.time()
        self.answer_confirmed = False
        self.is_transitioning = False
        self.is_closing = False
        self.play_generation = 0
        self.next_accumulated_time = 0  # 新增：保存下一题的时间

        self.media_player = MusicPlayer(volume=100)

        self.initUI()
        logging.info("答题窗口UI初始化完成")
        self.setup_button_group()
        logging.info("答题按钮组初始化完成")
        self.load_question()
        logging.info("第一题加载完成: %s", getattr(self, "current_correct_path", ""))

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer_display)
        self.timer.start(100)

        self.setFocusPolicy(Qt.StrongFocus)

    def initUI(self):
        global global_xd_mode

        title_mapping = {
            "简单": "简单难度",
            "普通": "普通难度",
            "困难": "困难难度"
        }

        title_text = title_mapping.get(self.selected_difficulty, "听歌猜名挑战")
        if global_xd_mode:
            title_text += " [XD模式]"

        self.setWindowTitle(title_text)
        self.setGeometry(300, 300, 800, 700)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        if global_xd_mode:
            xd_warning = QLabel("⚠️ XD模式：正确率低于50%时得分将归零！")
            xd_warning.setStyleSheet("""
                font-size: 14px;
                color: #d32f2f;
                font-weight: bold;
                background: #ffebee;
                padding: 8px;
                border-radius: 4px;
                border: 1px solid #ef5350;
            """)
            xd_warning.setAlignment(Qt.AlignCenter)
            layout.addWidget(xd_warning)

        keyboard_hint = QLabel("💡 快捷键：1/2/3/4 选择选项，Enter 确认 / 下一题")
        keyboard_hint.setStyleSheet("""
            font-size: 13px;
            color: #666;
            background: #f5f5f5;
            padding: 6px;
            border-radius: 4px;
        """)
        keyboard_hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(keyboard_hint)

        top_layout = QHBoxLayout()

        self.remaining_label = QLabel(f"剩余题目: {self.remaining_questions}/{self.total_questions}")
        self.remaining_label.setStyleSheet("font-size: 16px; margin: 10px; color: #333;")
        top_layout.addWidget(self.remaining_label)
        top_layout.addStretch(1)

        self.timer_label = QLabel("⏱ 00:00.00")
        self.timer_label.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #1565c0;
            font-family: 'Courier New', monospace;
            background: #e3f2fd;
            padding: 8px 16px;
            border-radius: 8px;
            border: 2px solid #1976d2;
        """)
        self.timer_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(self.timer_label)
        top_layout.addStretch(1)

        self.current_score_label = QLabel(f"当前得分: {round(global_score, 2)}")
        self.current_score_label.setStyleSheet("font-size: 16px; margin: 10px; color: #2e7d32;")
        top_layout.addWidget(self.current_score_label)

        layout.addLayout(top_layout)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #ccc;")
        layout.addWidget(line)

        self.option_btns = []
        self.option_labels = []

        for i in range(4):
            option_container = QWidget()
            option_layout = QHBoxLayout(option_container)
            option_layout.setSpacing(10)
            option_layout.setContentsMargins(10, 5, 10, 5)

            num_label = QLabel(f"[{i+1}]")
            num_label.setStyleSheet(OPTION_LABEL_STYLE)
            num_label.setAlignment(Qt.AlignCenter)
            self.option_labels.append(num_label)
            option_layout.addWidget(num_label)

            btn = QPushButton("选项")
            btn.setProperty("index", i)
            btn.setCheckable(True)
            btn.setStyleSheet(OPTION_BUTTON_STYLE)
            option_layout.addWidget(btn, 1)
            self.option_btns.append(btn)

            layout.addWidget(option_container)

        self.confirm_btn = QPushButton("确认 (Enter)")
        self.confirm_btn.setStyleSheet("""
            QPushButton {
                font-size: 20px;
                font-weight: bold;
                background: #4CAF50;
                color: white;
                padding: 12px 30px;
                border: none;
                border-radius: 8px;
                margin: 20px;
            }
            QPushButton:hover {
                background: #45a049;
            }
            QPushButton:disabled {
                background: #CCCCCC;
            }
        """)
        self.confirm_btn.clicked.connect(self.confirm_answer)
        layout.addWidget(self.confirm_btn, 0, Qt.AlignCenter)

    # ====================== 【核心修复】Enter 键全程生效 ======================
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if not self.answer_confirmed:
                self.confirm_answer()
            else:
                self.next_question(self.next_accumulated_time)
            return

        if not self.answer_confirmed:
            if key == Qt.Key_1:
                self.select_option(0)
            elif key == Qt.Key_2:
                self.select_option(1)
            elif key == Qt.Key_3:
                self.select_option(2)
            elif key == Qt.Key_4:
                self.select_option(3)

        super().keyPressEvent(event)

    def reset_question_state(self):
        self.answer_confirmed = False
        self.selected_option = None
        self.question_start_time = time.time()
        self.remaining_label.setText(f"剩余题目: {self.remaining_questions}/{self.total_questions}")
        self.current_score_label.setText(f"当前得分: {round(global_score, 2)}")

        for btn in self.option_btns:
            btn.setStyleSheet(OPTION_BUTTON_STYLE)
            btn.setEnabled(True)
            btn.setChecked(False)

        for label in self.option_labels:
            label.setStyleSheet(OPTION_LABEL_STYLE)

        self.confirm_btn.setEnabled(False)
        self.confirm_btn.setText("确认 (Enter)")
        try:
            self.confirm_btn.clicked.disconnect()
        except TypeError:
            pass
        self.confirm_btn.clicked.connect(self.confirm_answer)

    def finish_question_transition(self):
        self.is_transitioning = False

    def select_option(self, index):
        if index < len(self.option_btns):
            btn = self.option_btns[index]
            btn.setChecked(True)
            self.on_option_selected(btn)
            self.update_option_labels(index)

    def update_option_labels(self, selected_index):
        for i, label in enumerate(self.option_labels):
            if i == selected_index:
                label.setStyleSheet("""
                    font-size: 16px;
                    font-weight: bold;
                    color: white;
                    background: #1976d2;
                    padding: 5px 10px;
                    border-radius: 4px;
                    min-width: 30px;
                """)
            else:
                label.setStyleSheet("""
                    font-size: 16px;
                    font-weight: bold;
                    color: #666;
                    background: #e0e0e0;
                    padding: 5px 10px;
                    border-radius: 4px;
                    min-width: 30px;
                """)

    def update_timer_display(self):
        current_elapsed = time.time() - self.question_start_time
        total_elapsed = self.accumulated_time + current_elapsed
        minutes = int(total_elapsed // 60)
        seconds = int(total_elapsed % 60)
        milliseconds = int((total_elapsed % 1) * 100)
        time_str = f"⏱ {minutes:02d}:{seconds:02d}.{milliseconds:02d}"
        self.timer_label.setText(time_str)

    def setup_button_group(self):
        self.button_group = QButtonGroup(self)
        for i, btn in enumerate(self.option_btns):
            self.button_group.addButton(btn, i)
        self.button_group.buttonClicked.connect(self.on_option_selected)

    def get_song_name(self, path):
        return os.path.splitext(os.path.basename(path))[0]

    def load_question(self):
        self.answer_confirmed = False
        self.play_generation += 1

        if self.selected_difficulty == "简单":
            if len(self.easy_music_range) < 4:
                raise ValueError(f"简单难度至少需要4首可用歌曲，当前剩余{len(self.easy_music_range)}首")
            correct_index = random.randint(0, len(self.easy_music_range) - 1)
            correct_song = list(self.easy_music_range)[correct_index]
            self.current_correct_path = correct_song
            correct_name = self.get_song_name(correct_song)
            self.correct_name = correct_name
            wrong_options = list(self.easy_music_range)
            wrong_options.pop(correct_index)
            wrong_options = random.sample(wrong_options, 3)
            wrong_names = [self.get_song_name(song) for song in wrong_options]
            self.easy_music_range = {song for song in self.easy_music_range if song != correct_song}

        elif self.selected_difficulty == "普通":
            easy_songs = list(self.easy_music_range)
            hard_songs = list(self.hard_music_range)
            all_songs = easy_songs + hard_songs
            if len(all_songs) < 4:
                raise ValueError(f"普通难度至少需要4首可用歌曲，当前剩余{len(all_songs)}首")

            correct_song = random.choice(all_songs)
            self.current_correct_path = correct_song
            correct_name = self.get_song_name(correct_song)
            self.correct_name = correct_name
            wrong_options = random.sample([song for song in all_songs if song != correct_song], 3)
            if correct_song in self.easy_music_range:
                self.easy_music_range = {song for song in self.easy_music_range if song != correct_song}
            else:
                self.hard_music_range = {song for song in self.hard_music_range if song != correct_song}
            wrong_names = [self.get_song_name(song) for song in wrong_options]

        elif self.selected_difficulty == "困难":
            if len(self.hard_music_range) < 4:
                raise ValueError(f"困难难度至少需要4首可用歌曲，当前剩余{len(self.hard_music_range)}首")
            correct_index = random.randint(0, len(self.hard_music_range) - 1)
            correct_song = list(self.hard_music_range)[correct_index]
            self.current_correct_path = correct_song
            correct_name = self.get_song_name(correct_song)
            self.correct_name = correct_name
            wrong_options = list(self.hard_music_range)
            wrong_options.pop(correct_index)
            wrong_options = random.sample(wrong_options, 3)
            wrong_names = [self.get_song_name(song) for song in wrong_options]
            self.hard_music_range = {song for song in self.hard_music_range if song != correct_song}

        all_options = [correct_name] + wrong_names
        random.shuffle(all_options)

        for i, btn in enumerate(self.option_btns):
            btn.setText(all_options[i])
            btn.setProperty("is_correct", all_options[i] == correct_name)
            btn.setEnabled(True)
            btn.setChecked(False)
            btn.setStyleSheet(OPTION_BUTTON_STYLE)

        for label in self.option_labels:
            label.setStyleSheet(OPTION_LABEL_STYLE)

        self.selected_option = None
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.setText("确认 (Enter)")

        play_generation = self.play_generation
        QTimer.singleShot(500, lambda: self.play_current_music(play_generation))

    def on_option_selected(self, button):
        self.selected_option = self.button_group.id(button)
        self.confirm_btn.setEnabled(True)
        self.update_option_labels(self.selected_option)

    def play_current_music(self, play_generation=None):
        if play_generation != self.play_generation:
            logging.info("忽略过期的延迟播放请求")
            return

        if self.is_closing or not self.isVisible():
            logging.info("忽略已关闭窗口的延迟播放请求")
            return

        if self.media_player and hasattr(self, 'current_correct_path') and self.current_correct_path:
            try:
                self.media_player.play(self.current_correct_path)
            except Exception as exc:
                logging.exception("播放音乐失败: %s", self.current_correct_path)
                QMessageBox.critical(
                    self,
                    "播放失败",
                    f"音乐播放失败，{log_destination_text()}\n\n{exc}"
                )

    def confirm_answer(self):
        global global_score, global_correct_count, global_total_answered

        if self.selected_option is None or self.answer_confirmed or self.is_transitioning:
            return

        self.answer_confirmed = True
        self.timer.stop()
        question_elapsed = time.time() - self.question_start_time
        self.next_accumulated_time = self.accumulated_time + question_elapsed

        global_total_answered += 1

        for btn in self.option_btns:
            btn.setEnabled(False)

        selected_btn = self.option_btns[self.selected_option]
        is_correct = selected_btn.property("is_correct")

        if is_correct:
            global_correct_count += 1
            if self.selected_difficulty == "简单":
                global_score += 1
            elif self.selected_difficulty == "普通":
                global_score += 1.2
            else:
                global_score += 1.5

        self.current_score_label.setText(f"当前得分: {round(global_score, 2)}")

        for i, btn in enumerate(self.option_btns):
            if btn.property("is_correct"):
                btn.setStyleSheet("""
                    QPushButton {
                        font-size: 18px;
                        padding: 15px;
                        border-radius: 8px;
                        background: #c8e6c9;
                        border: 2px solid #4caf50;
                    }
                """)
                self.option_labels[i].setStyleSheet("""
                    font-size: 16px;
                    font-weight: bold;
                    color: white;
                    background: #4caf50;
                    padding: 5px 10px;
                    border-radius: 4px;
                    min-width: 30px;
                """)
            elif btn == selected_btn and not is_correct:
                btn.setStyleSheet("""
                    QPushButton {
                        font-size: 18px;
                        padding: 15px;
                        border-radius: 8px;
                        background: #ef9a9a;
                        border: 2px solid #f44336;
                    }
                """)
                self.option_labels[i].setStyleSheet("""
                    font-size: 16px;
                    font-weight: bold;
                    color: white;
                    background: #f44336;
                    padding: 5px 10px;
                    border-radius: 4px;
                    min-width: 30px;
                """)

        if self.remaining_questions <= 1:
            self.confirm_btn.setText("结束答题 (Enter)")
        else:
            self.confirm_btn.setText("下一题 (Enter)")

        try:
            self.confirm_btn.clicked.disconnect()
        except:
            pass
        self.confirm_btn.clicked.connect(lambda: self.next_question(self.next_accumulated_time))

    def next_question(self, accumulated_time):
        if self.is_transitioning:
            logging.info("忽略重复切题请求")
            return

        self.is_transitioning = True
        self.is_closing = True
        if self.media_player:
            self.media_player.stop()

        if self.remaining_questions <= 1:
            total_time = accumulated_time
            self.result_window = ResultWindow(total_time, self.total_questions)
            switch_window(self.result_window, self)
            return

        self.remaining_questions -= 1
        self.accumulated_time = accumulated_time
        self.is_closing = False
        self.reset_question_state()
        self.timer.start(100)
        self.load_question()
        logging.info("下一题加载完成: %s", getattr(self, "current_correct_path", ""))
        QTimer.singleShot(100, self.finish_question_transition)

    def closeEvent(self, event):
        if ignore_unexpected_close(self, event):
            return
        self.is_closing = True
        self.play_generation += 1
        if self.media_player:
            self.media_player.close()
            self.media_player = None
        release_window(self)
        if not _is_switching_window:
            quit_application()
        super().closeEvent(event)


class DifficultySelectionUI(QMainWindow):
    def __init__(self, selected_folders, music_root="music"):
        super().__init__()
        self.selected_folders = selected_folders
        self.music_root = music_root
        self.selected_difficulty = None
        self.xd_checkbox = None
        self.initUI()

    def initUI(self):
        global global_xd_mode

        self.setWindowTitle('听歌猜名挑战 - 难度选择')
        self.setGeometry(300, 300, 400, 400)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        title = QLabel("请选择难度：")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        self.radio_simple = QRadioButton("简单")
        self.radio_normal = QRadioButton("普通")
        self.radio_hard = QRadioButton("困难")

        self.radio_simple.toggled.connect(self.on_difficulty_selection)
        self.radio_normal.toggled.connect(self.on_difficulty_selection)
        self.radio_hard.toggled.connect(self.on_difficulty_selection)

        layout.addWidget(self.radio_simple)
        layout.addWidget(self.radio_normal)
        layout.addWidget(self.radio_hard)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #ccc; margin: 15px 0;")
        layout.addWidget(line)

        xd_container = QFrame()
        xd_container.setStyleSheet("""
            QFrame {
                background: #fff3e0;
                border-radius: 8px;
                border: 2px solid #ff9800;
                padding: 10px;
            }
        """)
        xd_layout = QVBoxLayout(xd_container)

        xd_title = QLabel("😈 XD模式（极限挑战）")
        xd_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #e65100;")
        xd_layout.addWidget(xd_title)

        self.xd_checkbox = QCheckBox("启用XD模式")
        self.xd_checkbox.setChecked(global_xd_mode)
        self.xd_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 14px;
                color: #bf360c;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
            }
        """)
        self.xd_checkbox.stateChanged.connect(self.on_xd_mode_changed)
        xd_layout.addWidget(self.xd_checkbox)

        xd_desc = QLabel("规则：正确率低于50%时，\n最终得分将强制归零！")
        xd_desc.setStyleSheet("font-size: 12px; color: #d84315;")
        xd_desc.setAlignment(Qt.AlignCenter)
        xd_layout.addWidget(xd_desc)

        layout.addWidget(xd_container)
        layout.addStretch(1)

        self.confirm_btn = QPushButton("确认")
        self.confirm_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                background: #4CAF50;
                color: white;
                padding: 10px;
                border: none;
                border-radius: 5px;
                min-width: 120px;
            }
            QPushButton:hover {
                background: #45a049;
            }
        """)
        self.confirm_btn.clicked.connect(self.on_confirm_click)
        layout.addWidget(self.confirm_btn, 0, Qt.AlignCenter)

    def on_difficulty_selection(self):
        sender = self.sender()
        if sender.isChecked():
            self.selected_difficulty = sender.text()

    def on_xd_mode_changed(self, state):
        global global_xd_mode
        global_xd_mode = (state == Qt.Checked)

    def on_confirm_click(self):
        try:
            self.start_quiz()
        except Exception as exc:
            logging.exception("开始答题失败")
            QMessageBox.critical(
                self,
                "开始失败",
                f"开始答题时发生错误，{log_destination_text()}\n\n{exc}"
            )

    def start_quiz(self):
        global global_start_time, global_score, global_correct_count, global_total_answered

        if not self.selected_difficulty:
            QMessageBox.warning(self, "请选择难度", "请先选择一个难度。")
            return

        global_score = 0.0
        global_correct_count = 0
        global_total_answered = 0

        easy_music_range = set()
        hard_music_range = set()
        for ip, sub_dir in self.selected_folders:
            base_path = os.path.join(self.music_root, ip, sub_dir)
            for root, dirs, files in os.walk(base_path):
                for file in files:
                    if file.lower().endswith(('.mp3', '.wav')):
                        if "easy" in root.lower():
                            easy_music_range.add(os.path.join(root, file))
                        elif "hard" in root.lower():
                            hard_music_range.add(os.path.join(root, file))

        if self.selected_difficulty == "简单":
            quiz_easy = easy_music_range
            quiz_hard = set()
            desired_question_count = 10
        elif self.selected_difficulty == "困难":
            quiz_easy = set()
            quiz_hard = hard_music_range
            desired_question_count = 5
        else:
            quiz_easy = easy_music_range
            quiz_hard = hard_music_range
            desired_question_count = 8

        available_count = len(quiz_easy) + len(quiz_hard)
        max_question_count = max(0, available_count - 3)
        question_count = min(desired_question_count, max_question_count)
        logging.info(
            "选择难度: %s, easy=%d, hard=%d, 可出题=%d, 实际题数=%d, 已选歌单=%s",
            self.selected_difficulty,
            len(quiz_easy),
            len(quiz_hard),
            max_question_count,
            question_count,
            sorted(self.selected_folders)
        )

        if question_count <= 0:
            QMessageBox.warning(
                self,
                "歌曲数量不足",
                f"{self.selected_difficulty}难度至少需要4首可用歌曲，当前只有{available_count}首。"
            )
            return

        if question_count < desired_question_count:
            QMessageBox.information(
                self,
                "题数已调整",
                f"当前歌单数量不足以生成{desired_question_count}题，本轮将生成{question_count}题。"
            )

        global_start_time = time.time()

        logging.info("开始创建答题窗口")
        self.quiz_ui = QuizUI(quiz_easy, quiz_hard, self.selected_difficulty, question_count, question_count, 0)
        logging.info("答题窗口创建完成，准备显示")
        switch_window(self.quiz_ui, self)
        logging.info("答题窗口已显示")

    def closeEvent(self, event):
        if ignore_unexpected_close(self, event):
            return
        release_window(self)
        if not _is_switching_window:
            quit_application()
        super().closeEvent(event)


class SongSelectionUI(QMainWindow):
    def __init__(self, music_root="music"):
        super().__init__()
        self.music_root = music_root
        self.selected_folders = set()
        self.ip_checkboxes = {}
        self.subdir_checkboxes = {}
        self.initUI()

    def initUI(self):
        self.setWindowTitle('听歌猜名挑战 - 选择歌单')
        self.setGeometry(300, 300, 600, 900)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        title = QLabel("请选择要挑战的歌单范围：")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        scroll.setWidget(content_widget)
        scroll_layout = QVBoxLayout(content_widget)
        scroll_layout.setSpacing(5)

        for ip in sorted(os.listdir(self.music_root)):
            ip_path = os.path.join(self.music_root, ip)
            if not os.path.isdir(ip_path):
                continue

            ip_container = QFrame()
            ip_container.setFrameShape(QFrame.StyledPanel)
            ip_container.setStyleSheet("""
                QFrame {
                    background: #F5F5F5;
                    border-radius: 4px;
                }
                QFrame:hover {
                    background: #EDEDED;
                }
            """)
            ip_layout = QVBoxLayout(ip_container)
            ip_layout.setContentsMargins(8, 8, 8, 8)

            ip_cb = QCheckBox(ip)
            ip_cb.setStyleSheet("""
                QCheckBox {
                    font-weight: bold;
                    font-size: 14px;
                    spacing: 8px;
                    padding: 2px;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                }
            """)
            ip_cb.ip = ip
            ip_cb.setTristate(True)
            ip_cb.stateChanged.connect(self.on_ip_checkbox_changed)
            self.ip_checkboxes[ip] = ip_cb
            ip_layout.addWidget(ip_cb)

            subdir_container = QWidget()
            subdir_layout = QVBoxLayout(subdir_container)
            subdir_layout.setContentsMargins(20, 5, 0, 0)
            subdir_layout.setSpacing(10)

            self.subdir_checkboxes[ip] = {}
            for sub_dir in sorted(os.listdir(ip_path)):
                sub_path = os.path.join(ip_path, sub_dir)
                if os.path.isdir(sub_path):
                    sub_cb = QCheckBox(sub_dir)
                    sub_cb.setStyleSheet("""
                        QCheckBox {
                            font-size: 13px;
                            padding: 1px;
                        }
                        QCheckBox::indicator {
                            width: 14px;
                            height: 14px;
                        }
                    """)
                    sub_cb.ip = ip
                    sub_cb.sub_dir = sub_dir
                    sub_cb.stateChanged.connect(self.on_subdir_selection_change)
                    subdir_layout.addWidget(sub_cb)
                    self.subdir_checkboxes[ip][sub_dir] = sub_cb

            ip_layout.addWidget(subdir_container)
            scroll_layout.addWidget(ip_container)

        scroll_layout.addStretch(1)
        layout.addWidget(scroll)

        self.next_btn = QPushButton("开始挑战 (0)")
        self.next_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                background: #4CAF50;
                color: white;
                padding: 10px;
                border: none;
                border-radius: 5px;
                min-width: 120px;
            }
            QPushButton:disabled {
                background: #CCCCCC;
            }
            QPushButton:hover {
                background: #45a049;
            }
        """)
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self.go_next_step)
        layout.addWidget(self.next_btn, 0, Qt.AlignCenter)

    def on_ip_checkbox_changed(self, state):
        ip_cb = self.sender()
        ip = ip_cb.ip
        if ip not in self.subdir_checkboxes:
            return
        if state == Qt.PartiallyChecked:
            return
        for cb in self.subdir_checkboxes[ip].values():
            cb.setChecked(state == Qt.Checked)

    def on_subdir_selection_change(self, state):
        sub_cb = self.sender()
        ip = sub_cb.ip
        sub_dir = sub_cb.sub_dir
        key = (ip, sub_dir)
        if state == Qt.Checked:
            self.selected_folders.add(key)
        else:
            self.selected_folders.discard(key)
        self.update_ip_checkbox_state(ip)
        self.next_btn.setText(f"开始挑战 ({len(self.selected_folders)})")
        self.next_btn.setEnabled(len(self.selected_folders) > 0)

    def update_ip_checkbox_state(self, ip):
        if ip not in self.ip_checkboxes or ip not in self.subdir_checkboxes:
            return
        ip_cb = self.ip_checkboxes[ip]
        subdirs = self.subdir_checkboxes[ip].values()
        checked_count = sum(1 for cb in subdirs if cb.isChecked())
        total_count = len(subdirs)
        if checked_count == 0:
            ip_cb.setCheckState(Qt.Unchecked)
        elif checked_count == total_count:
            ip_cb.setCheckState(Qt.Checked)
        else:
            ip_cb.setCheckState(Qt.PartiallyChecked)

    def go_next_step(self):
        self.difficulty_ui = DifficultySelectionUI(self.selected_folders)
        switch_window(self.difficulty_ui, self)

    def closeEvent(self, event):
        if ignore_unexpected_close(self, event):
            return
        release_window(self)
        if not _is_switching_window:
            quit_application()
        super().closeEvent(event)


if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.aboutToQuit.connect(stop_all_music_players)
    ex = SongSelectionUI()
    keep_window(ex)
    ex.show()
    sys.exit(app.exec_())
