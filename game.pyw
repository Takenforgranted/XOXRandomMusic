from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QCheckBox, QPushButton, QScrollArea, QHBoxLayout,
                             QLabel, QFrame, QRadioButton, QGridLayout, QButtonGroup, QMessageBox)
from PyQt5.QtCore import Qt, QTimer, QUrl


import os
import random

global_score = 0.0  # 分数记录

class ResultWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("答题结果")
        self.setGeometry(400, 400, 300, 200)
        self.setCentralWidget(QWidget())

        layout = QVBoxLayout(self.centralWidget())
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(20)

        # 标题标签
        title_label = QLabel("答题结束！", self)
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #333;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # 分数显示标签
        rounded_score = round(global_score, 2)
        self.score_label = QLabel(f"您的最终得分：{rounded_score} 分", self)
        self.score_label.setStyleSheet("font-size: 18px; color: #666;")
        self.score_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.score_label)

        # 关闭按钮
        close_btn = QPushButton("关闭窗口", self)
        close_btn.setStyleSheet("""
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
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, 0, Qt.AlignCenter)

        # 关闭按钮
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
        layout.addWidget(restart_btn, 0, Qt.AlignCenter)

        self.setWindowModality(Qt.ApplicationModal)  # 模态窗口防止后台操作

    def restart(self):
        global global_score
        global_score = 0
        self.next_window = SongSelectionUI()
        self.close()
        self.next_window.show()
class QuizUI(QMainWindow):
    def __init__(self, easy_music_range, hard_music_range, selected_difficulty, remaining_questions):
        super().__init__()
        self.easy_music_range = easy_music_range
        self.hard_music_range = hard_music_range
        self.selected_difficulty = selected_difficulty
        self.remaining_questions = remaining_questions
        self.selected_option = None

        # 初始化媒体播放器
        self.media_player = QMediaPlayer()
        self.media_player.setVolume(50)  # 设置音量为50%

        self.initUI()
        self.setup_button_group()
        self.load_question()

    def initUI(self):
        title_mapping = {
            "简单": "简单难度",
            "普通": "普通难度",
            "困难": "困难难度"
        }
        self.setWindowTitle(title_mapping.get(self.selected_difficulty, "听歌猜名挑战"))
        self.setGeometry(300, 300, 800, 600)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        layout = QVBoxLayout(main_widget)

        remaining_label = QLabel(f"剩余题目: {self.remaining_questions}")
        remaining_label.setStyleSheet("font-size: 16px; margin: 10px;")
        layout.addWidget(remaining_label, 0, Qt.AlignCenter)

        self.option_btns = []
        option_layout = QVBoxLayout()
        for i in range(4):  # 改为显式使用索引i
            btn = QPushButton("选项")
            btn.setProperty("index", i)  # 存储按钮索引
            btn.setCheckable(True)  # 设为可选中状态
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 18px;
                    padding: 15px;
                    margin: 10px;
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
            """)

            option_layout.addWidget(btn)
            self.option_btns.append(btn)
        layout.addLayout(option_layout)

        # 将确认按钮设为类属性，方便后续访问
        self.confirm_btn = QPushButton("确认")
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

    def setup_button_group(self):
        """设置按钮组，实现单选效果"""
        self.button_group = QButtonGroup(self)
        for i, btn in enumerate(self.option_btns):
            self.button_group.addButton(btn, i)
        self.button_group.buttonClicked.connect(self.on_option_selected)

    def get_song_name(self, path):
        """从路径中提取歌曲名（不含扩展名）"""
        return os.path.splitext(os.path.basename(path))[0]

    def load_question(self):
        if self.selected_difficulty == "简单":
            # 随机选择正确答案
            correct_index = random.randint(0, len(self.easy_music_range) - 1)
            correct_song = list(self.easy_music_range)[correct_index]
            self.current_correct_path = correct_song
            correct_name = self.get_song_name(correct_song)
            self.correct_name = correct_name  # 保存正确答案名称

            # 从剩余歌曲中选择错误答案
            wrong_options = list(self.easy_music_range)
            wrong_options.pop(correct_index)
            wrong_options = random.sample(wrong_options, 3)
            wrong_names = [self.get_song_name(song) for song in wrong_options]

            # 从easy_music_range中剔除已选的正确歌曲
            self.easy_music_range = {song for song in self.easy_music_range if song != correct_song}

        elif self.selected_difficulty == "普通":
            # 普通难度逻辑（保持原有代码不变）
            easy_songs = list(self.easy_music_range)
            hard_songs = list(self.hard_music_range)

            if len(easy_songs) < 2 or len(hard_songs) < 2:
                print("警告：普通难度歌单数量不足，无法生成题目")
                return

            correct_song = random.choice(easy_songs + hard_songs)
            self.current_correct_path = correct_song
            correct_name = self.get_song_name(correct_song)
            self.correct_name = correct_name

            if correct_song in easy_songs:
                wrong_easy = random.sample([s for s in easy_songs if s != correct_song], 1)
                wrong_hard = random.sample(hard_songs, 2)
                # 从easy_music_range中剔除已选的正确歌曲
                self.easy_music_range = {song for song in self.easy_music_range if song != correct_song}
            else:
                wrong_easy = random.sample(easy_songs, 2)
                wrong_hard = random.sample([s for s in hard_songs if s != correct_song], 1)
                # 从hard_music_range中剔除已选的正确歌曲
                self.hard_music_range = {song for song in self.hard_music_range if song != correct_song}

            wrong_options = wrong_easy + wrong_hard
            random.shuffle(wrong_options)
            wrong_names = [self.get_song_name(song) for song in wrong_options]

        elif self.selected_difficulty == "困难":
            # 随机选择正确答案
            correct_index = random.randint(0, len(self.hard_music_range) - 1)
            correct_song = list(self.hard_music_range)[correct_index]
            self.current_correct_path = correct_song
            correct_name = self.get_song_name(correct_song)
            self.correct_name = correct_name  # 保存正确答案名称

            # 从剩余歌曲中选择错误答案
            wrong_options = list(self.hard_music_range)
            wrong_options.pop(correct_index)
            wrong_options = random.sample(wrong_options, 3)
            wrong_names = [self.get_song_name(song) for song in wrong_options]

            # 从hard_music_range中剔除已选的正确歌曲
            self.hard_music_range = {song for song in self.hard_music_range if song != correct_song}

        # 合并选项并随机打乱（三种难度共用代码）
        all_options = [correct_name] + wrong_names
        random.shuffle(all_options)

        # 设置选项按钮文本
        for i, btn in enumerate(self.option_btns):
            btn.setText(all_options[i])
            btn.setProperty("is_correct", all_options[i] == correct_name)  # 标记正确选项

        # 延迟0.5秒后播放音乐
        QTimer.singleShot(500, self.play_current_music)

    def on_option_selected(self, button):
        """处理选项选择"""
        self.selected_option = self.button_group.id(button)
        if self.confirm_btn:
            self.confirm_btn.setEnabled(True)

    def play_current_music(self):
        if hasattr(self, 'current_correct_path') and self.current_correct_path:
            media_content = QMediaContent(QUrl.fromLocalFile(self.current_correct_path))
            self.media_player.setMedia(media_content)
            self.media_player.play()
            if self.media_player.state() == self.media_player.PlayingState:
                print("音乐正在播放")
            else:
                print("播放失败，状态:", self.media_player.state())
                print("错误信息:", self.media_player.errorString())

    def confirm_answer(self):
        global global_score  # 声明使用全局变量

        if self.selected_option is None:
            return

        # 禁用所有按钮防止重复选择
        for btn in self.option_btns:
            btn.setEnabled(False)

        selected_btn = self.option_btns[self.selected_option]
        is_correct = selected_btn.property("is_correct")

        #TODO: 得分记录
        if is_correct:
            if self.selected_difficulty == "简单":
                global_score += 1
            elif self.selected_difficulty == "普通":
                global_score += 1.2
            else:
                global_score += 1.5


        # **保留样式切换逻辑**
        for btn in self.option_btns:
            if btn.property("is_correct"):
                # 正确答案变绿
                btn.setStyleSheet("""
                    QPushButton {
                        font-size: 18px;
                        padding: 15px;
                        margin: 10px;
                        border-radius: 8px;
                        background: #c8e6c9;
                        border: 2px solid #4caf50;
                    }
                """)
            elif btn == selected_btn and not is_correct:
                # 错误选择变红
                btn.setStyleSheet("""
                    QPushButton {
                        font-size: 18px;
                        padding: 15px;
                        margin: 10px;
                        border-radius: 8px;
                        background: #ef9a9a;
                        border: 2px solid #f44336;
                    }
                """)

        # 修改确认按钮为下一题（安全连接信号）
        if self.confirm_btn:
            if self.remaining_questions <= 1:
                self.confirm_btn.setText("结束答题")
            else:
                self.confirm_btn.setText("下一题")

            # 先尝试断开原有连接，避免重复
            try:
                self.confirm_btn.clicked.disconnect(self.confirm_answer)
            except Exception as e:
                print("断开信号时忽略错误:", e)
            # 连接新槽函数
            self.confirm_btn.clicked.connect(self.next_question)
            print("确认按钮已切换为下一题，等待点击...")

    def next_question(self):
        # 停止当前音乐播放并清除媒体播放器实例
        if self.media_player:
            self.media_player.stop()
            self.media_player = None

        if self.remaining_questions <= 1:
            # 题目已完成，可在此添加结束逻辑（如显示结果）
            # 显示结果窗口（假设当前答对次数为 self.correct_count）
            self.result_window = ResultWindow()
            self.result_window.show()
            self.close()
            return

        # 创建新的QuizUI实例，传递更新后的参数
        self.next_window = QuizUI(
            easy_music_range=self.easy_music_range,
            hard_music_range=self.hard_music_range,
            selected_difficulty=self.selected_difficulty,
            remaining_questions=self.remaining_questions - 1
        )

        # 关闭当前窗口并显示下一题窗口
        self.close()
        self.next_window.show()

