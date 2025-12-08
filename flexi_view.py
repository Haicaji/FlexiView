"""
FlexiView - 灵活的视频/图像显示控制程序
支持在另一块显示屏上播放视频或图像，可控制大小、位置和旋转角度
"""

import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import screeninfo
import os
import json
from PIL import Image, ImageTk


class DisplayWindow:
    """显示窗口类 - 在第二显示器上显示视频/图像"""
    
    def __init__(self, monitor_index=1):
        self.monitor_index = monitor_index
        self.monitors = screeninfo.get_monitors()
        self.window_name = "FlexiView Display"
        self.running = False
        self.frame = None
        self.lock = threading.Lock()
        
        # 显示参数
        self.scale = 1.0
        self.rotation = 0  # 旋转角度（度）
        self.offset_x = 0
        self.offset_y = 0
        self.background_color = (0, 0, 0)  # 背景颜色
        self.mirror_h = False  # 水平镜像
        self.mirror_v = False  # 垂直镜像
        
        # 智能选择显示器：如果有多个显示器，默认用第二个；否则用第一个
        if len(self.monitors) > 1:
            self.update_monitor(monitor_index)
        else:
            self.update_monitor(0)
            print("注意：只检测到一个显示器，显示窗口将在同一屏幕上打开")
    
    def update_monitor(self, monitor_index):
        """更新目标显示器"""
        self.monitors = screeninfo.get_monitors()
        if monitor_index < len(self.monitors):
            self.monitor_index = monitor_index
            self.target_monitor = self.monitors[monitor_index]
        else:
            self.target_monitor = self.monitors[0]
            self.monitor_index = 0
    
    def get_monitor_info(self):
        """获取所有显示器信息"""
        return [(i, f"显示器 {i+1}: {m.width}x{m.height} @ ({m.x}, {m.y})") 
                for i, m in enumerate(self.monitors)]
    
    def create_window(self):
        """创建显示窗口"""
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        
        # 先移动窗口到目标显示器
        cv2.moveWindow(self.window_name, self.target_monitor.x + 100, self.target_monitor.y + 100)
        
        # 稍等一下让窗口创建完成
        cv2.waitKey(100)
        
        # 设置全屏
        cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        cv2.moveWindow(self.window_name, self.target_monitor.x, self.target_monitor.y)
        cv2.resizeWindow(self.window_name, self.target_monitor.width, self.target_monitor.height)
        
        print(f"显示窗口已在显示器 {self.monitor_index + 1} 上创建: {self.target_monitor.width}x{self.target_monitor.height} @ ({self.target_monitor.x}, {self.target_monitor.y})")
    
    def set_frame(self, frame):
        """设置要显示的帧"""
        with self.lock:
            self.frame = frame.copy() if frame is not None else None
    
    def transform_frame(self, frame):
        """应用变换（缩放、旋转、镜像、位移）"""
        if frame is None:
            return None
        
        h, w = frame.shape[:2]
        
        # 镜像
        if self.mirror_h and self.mirror_v:
            frame = cv2.flip(frame, -1)  # 水平和垂直同时翻转
        elif self.mirror_h:
            frame = cv2.flip(frame, 1)  # 水平翻转
        elif self.mirror_v:
            frame = cv2.flip(frame, 0)  # 垂直翻转
        
        # 缩放（无限制）
        new_w = int(w * self.scale)
        new_h = int(h * self.scale)
        if new_w > 0 and new_h > 0:
            scaled = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        else:
            scaled = frame
        
        # 旋转
        if self.rotation != 0:
            center = (new_w // 2, new_h // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, self.rotation, 1.0)
            
            # 计算旋转后的边界框大小
            cos = np.abs(rotation_matrix[0, 0])
            sin = np.abs(rotation_matrix[0, 1])
            new_w_rot = int(new_h * sin + new_w * cos)
            new_h_rot = int(new_h * cos + new_w * sin)
            
            # 调整旋转中心
            rotation_matrix[0, 2] += (new_w_rot - new_w) / 2
            rotation_matrix[1, 2] += (new_h_rot - new_h) / 2
            
            rotated = cv2.warpAffine(scaled, rotation_matrix, (new_w_rot, new_h_rot),
                                     borderValue=self.background_color)
        else:
            rotated = scaled
        
        # 创建画布并放置图像
        canvas = np.full((self.target_monitor.height, self.target_monitor.width, 3),
                        self.background_color, dtype=np.uint8)
        
        # 计算放置位置（居中 + 偏移）
        rh, rw = rotated.shape[:2]
        x = (self.target_monitor.width - rw) // 2 + self.offset_x
        y = (self.target_monitor.height - rh) // 2 + self.offset_y
        
        # 计算有效的放置区域
        src_x1 = max(0, -x)
        src_y1 = max(0, -y)
        src_x2 = min(rw, self.target_monitor.width - x)
        src_y2 = min(rh, self.target_monitor.height - y)
        
        dst_x1 = max(0, x)
        dst_y1 = max(0, y)
        dst_x2 = dst_x1 + (src_x2 - src_x1)
        dst_y2 = dst_y1 + (src_y2 - src_y1)
        
        if src_x2 > src_x1 and src_y2 > src_y1:
            canvas[dst_y1:dst_y2, dst_x1:dst_x2] = rotated[src_y1:src_y2, src_x1:src_x2]
        
        return canvas
    
    def display_loop(self):
        """显示循环"""
        self.create_window()
        self.running = True
        
        while self.running:
            with self.lock:
                current_frame = self.frame.copy() if self.frame is not None else None
            
            if current_frame is not None:
                display_frame = self.transform_frame(current_frame)
                if display_frame is not None:
                    cv2.imshow(self.window_name, display_frame)
            else:
                # 显示黑屏
                black = np.zeros((self.target_monitor.height, self.target_monitor.width, 3), dtype=np.uint8)
                cv2.imshow(self.window_name, black)
            
            key = cv2.waitKey(16)  # ~60fps
            if key == 27:  # ESC键退出
                self.running = False
        
        cv2.destroyWindow(self.window_name)
    
    def stop(self):
        """停止显示"""
        self.running = False


class VideoPlayer:
    """视频播放器类"""
    
    def __init__(self, display_window):
        self.display = display_window
        self.cap = None
        self.playing = False
        self.paused = False
        self.loop = True
        self.current_frame_idx = 0
        self.total_frames = 0
        self.fps = 30
        self.source_type = None  # 'video', 'image', 'camera'
        self.static_frame = None
        self.play_thread = None
    
    def load_video(self, path):
        """加载视频文件"""
        if self.cap is not None:
            self.cap.release()
        
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            return False
        
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        self.current_frame_idx = 0
        self.source_type = 'video'
        
        # 读取第一帧预览
        ret, frame = self.cap.read()
        if ret:
            self.display.set_frame(frame)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        return True
    
    def load_image(self, path):
        """加载图像文件"""
        self.stop()
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        
        frame = cv2.imread(path)
        if frame is None:
            return False
        
        self.static_frame = frame
        self.source_type = 'image'
        self.display.set_frame(frame)
        return True
    
    def load_camera(self, camera_id=0):
        """加载摄像头"""
        if self.cap is not None:
            self.cap.release()
        
        self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            return False
        
        self.fps = 30
        self.source_type = 'camera'
        return True
    
    def play(self):
        """开始播放"""
        if self.source_type == 'image':
            return
        
        self.playing = True
        self.paused = False
        
        if self.play_thread is None or not self.play_thread.is_alive():
            self.play_thread = threading.Thread(target=self._play_loop, daemon=True)
            self.play_thread.start()
    
    def pause(self):
        """暂停播放"""
        self.paused = True
    
    def resume(self):
        """继续播放"""
        self.paused = False
    
    def stop(self):
        """停止播放"""
        self.playing = False
        if self.play_thread is not None:
            self.play_thread.join(timeout=1)
        if self.cap is not None and self.source_type == 'video':
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.current_frame_idx = 0
    
    def seek(self, frame_idx):
        """跳转到指定帧"""
        if self.cap is not None and self.source_type == 'video':
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            self.current_frame_idx = frame_idx
            ret, frame = self.cap.read()
            if ret:
                self.display.set_frame(frame)
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    
    def _play_loop(self):
        """播放循环"""
        import time
        
        frame_duration = 1.0 / self.fps
        
        while self.playing and self.cap is not None:
            if self.paused:
                time.sleep(0.05)
                continue
            
            start_time = time.time()
            
            ret, frame = self.cap.read()
            if not ret:
                if self.loop and self.source_type == 'video':
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self.current_frame_idx = 0
                    continue
                else:
                    self.playing = False
                    break
            
            self.current_frame_idx = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            self.display.set_frame(frame)
            
            # 帧率控制
            elapsed = time.time() - start_time
            if elapsed < frame_duration:
                time.sleep(frame_duration - elapsed)
    
    def release(self):
        """释放资源"""
        self.stop()
        if self.cap is not None:
            self.cap.release()


class ControlPanel:
    """控制面板类 - 在主显示器上"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("FlexiView 控制面板")
        self.root.resizable(True, True)
        
        # 初始化显示窗口和播放器
        self.display = DisplayWindow(monitor_index=1)
        self.player = VideoPlayer(self.display)
        
        # 显示线程
        self.display_thread = None
        
        # 预览相关
        self.preview_show_processed = True  # True显示处理后，False显示原始
        self.preview_label = None
        self.preview_size = (320, 180)  # 预览窗口大小
        
        self.setup_ui()
        
        # 让窗口根据内容自适应大小
        self.root.update_idletasks()
        
        # 获取内容所需的大小
        req_width = self.root.winfo_reqwidth()
        req_height = self.root.winfo_reqheight()
        
        # 获取屏幕大小，限制最大高度为屏幕高度的90%
        monitors = screeninfo.get_monitors()
        if len(monitors) > 0:
            screen_height = monitors[0].height
            screen_width = monitors[0].width
            max_height = int(screen_height * 0.9)
            max_width = int(screen_width * 0.9)
            
            # 设置窗口大小（不超过屏幕限制）
            final_width = min(req_width + 30, max_width)  # +30 为滚动条预留空间
            final_height = min(req_height + 20, max_height)
            
            self.root.geometry(f"{final_width}x{final_height}+{monitors[0].x + 50}+{monitors[0].y + 50}")
        else:
            self.root.geometry(f"{req_width + 30}x{req_height + 20}")
        
        # 设置最小尺寸
        self.root.minsize(450, 400)
        
        # 启动预览更新
        self.update_preview()
    
    def setup_ui(self):
        """设置用户界面"""
        # 创建 Canvas 和滚动条实现可滚动界面
        self.main_canvas = tk.Canvas(self.root)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        scrollable_frame = ttk.Frame(self.main_canvas, padding="10")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        )
        
        self.main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=scrollbar.set)
        
        # 鼠标滚轮支持
        def on_mousewheel(event):
            self.main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.main_canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        scrollbar.pack(side="right", fill="y")
        self.main_canvas.pack(side="left", fill="both", expand=True)
        
        # 主框架 (使用 scrollable_frame 替代原来的 main_frame)
        main_frame = scrollable_frame
        
        # === 文件选择区域 ===
        file_frame = ttk.LabelFrame(main_frame, text="媒体源", padding="5")
        file_frame.pack(fill=tk.X, pady=5)
        
        btn_frame = ttk.Frame(file_frame)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="打开视频", command=self.open_video).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="打开图片", command=self.open_image).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="打开摄像头", command=self.open_camera).pack(side=tk.LEFT, padx=2)
        
        self.file_label = ttk.Label(file_frame, text="未选择文件")
        self.file_label.pack(fill=tk.X, pady=5)
        
        # === 显示器选择 ===
        monitor_frame = ttk.LabelFrame(main_frame, text="显示器", padding="5")
        monitor_frame.pack(fill=tk.X, pady=5)
        
        self.monitor_var = tk.StringVar()
        self.monitor_combo = ttk.Combobox(monitor_frame, textvariable=self.monitor_var, state="readonly")
        self.monitor_combo.pack(fill=tk.X)
        self.update_monitor_list()
        self.monitor_combo.bind("<<ComboboxSelected>>", self.on_monitor_change)
        
        ttk.Button(monitor_frame, text="刷新显示器列表", command=self.update_monitor_list).pack(pady=5)
        
        # === 播放控制 ===
        play_frame = ttk.LabelFrame(main_frame, text="播放控制", padding="5")
        play_frame.pack(fill=tk.X, pady=5)
        
        play_btn_frame = ttk.Frame(play_frame)
        play_btn_frame.pack(fill=tk.X)
        
        self.play_btn = ttk.Button(play_btn_frame, text="▶ 播放", command=self.toggle_play)
        self.play_btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(play_btn_frame, text="■ 停止", command=self.stop_play).pack(side=tk.LEFT, padx=2)
        
        self.loop_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(play_btn_frame, text="循环播放", variable=self.loop_var,
                       command=self.toggle_loop).pack(side=tk.LEFT, padx=10)
        
        # 进度条
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_scale = ttk.Scale(play_frame, from_=0, to=100, 
                                        variable=self.progress_var, orient=tk.HORIZONTAL)
        self.progress_scale.pack(fill=tk.X, pady=5)
        self.progress_scale.bind("<ButtonRelease-1>", self.on_seek)
        
        # === 变换控制 ===
        transform_frame = ttk.LabelFrame(main_frame, text="变换控制", padding="5")
        transform_frame.pack(fill=tk.X, pady=5)
        
        # 缩放（无限制，使用输入框控制）
        scale_frame = ttk.Frame(transform_frame)
        scale_frame.pack(fill=tk.X, pady=2)
        ttk.Label(scale_frame, text="缩放:").pack(side=tk.LEFT)
        self.scale_var = tk.DoubleVar(value=1.0)
        self.scale_entry = ttk.Entry(scale_frame, textvariable=self.scale_var, width=8)
        self.scale_entry.pack(side=tk.LEFT, padx=5)
        self.scale_entry.bind('<Return>', self.on_scale_entry_change)
        self.scale_entry.bind('<FocusOut>', self.on_scale_entry_change)
        # 滑块范围仅用于快速调整，实际值可通过输入框设置任意值
        self.scale_slider = ttk.Scale(scale_frame, from_=0.01, to=10.0, variable=self.scale_var,
                 orient=tk.HORIZONTAL, command=self.on_scale_change)
        self.scale_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 旋转
        rotation_frame = ttk.Frame(transform_frame)
        rotation_frame.pack(fill=tk.X, pady=2)
        ttk.Label(rotation_frame, text="旋转:").pack(side=tk.LEFT)
        self.rotation_var = tk.DoubleVar(value=0)
        self.rotation_entry = ttk.Entry(rotation_frame, textvariable=self.rotation_var, width=8)
        self.rotation_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(rotation_frame, text="°").pack(side=tk.LEFT)
        ttk.Scale(rotation_frame, from_=-180, to=180, variable=self.rotation_var,
                 orient=tk.HORIZONTAL, command=self.on_rotation_change).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # X偏移
        x_frame = ttk.Frame(transform_frame)
        x_frame.pack(fill=tk.X, pady=2)
        ttk.Label(x_frame, text="X偏移:").pack(side=tk.LEFT)
        self.offset_x_var = tk.IntVar(value=0)
        ttk.Entry(x_frame, textvariable=self.offset_x_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Scale(x_frame, from_=-1000, to=1000, variable=self.offset_x_var,
                 orient=tk.HORIZONTAL, command=self.on_offset_change).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Y偏移
        y_frame = ttk.Frame(transform_frame)
        y_frame.pack(fill=tk.X, pady=2)
        ttk.Label(y_frame, text="Y偏移:").pack(side=tk.LEFT)
        self.offset_y_var = tk.IntVar(value=0)
        ttk.Entry(y_frame, textvariable=self.offset_y_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Scale(y_frame, from_=-1000, to=1000, variable=self.offset_y_var,
                 orient=tk.HORIZONTAL, command=self.on_offset_change).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 重置按钮
        ttk.Button(transform_frame, text="重置变换", command=self.reset_transform).pack(pady=5)
        
        # === 快捷旋转 ===
        quick_rotation_frame = ttk.Frame(transform_frame)
        quick_rotation_frame.pack(fill=tk.X, pady=5)
        ttk.Label(quick_rotation_frame, text="快捷旋转:").pack(side=tk.LEFT)
        for angle in [0, 90, 180, 270]:
            ttk.Button(quick_rotation_frame, text=f"{angle}°", width=5,
                      command=lambda a=angle: self.set_rotation(a)).pack(side=tk.LEFT, padx=2)
        
        # === 镜像控制 ===
        mirror_frame = ttk.Frame(transform_frame)
        mirror_frame.pack(fill=tk.X, pady=5)
        ttk.Label(mirror_frame, text="镜像:").pack(side=tk.LEFT)
        self.mirror_h_var = tk.BooleanVar(value=False)
        self.mirror_v_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(mirror_frame, text="水平镜像", variable=self.mirror_h_var,
                       command=self.on_mirror_change).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(mirror_frame, text="垂直镜像", variable=self.mirror_v_var,
                       command=self.on_mirror_change).pack(side=tk.LEFT, padx=5)
        
        # === 背景颜色 ===
        bg_frame = ttk.LabelFrame(main_frame, text="背景颜色", padding="5")
        bg_frame.pack(fill=tk.X, pady=5)
        
        bg_btn_frame = ttk.Frame(bg_frame)
        bg_btn_frame.pack(fill=tk.X)
        
        ttk.Button(bg_btn_frame, text="黑色", command=lambda: self.set_bg_color(0, 0, 0)).pack(side=tk.LEFT, padx=2)
        ttk.Button(bg_btn_frame, text="白色", command=lambda: self.set_bg_color(255, 255, 255)).pack(side=tk.LEFT, padx=2)
        ttk.Button(bg_btn_frame, text="绿色", command=lambda: self.set_bg_color(0, 255, 0)).pack(side=tk.LEFT, padx=2)
        ttk.Button(bg_btn_frame, text="蓝色", command=lambda: self.set_bg_color(255, 0, 0)).pack(side=tk.LEFT, padx=2)
        
        # === 显示控制 ===
        display_frame = ttk.LabelFrame(main_frame, text="显示控制", padding="5")
        display_frame.pack(fill=tk.X, pady=5)
        
        self.display_btn = ttk.Button(display_frame, text="启动显示窗口", command=self.toggle_display)
        self.display_btn.pack(fill=tk.X)
        
        # === 配置保存/加载 ===
        config_frame = ttk.LabelFrame(main_frame, text="配置管理", padding="5")
        config_frame.pack(fill=tk.X, pady=5)
        
        config_btn_frame = ttk.Frame(config_frame)
        config_btn_frame.pack(fill=tk.X)
        
        ttk.Button(config_btn_frame, text="保存配置", command=self.save_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(config_btn_frame, text="加载配置", command=self.load_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(config_btn_frame, text="快速保存", command=self.quick_save_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(config_btn_frame, text="快速加载", command=self.quick_load_config).pack(side=tk.LEFT, padx=2)
        
        # === 预览窗口 ===
        preview_frame = ttk.LabelFrame(main_frame, text="预览", padding="5")
        preview_frame.pack(fill=tk.X, pady=5)
        
        # 预览控制按钮
        preview_ctrl_frame = ttk.Frame(preview_frame)
        preview_ctrl_frame.pack(fill=tk.X, pady=2)
        
        self.preview_mode_var = tk.StringVar(value="处理后")
        self.preview_toggle_btn = ttk.Button(preview_ctrl_frame, text="显示: 处理后", 
                                              command=self.toggle_preview_mode)
        self.preview_toggle_btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(preview_ctrl_frame, text="预览大小:").pack(side=tk.LEFT, padx=(10, 2))
        self.preview_size_var = tk.StringVar(value="320x180")
        preview_size_combo = ttk.Combobox(preview_ctrl_frame, textvariable=self.preview_size_var, 
                                          state="readonly", width=10)
        preview_size_combo['values'] = ["160x90", "320x180", "480x270", "640x360"]
        preview_size_combo.pack(side=tk.LEFT, padx=2)
        preview_size_combo.bind("<<ComboboxSelected>>", self.on_preview_size_change)
        
        # 预览画面显示区域
        self.preview_canvas = tk.Canvas(preview_frame, width=320, height=180, bg='black')
        self.preview_canvas.pack(pady=5)
        
        # 用于保存当前预览图像引用（防止被垃圾回收）
        self.preview_photo = None
        
        # === 状态栏 ===
        self.status_label = ttk.Label(main_frame, text="就绪")
        self.status_label.pack(fill=tk.X, pady=5)
        
        # 定时更新UI
        self.update_ui()
    
    def update_monitor_list(self):
        """更新显示器列表"""
        monitors = self.display.get_monitor_info()
        values = [info for _, info in monitors]
        self.monitor_combo['values'] = values
        if values:
            if self.display.monitor_index < len(values):
                self.monitor_combo.current(self.display.monitor_index)
            else:
                self.monitor_combo.current(0)
    
    def on_monitor_change(self, event):
        """显示器选择改变"""
        idx = self.monitor_combo.current()
        self.display.update_monitor(idx)
        self.status_label.config(text=f"切换到显示器 {idx + 1}")
    
    def open_video(self):
        """打开视频文件"""
        path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[
                ("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm"),
                ("所有文件", "*.*")
            ]
        )
        if path:
            if self.player.load_video(path):
                self.file_label.config(text=os.path.basename(path))
                self.status_label.config(text=f"已加载视频: {os.path.basename(path)}")
                self.progress_scale.config(to=self.player.total_frames)
            else:
                messagebox.showerror("错误", "无法打开视频文件")
    
    def open_image(self):
        """打开图像文件"""
        path = filedialog.askopenfilename(
            title="选择图像文件",
            filetypes=[
                ("图像文件", "*.jpg *.jpeg *.png *.bmp *.gif *.tiff"),
                ("所有文件", "*.*")
            ]
        )
        if path:
            if self.player.load_image(path):
                self.file_label.config(text=os.path.basename(path))
                self.status_label.config(text=f"已加载图像: {os.path.basename(path)}")
            else:
                messagebox.showerror("错误", "无法打开图像文件")
    
    def open_camera(self):
        """打开摄像头"""
        if self.player.load_camera(0):
            self.file_label.config(text="摄像头 0")
            self.status_label.config(text="摄像头已连接")
            self.player.play()
        else:
            messagebox.showerror("错误", "无法打开摄像头")
    
    def toggle_play(self):
        """切换播放/暂停"""
        if self.player.playing and not self.player.paused:
            self.player.pause()
            self.play_btn.config(text="▶ 播放")
        else:
            self.player.play()
            self.play_btn.config(text="⏸ 暂停")
    
    def stop_play(self):
        """停止播放"""
        self.player.stop()
        self.play_btn.config(text="▶ 播放")
        self.progress_var.set(0)
    
    def toggle_loop(self):
        """切换循环播放"""
        self.player.loop = self.loop_var.get()
    
    def on_seek(self, event):
        """进度条拖动"""
        if self.player.source_type == 'video':
            frame_idx = int(self.progress_var.get())
            self.player.seek(frame_idx)
    
    def on_scale_change(self, value):
        """缩放改变（滑块）"""
        self.display.scale = float(value)
    
    def on_scale_entry_change(self, event=None):
        """缩放改变（输入框）"""
        try:
            value = float(self.scale_var.get())
            if value > 0:
                self.display.scale = value
            else:
                self.scale_var.set(self.display.scale)
        except ValueError:
            self.scale_var.set(self.display.scale)
    
    def on_mirror_change(self):
        """镜像改变"""
        self.display.mirror_h = self.mirror_h_var.get()
        self.display.mirror_v = self.mirror_v_var.get()
    
    def on_rotation_change(self, value):
        """旋转改变"""
        self.display.rotation = float(value)
    
    def on_offset_change(self, value=None):
        """偏移改变"""
        self.display.offset_x = self.offset_x_var.get()
        self.display.offset_y = self.offset_y_var.get()
    
    def set_rotation(self, angle):
        """设置旋转角度"""
        self.rotation_var.set(angle)
        self.display.rotation = angle
    
    def set_bg_color(self, b, g, r):
        """设置背景颜色（BGR格式）"""
        self.display.background_color = (b, g, r)
    
    def reset_transform(self):
        """重置所有变换"""
        self.scale_var.set(1.0)
        self.rotation_var.set(0)
        self.offset_x_var.set(0)
        self.offset_y_var.set(0)
        self.mirror_h_var.set(False)
        self.mirror_v_var.set(False)
        
        self.display.scale = 1.0
        self.display.rotation = 0
        self.display.offset_x = 0
        self.display.offset_y = 0
        self.display.mirror_h = False
        self.display.mirror_v = False
    
    def get_config(self):
        """获取当前配置"""
        return {
            'scale': self.display.scale,
            'rotation': self.display.rotation,
            'offset_x': self.display.offset_x,
            'offset_y': self.display.offset_y,
            'mirror_h': self.display.mirror_h,
            'mirror_v': self.display.mirror_v,
            'background_color': list(self.display.background_color),
            'monitor_index': self.display.monitor_index
        }
    
    def apply_config(self, config):
        """应用配置"""
        if 'scale' in config:
            self.scale_var.set(config['scale'])
            self.display.scale = config['scale']
        if 'rotation' in config:
            self.rotation_var.set(config['rotation'])
            self.display.rotation = config['rotation']
        if 'offset_x' in config:
            self.offset_x_var.set(config['offset_x'])
            self.display.offset_x = config['offset_x']
        if 'offset_y' in config:
            self.offset_y_var.set(config['offset_y'])
            self.display.offset_y = config['offset_y']
        if 'mirror_h' in config:
            self.mirror_h_var.set(config['mirror_h'])
            self.display.mirror_h = config['mirror_h']
        if 'mirror_v' in config:
            self.mirror_v_var.set(config['mirror_v'])
            self.display.mirror_v = config['mirror_v']
        if 'background_color' in config:
            self.display.background_color = tuple(config['background_color'])
        if 'monitor_index' in config:
            self.display.update_monitor(config['monitor_index'])
            self.update_monitor_list()
    
    def save_config(self):
        """保存配置到文件"""
        path = filedialog.asksaveasfilename(
            title="保存配置",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")]
        )
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(self.get_config(), f, indent=2, ensure_ascii=False)
                self.status_label.config(text=f"配置已保存: {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("错误", f"保存配置失败: {e}")
    
    def load_config(self):
        """从文件加载配置"""
        path = filedialog.askopenfilename(
            title="加载配置",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")]
        )
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.apply_config(config)
                self.status_label.config(text=f"配置已加载: {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("错误", f"加载配置失败: {e}")
    
    def quick_save_config(self):
        """快速保存配置到默认文件"""
        config_path = os.path.join(os.path.dirname(__file__), 'flexi_view_config.json')
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.get_config(), f, indent=2, ensure_ascii=False)
            self.status_label.config(text="配置已快速保存")
        except Exception as e:
            messagebox.showerror("错误", f"快速保存失败: {e}")
    
    def quick_load_config(self):
        """从默认文件快速加载配置"""
        config_path = os.path.join(os.path.dirname(__file__), 'flexi_view_config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.apply_config(config)
                self.status_label.config(text="配置已快速加载")
            except Exception as e:
                messagebox.showerror("错误", f"快速加载失败: {e}")
        else:
            messagebox.showinfo("提示", "没有找到快速保存的配置文件")
    
    def toggle_display(self):
        """切换显示窗口"""
        if self.display_thread is None or not self.display_thread.is_alive():
            self.display_thread = threading.Thread(target=self.display.display_loop, daemon=True)
            self.display_thread.start()
            self.display_btn.config(text="关闭显示窗口")
            self.status_label.config(text="显示窗口已启动")
        else:
            self.display.stop()
            self.display_btn.config(text="启动显示窗口")
            self.status_label.config(text="显示窗口已关闭")
    
    def toggle_preview_mode(self):
        """切换预览模式（处理后/原始）"""
        self.preview_show_processed = not self.preview_show_processed
        if self.preview_show_processed:
            self.preview_toggle_btn.config(text="显示: 处理后")
        else:
            self.preview_toggle_btn.config(text="显示: 原始")
    
    def on_preview_size_change(self, event=None):
        """预览大小改变"""
        size_str = self.preview_size_var.get()
        try:
            w, h = map(int, size_str.split('x'))
            self.preview_size = (w, h)
            self.preview_canvas.config(width=w, height=h)
        except:
            pass
    
    def update_preview(self):
        """更新预览画面"""
        try:
            # 获取当前帧
            with self.display.lock:
                current_frame = self.display.frame.copy() if self.display.frame is not None else None
            
            if current_frame is not None:
                preview_w, preview_h = self.preview_size
                
                if self.preview_show_processed:
                    # 显示处理后的画面 - 模拟实际显示效果
                    frame = current_frame.copy()
                    h, w = frame.shape[:2]
                    
                    # 应用镜像
                    if self.display.mirror_h and self.display.mirror_v:
                        frame = cv2.flip(frame, -1)
                    elif self.display.mirror_h:
                        frame = cv2.flip(frame, 1)
                    elif self.display.mirror_v:
                        frame = cv2.flip(frame, 0)
                    
                    # 计算预览的缩放比例（相对于目标显示器）
                    # 预览窗口与目标显示器的比例
                    monitor_w = self.display.target_monitor.width
                    monitor_h = self.display.target_monitor.height
                    preview_scale = min(preview_w / monitor_w, preview_h / monitor_h)
                    
                    # 应用用户设置的缩放
                    scaled_w = int(w * self.display.scale * preview_scale)
                    scaled_h = int(h * self.display.scale * preview_scale)
                    
                    if scaled_w > 0 and scaled_h > 0:
                        frame = cv2.resize(frame, (scaled_w, scaled_h), interpolation=cv2.INTER_LINEAR)
                    
                    # 应用旋转
                    if self.display.rotation != 0:
                        rh, rw = frame.shape[:2]
                        center = (rw // 2, rh // 2)
                        rotation_matrix = cv2.getRotationMatrix2D(center, self.display.rotation, 1.0)
                        cos = np.abs(rotation_matrix[0, 0])
                        sin = np.abs(rotation_matrix[0, 1])
                        new_w_rot = int(rh * sin + rw * cos)
                        new_h_rot = int(rh * cos + rw * sin)
                        rotation_matrix[0, 2] += (new_w_rot - rw) / 2
                        rotation_matrix[1, 2] += (new_h_rot - rh) / 2
                        frame = cv2.warpAffine(frame, rotation_matrix, (new_w_rot, new_h_rot),
                                             borderValue=self.display.background_color)
                    
                    # 创建预览画布（模拟显示器）
                    preview_img = np.full((preview_h, preview_w, 3), self.display.background_color, dtype=np.uint8)
                    
                    # 计算放置位置（居中 + 偏移，按比例缩放偏移量）
                    rh, rw = frame.shape[:2]
                    x = int((preview_w - rw) / 2 + self.display.offset_x * preview_scale)
                    y = int((preview_h - rh) / 2 + self.display.offset_y * preview_scale)
                    
                    # 计算有效的放置区域
                    src_x1 = max(0, -x)
                    src_y1 = max(0, -y)
                    src_x2 = min(rw, preview_w - x)
                    src_y2 = min(rh, preview_h - y)
                    
                    dst_x1 = max(0, x)
                    dst_y1 = max(0, y)
                    dst_x2 = dst_x1 + (src_x2 - src_x1)
                    dst_y2 = dst_y1 + (src_y2 - src_y1)
                    
                    if src_x2 > src_x1 and src_y2 > src_y1:
                        preview_img[dst_y1:dst_y2, dst_x1:dst_x2] = frame[src_y1:src_y2, src_x1:src_x2]
                    
                    display_frame = preview_img
                else:
                    # 显示原始画面 - 简单缩放到预览尺寸
                    h, w = current_frame.shape[:2]
                    scale = min(preview_w / w, preview_h / h)
                    new_w = int(w * scale)
                    new_h = int(h * scale)
                    
                    if new_w > 0 and new_h > 0:
                        resized = cv2.resize(current_frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                        display_frame = np.zeros((preview_h, preview_w, 3), dtype=np.uint8)
                        x_offset = (preview_w - new_w) // 2
                        y_offset = (preview_h - new_h) // 2
                        display_frame[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
                    else:
                        display_frame = np.zeros((preview_h, preview_w, 3), dtype=np.uint8)
                
                # 转换为Tkinter可用格式 (BGR -> RGB)
                preview_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(preview_rgb)
                self.preview_photo = ImageTk.PhotoImage(pil_image)
                
                # 更新Canvas
                self.preview_canvas.delete("all")
                self.preview_canvas.create_image(preview_w//2, preview_h//2, 
                                                 image=self.preview_photo, anchor=tk.CENTER)
            else:
                # 无画面时显示黑色
                self.preview_canvas.delete("all")
                self.preview_canvas.create_rectangle(0, 0, self.preview_size[0], self.preview_size[1], 
                                                     fill='black', outline='')
        except Exception as e:
            pass  # 静默处理异常
        
        # 定时更新（约30fps）
        self.root.after(33, self.update_preview)
    
    def update_ui(self):
        """定时更新UI"""
        # 更新进度条
        if self.player.source_type == 'video' and self.player.playing:
            self.progress_var.set(self.player.current_frame_idx)
        
        # 更新状态
        if self.player.playing and not self.player.paused:
            self.play_btn.config(text="⏸ 暂停")
        else:
            self.play_btn.config(text="▶ 播放")
        
        self.root.after(100, self.update_ui)
    
    def run(self):
        """运行控制面板"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()
    
    def on_close(self):
        """关闭程序"""
        self.player.release()
        self.display.stop()
        self.root.destroy()


def main():
    """主函数"""
    app = ControlPanel()
    app.run()


if __name__ == "__main__":
    main()