class DifficultySelectionUI(QMainWindow):
    def __init__(self, selected_folders, music_root="music"):
        super().__init__()
        self.selected_folders = selected_folders
        self.music_root = music_root
        self.selected_difficulty = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('听歌猜名挑战 - 难度选择')
        self.setGeometry(300, 300, 400, 300)

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

    def on_confirm_click(self):
        easy_music_range = set()
        hard_music_range = set()
        for ip, sub_dir in self.selected_folders:
            base_path = os.path.join(self.music_root, ip, sub_dir)
            for root, dirs, files in os.walk(base_path):
                for file in files:
                    if file.endswith('.mp3') or file.endswith('.wav'):
                        if "easy" in root.lower():
                            easy_music_range.add(os.path.join(root, file))
                        elif "hard" in root.lower():
                            hard_music_range.add(os.path.join(root, file))
        print("已选择的歌单：", self.selected_folders)
        print("已选择的难度：", self.selected_difficulty)
        print("easy难度歌单:")
        for path in easy_music_range:
            print("   "+path)
        print("hard难度歌单:")
        for path in hard_music_range:
            print("   "+path)

            # 根据难度选择相应的音乐集合
            if self.selected_difficulty == "简单":
                quiz_easy = easy_music_range
                quiz_hard = set()
            elif self.selected_difficulty == "困难":
                quiz_easy = set()
                quiz_hard = hard_music_range
            else:  # 普通难度
                quiz_easy = easy_music_range
                quiz_hard = hard_music_range

        # 关闭当前界面，显示答题界面
        self.close()
        self.quiz_ui = QuizUI(quiz_easy, quiz_hard, self.selected_difficulty, 5)
        self.quiz_ui.show()

class SongSelectionUI(QMainWindow):
    def __init__(self, music_root="music"):
        super().__init__()
        self.music_root = music_root
        self.selected_folders = set()
        self.ip_checkboxes = {}  # 存储IP级复选框 {ip: checkbox}
        self.subdir_checkboxes = {}  # 存储子目录复选框 {ip: {subdir: checkbox}}
        self.initUI()

    def initUI(self):
        self.setWindowTitle('听歌猜名挑战 - 选择歌单')
        self.setGeometry(300, 300, 600, 900)

        # 主容器
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # 标题
        title = QLabel("请选择要挑战的歌单范围：")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        scroll.setWidget(content_widget)
        scroll_layout = QVBoxLayout(content_widget)
        scroll_layout.setSpacing(5)

        # 遍历music目录生成选项
        for ip in sorted(os.listdir(self.music_root)):
            ip_path = os.path.join(self.music_root, ip)
            if not os.path.isdir(ip_path):
                continue

            # IP分类容器
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

            # IP复选框（点击将切换所有子目录）
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
            ip_cb.setTristate(True)  # 启用三态模式
            ip_cb.stateChanged.connect(self.on_ip_checkbox_changed)
            self.ip_checkboxes[ip] = ip_cb
            ip_layout.addWidget(ip_cb)

            # 子目录容器
            subdir_container = QWidget()
            subdir_layout = QVBoxLayout(subdir_container)
            subdir_layout.setContentsMargins(20, 5, 0, 0)  # 缩进效果
            subdir_layout.setSpacing(10)

            self.subdir_checkboxes[ip] = {}
            for sub_dir in sorted(os.listdir(ip_path)):
                sub_path = os.path.join(ip_path, sub_dir)
                if os.path.isdir(sub_path):
                    # 子目录复选框
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

        # 下一步按钮
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
        """IP复选框状态变化时的处理"""
        ip_cb = self.sender()
        ip = ip_cb.ip

        if ip not in self.subdir_checkboxes:
            return

        # 只有当用户点击时才处理（避免递归调用）
        if state == Qt.PartiallyChecked:
            return

        # 设置所有子目录的状态
        for cb in self.subdir_checkboxes[ip].values():
            cb.setChecked(state == Qt.Checked)

    def on_subdir_selection_change(self, state):
        """子目录选择变化时处理"""
        sub_cb = self.sender()
        ip = sub_cb.ip
        sub_dir = sub_cb.sub_dir

        # 更新选择集合
        key = (ip, sub_dir)
        if state == Qt.Checked:
            self.selected_folders.add(key)
        else:
            self.selected_folders.discard(key)

        # 更新IP复选框状态
        self.update_ip_checkbox_state(ip)

        # 更新下一步按钮
        self.next_btn.setText(f"开始挑战 ({len(self.selected_folders)})")
        self.next_btn.setEnabled(len(self.selected_folders) > 0)

    def update_ip_checkbox_state(self, ip):
        """根据子目录选择情况更新IP复选框状态"""
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
        """下一步按钮点击事件"""
        # print("已选择的歌单：", self.selected_folders)
        # 实际使用时替换为跳转逻辑
        self.close()  # 关闭当前界面
        self.difficulty_ui = DifficultySelectionUI(self.selected_folders)
        self.difficulty_ui.show()


if __name__ == '__main__':
    app = QApplication([])
    ex = SongSelectionUI()
    ex.show()
    app.exec_()