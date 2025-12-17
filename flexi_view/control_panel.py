"""
控制面板模块
提供 GUI 控制界面
"""

import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import threading
import screeninfo
import os
import json
import asyncio
from PIL import Image, ImageTk

from .display import DisplayWindow
from .player import VideoPlayer
from .ir_camera import (
    IR_CAMERA_AVAILABLE, 
    IRFrameFilter, 
    IRMappingMode
)

# 仅在红外摄像头可用时导入相关类
if IR_CAMERA_AVAILABLE:
    from .ir_camera import MediaFrameSourceGroup, MediaFrameSourceKind


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
        self.preview_size = (800, 450)  # 预览窗口大小（更大的默认值）
        
        # 进度条拖动状态
        self.seeking = False
        self.was_playing_before_seek = False
        
        # 辅助矩形框设置
        self.guide_rect_enabled = False  # 是否启用辅助框
        self.guide_rect_x = 0  # 辅助框X偏移（相对于显示器中心）
        self.guide_rect_y = 0  # 辅助框Y偏移
        self.guide_rect_width = 800  # 辅助框宽度（像素）
        self.guide_rect_height = 600  # 辅助框高度
        self.guide_rect_color = "#00FF00"  # 辅助框颜色（绿色）
        
        # 方向键步进值（固定为5）
        self.offset_step = 5
        
        self.setup_ui()
        
        # 让窗口根据内容自适应大小
        self.root.update_idletasks()
        
        # 获取内容所需的大小
        req_width = self.root.winfo_reqwidth()
        req_height = self.root.winfo_reqheight()
        
        # 获取屏幕大小，限制最大尺寸
        monitors = screeninfo.get_monitors()
        if len(monitors) > 0:
            screen_height = monitors[0].height
            screen_width = monitors[0].width
            max_height = int(screen_height * 0.9)
            max_width = int(screen_width * 0.9)
            
            # 设置窗口大小（不超过屏幕限制）
            final_width = min(req_width + 30, max_width)
            final_height = min(req_height + 20, max_height)
            
            # 窗口居中
            pos_x = monitors[0].x + (screen_width - final_width) // 2
            pos_y = monitors[0].y + (screen_height - final_height) // 2
            
            self.root.geometry(f"{final_width}x{final_height}+{pos_x}+{pos_y}")
        else:
            self.root.geometry(f"{req_width + 30}x{req_height + 20}")
        
        # 设置最小尺寸
        self.root.minsize(800, 500)
        
        # 启动预览更新
        self.update_preview()
        
        # 延迟刷新摄像头列表（避免启动时阻塞UI）
        self.root.after(500, self._auto_refresh_cameras)
    
    def _auto_refresh_cameras(self):
        """自动刷新摄像头列表"""
        self.refresh_cameras()
        if IR_CAMERA_AVAILABLE:
            self.refresh_ir_cameras()
    
    def setup_ui(self):
        """设置用户界面"""
        # 创建主容器 - 左右两栏布局
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # === 左侧：预览区域 ===
        left_frame = ttk.Frame(main_container, padding="5")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH)
        
        # 预览窗口
        preview_frame = ttk.LabelFrame(left_frame, text="预览", padding="5")
        preview_frame.pack(fill=tk.BOTH, expand=True)
        
        preview_ctrl_frame = ttk.Frame(preview_frame)
        preview_ctrl_frame.pack(fill=tk.X, pady=2)
        
        self.preview_mode_var = tk.StringVar(value="处理后")
        self.preview_toggle_btn = ttk.Button(preview_ctrl_frame, text="显示: 处理后", 
                                              command=self.toggle_preview_mode)
        self.preview_toggle_btn.pack(side=tk.LEFT, padx=2)
        
        # 预览大小滑动条（固定16:9比例）
        ttk.Label(preview_ctrl_frame, text="大小:").pack(side=tk.LEFT, padx=(10, 2))
        self.preview_scale_var = tk.IntVar(value=800)  # 宽度值，默认最大
        self.preview_scale_slider = ttk.Scale(preview_ctrl_frame, from_=320, to=800, 
                                               variable=self.preview_scale_var,
                                               orient=tk.HORIZONTAL, length=120,
                                               command=self.on_preview_scale_change)
        self.preview_scale_slider.pack(side=tk.LEFT, padx=2)
        self.preview_size_label = ttk.Label(preview_ctrl_frame, text="800x450")
        self.preview_size_label.pack(side=tk.LEFT, padx=2)
        
        self.preview_canvas = tk.Canvas(preview_frame, width=800, height=450, bg='black')
        self.preview_canvas.pack(pady=5)
        
        self.preview_photo = None
        
        # 辅助框控制（放在预览下方）
        guide_frame = ttk.LabelFrame(left_frame, text="辅助定位框 (Shift+方向键)", padding="5")
        guide_frame.pack(fill=tk.X, pady=5)
        
        guide_enable_frame = ttk.Frame(guide_frame)
        guide_enable_frame.pack(fill=tk.X, pady=2)
        self.guide_rect_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(guide_enable_frame, text="显示辅助框", variable=self.guide_rect_var,
                       command=self.on_guide_rect_toggle).pack(side=tk.LEFT)
        
        # X位置
        guide_x_frame = ttk.Frame(guide_frame)
        guide_x_frame.pack(fill=tk.X, pady=2)
        ttk.Label(guide_x_frame, text="X:").pack(side=tk.LEFT)
        self.guide_x_var = tk.IntVar(value=0)
        ttk.Entry(guide_x_frame, textvariable=self.guide_x_var, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Scale(guide_x_frame, from_=-1000, to=1000, variable=self.guide_x_var,
                 orient=tk.HORIZONTAL, command=self.on_guide_pos_change).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Y位置
        guide_y_frame = ttk.Frame(guide_frame)
        guide_y_frame.pack(fill=tk.X, pady=2)
        ttk.Label(guide_y_frame, text="Y:").pack(side=tk.LEFT)
        self.guide_y_var = tk.IntVar(value=0)
        ttk.Entry(guide_y_frame, textvariable=self.guide_y_var, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Scale(guide_y_frame, from_=-1000, to=1000, variable=self.guide_y_var,
                 orient=tk.HORIZONTAL, command=self.on_guide_pos_change).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 宽度
        guide_w_frame = ttk.Frame(guide_frame)
        guide_w_frame.pack(fill=tk.X, pady=2)
        ttk.Label(guide_w_frame, text="宽:").pack(side=tk.LEFT)
        self.guide_w_var = tk.IntVar(value=800)
        ttk.Entry(guide_w_frame, textvariable=self.guide_w_var, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Scale(guide_w_frame, from_=100, to=2000, variable=self.guide_w_var,
                 orient=tk.HORIZONTAL, command=self.on_guide_size_change).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 高度
        guide_h_frame = ttk.Frame(guide_frame)
        guide_h_frame.pack(fill=tk.X, pady=2)
        ttk.Label(guide_h_frame, text="高:").pack(side=tk.LEFT)
        self.guide_h_var = tk.IntVar(value=600)
        ttk.Entry(guide_h_frame, textvariable=self.guide_h_var, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Scale(guide_h_frame, from_=100, to=2000, variable=self.guide_h_var,
                 orient=tk.HORIZONTAL, command=self.on_guide_size_change).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 状态栏
        self.status_label = ttk.Label(left_frame, text="就绪")
        self.status_label.pack(fill=tk.X, pady=5)
        
        # === 右侧：设置区域 ===
        right_frame = ttk.Frame(main_container, padding="5")
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 右侧设置框架
        main_frame = right_frame
        
        # === 显示源（合并媒体源和摄像头选择）===
        source_frame = ttk.LabelFrame(main_frame, text="显示源", padding="5")
        source_frame.pack(fill=tk.X, pady=5)
        
        # 文件选择
        file_btn_frame = ttk.Frame(source_frame)
        file_btn_frame.pack(fill=tk.X, pady=2)
        ttk.Label(file_btn_frame, text="文件:").pack(side=tk.LEFT)
        ttk.Button(file_btn_frame, text="无", command=self.clear_source, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_btn_frame, text="视频", command=self.open_video, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_btn_frame, text="图片", command=self.open_image, width=6).pack(side=tk.LEFT, padx=2)
        
        self.file_label = ttk.Label(source_frame, text="未选择文件")
        self.file_label.pack(fill=tk.X, pady=2)
        
        ttk.Separator(source_frame, orient='horizontal').pack(fill=tk.X, pady=5)
        
        # RGB摄像头选择
        rgb_frame = ttk.Frame(source_frame)
        rgb_frame.pack(fill=tk.X, pady=2)
        ttk.Label(rgb_frame, text="RGB:").pack(side=tk.LEFT)
        self.camera_var = tk.StringVar(value="点击刷新")
        self.camera_combo = ttk.Combobox(rgb_frame, textvariable=self.camera_var, state="readonly", width=15)
        self.camera_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(rgb_frame, text="刷新", command=self.refresh_cameras, width=5).pack(side=tk.LEFT)
        ttk.Button(rgb_frame, text="打开", command=self.open_selected_camera, width=5).pack(side=tk.LEFT, padx=2)
        
        # 初始化摄像头列表（延迟刷新，避免启动时卡顿）
        self.available_cameras = []
        
        # 红外摄像头选择（仅在支持时显示）
        if IR_CAMERA_AVAILABLE:
            ir_cam_frame = ttk.Frame(source_frame)
            ir_cam_frame.pack(fill=tk.X, pady=2)
            ttk.Label(ir_cam_frame, text="红外:").pack(side=tk.LEFT)
            self.ir_camera_var = tk.StringVar(value="点击刷新")
            self.ir_camera_combo = ttk.Combobox(ir_cam_frame, textvariable=self.ir_camera_var, state="readonly", width=15)
            self.ir_camera_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
            ttk.Button(ir_cam_frame, text="刷新", command=self.refresh_ir_cameras, width=5).pack(side=tk.LEFT)
            ttk.Button(ir_cam_frame, text="打开", command=self.open_selected_ir_camera, width=5).pack(side=tk.LEFT, padx=2)
            
            # 初始化红外摄像头列表（延迟刷新，避免启动时卡顿）
            self.available_ir_cameras = []
        
        # === 红外摄像头控制（仅在支持时显示）===
        if IR_CAMERA_AVAILABLE:
            self.ir_frame = ttk.LabelFrame(main_frame, text="红外摄像头设置", padding="5")
            # 初始隐藏，打开红外摄像头时显示
            
            # 帧过滤
            ir_filter_frame = ttk.Frame(self.ir_frame)
            ir_filter_frame.pack(fill=tk.X, pady=2)
            ttk.Label(ir_filter_frame, text="帧过滤:").pack(side=tk.LEFT)
            self.ir_filter_var = tk.StringVar(value="全部")
            self.ir_filter_combo = ttk.Combobox(ir_filter_frame, textvariable=self.ir_filter_var, 
                                                 state="readonly", width=10)
            self.ir_filter_combo['values'] = ["全部", "原始", "照明"]
            self.ir_filter_combo.pack(side=tk.LEFT, padx=5)
            self.ir_filter_combo.bind("<<ComboboxSelected>>", self.on_ir_filter_change)
            
            # 颜色映射
            ir_color_frame = ttk.Frame(self.ir_frame)
            ir_color_frame.pack(fill=tk.X, pady=2)
            ttk.Label(ir_color_frame, text="颜色映射:").pack(side=tk.LEFT)
            self.ir_color_var = tk.StringVar(value="原始")
            self.ir_color_combo = ttk.Combobox(ir_color_frame, textvariable=self.ir_color_var,
                                                state="readonly", width=10)
            self.ir_color_combo['values'] = ["原始", "绿色", "热力", "JET"]
            self.ir_color_combo.pack(side=tk.LEFT, padx=5)
            self.ir_color_combo.bind("<<ComboboxSelected>>", self.on_ir_color_change)
        
        # === 显示器选择与控制 ===
        monitor_frame = ttk.LabelFrame(main_frame, text="显示器", padding="5")
        monitor_frame.pack(fill=tk.X, pady=5)
        
        self.monitor_var = tk.StringVar()
        self.monitor_combo = ttk.Combobox(monitor_frame, textvariable=self.monitor_var, state="readonly")
        self.monitor_combo.pack(fill=tk.X)
        self.update_monitor_list()
        self.monitor_combo.bind("<<ComboboxSelected>>", self.on_monitor_change)
        
        monitor_btn_frame = ttk.Frame(monitor_frame)
        monitor_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(monitor_btn_frame, text="刷新列表", command=self.update_monitor_list).pack(side=tk.LEFT, padx=2)
        self.display_btn = ttk.Button(monitor_btn_frame, text="启动显示窗口", command=self.toggle_display)
        self.display_btn.pack(side=tk.LEFT, padx=2)
        
        # === 播放控制 ===
        play_frame = ttk.LabelFrame(main_frame, text="播放控制", padding="5")
        play_frame.pack(fill=tk.X, pady=5)
        
        play_btn_frame = ttk.Frame(play_frame)
        play_btn_frame.pack(fill=tk.X)
        
        self.play_btn = ttk.Button(play_btn_frame, text="▶ 播放", command=self.toggle_play)
        self.play_btn.pack(side=tk.LEFT, padx=2)
        
        self.loop_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(play_btn_frame, text="循环播放", variable=self.loop_var,
                       command=self.toggle_loop).pack(side=tk.LEFT, padx=10)
        
        # 进度条
        progress_frame = ttk.Frame(play_frame)
        progress_frame.pack(fill=tk.X, pady=5)
        
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_scale = tk.Scale(progress_frame, from_=0, to=100, 
                                       variable=self.progress_var, orient=tk.HORIZONTAL,
                                       showvalue=False, sliderlength=15, length=200)
        self.progress_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.progress_scale.bind("<Button-1>", self.on_seek_start)
        self.progress_scale.bind("<ButtonRelease-1>", self.on_seek_end)
        self.progress_scale.bind("<B1-Motion>", self.on_seeking)
        
        # 时间标签
        self.time_label = ttk.Label(progress_frame, text="0/0", width=12)
        self.time_label.pack(side=tk.LEFT)
        
        # === 变换控制 ===
        transform_frame = ttk.LabelFrame(main_frame, text="变换控制", padding="5")
        transform_frame.pack(fill=tk.X, pady=5)
        
        # 缩放
        scale_frame = ttk.Frame(transform_frame)
        scale_frame.pack(fill=tk.X, pady=2)
        ttk.Label(scale_frame, text="缩放:").pack(side=tk.LEFT)
        self.scale_var = tk.DoubleVar(value=1.0)
        self.scale_entry = ttk.Entry(scale_frame, textvariable=self.scale_var, width=8)
        self.scale_entry.pack(side=tk.LEFT, padx=5)
        self.scale_entry.bind('<Return>', self.on_scale_entry_change)
        self.scale_entry.bind('<FocusOut>', self.on_scale_entry_change)
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
        
        # 快捷旋转
        quick_rotation_frame = ttk.Frame(transform_frame)
        quick_rotation_frame.pack(fill=tk.X, pady=5)
        ttk.Label(quick_rotation_frame, text="快捷旋转:").pack(side=tk.LEFT)
        for angle in [0, 90, 180, 270]:
            ttk.Button(quick_rotation_frame, text=f"{angle}°", width=5,
                      command=lambda a=angle: self.set_rotation(a)).pack(side=tk.LEFT, padx=2)
        
        # 镜像控制
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
        
        # 颜色预览方块
        self.bg_color_preview = tk.Canvas(bg_btn_frame, width=30, height=25, bg='black', 
                                          highlightthickness=1, highlightbackground='gray')
        self.bg_color_preview.pack(side=tk.LEFT, padx=2)
        
        # 选择颜色按钮
        ttk.Button(bg_btn_frame, text="选择颜色", command=self.choose_bg_color).pack(side=tk.LEFT, padx=2)
        
        # 快捷颜色按钮
        ttk.Button(bg_btn_frame, text="黑", width=3, command=lambda: self.set_bg_color(0, 0, 0)).pack(side=tk.LEFT, padx=1)
        ttk.Button(bg_btn_frame, text="白", width=3, command=lambda: self.set_bg_color(255, 255, 255)).pack(side=tk.LEFT, padx=1)
        ttk.Button(bg_btn_frame, text="绿", width=3, command=lambda: self.set_bg_color(0, 255, 0)).pack(side=tk.LEFT, padx=1)
        
        # === 配置保存/加载 ===
        config_frame = ttk.LabelFrame(main_frame, text="配置管理", padding="5")
        config_frame.pack(fill=tk.X, pady=5)
        
        config_btn_frame = ttk.Frame(config_frame)
        config_btn_frame.pack(fill=tk.X)
        
        ttk.Button(config_btn_frame, text="保存配置", command=self.save_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(config_btn_frame, text="加载配置", command=self.load_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(config_btn_frame, text="快速保存", command=self.quick_save_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(config_btn_frame, text="快速加载", command=self.quick_load_config).pack(side=tk.LEFT, padx=2)
        
        # 绑定方向键
        self.root.bind("<Up>", self.on_key_up)
        self.root.bind("<Down>", self.on_key_down)
        self.root.bind("<Left>", self.on_key_left)
        self.root.bind("<Right>", self.on_key_right)
        self.root.bind("<Shift-Up>", self.on_shift_key_up)
        self.root.bind("<Shift-Down>", self.on_shift_key_down)
        self.root.bind("<Shift-Left>", self.on_shift_key_left)
        self.root.bind("<Shift-Right>", self.on_shift_key_right)
        
        # 定时更新UI
        self.update_ui()
    
    # ==================== 显示器管理 ====================
    
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
    
    # ==================== 媒体源管理 ====================
    
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
                if IR_CAMERA_AVAILABLE:
                    self.ir_frame.pack_forget()
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
                if IR_CAMERA_AVAILABLE:
                    self.ir_frame.pack_forget()
            else:
                messagebox.showerror("错误", "无法打开图像文件")
    
    def clear_source(self):
        """清除媒体源"""
        self.player.stop()
        self.player.release()
        self.display.set_frame(None)
        self.file_label.config(text="无")
        self.status_label.config(text="已清除媒体源")
        if IR_CAMERA_AVAILABLE:
            self.ir_frame.pack_forget()
    
    # ==================== 摄像头管理 ====================
    
    def refresh_cameras(self):
        """刷新RGB摄像头列表"""
        self.available_cameras = []
        
        # 使用 PowerShell 获取摄像头名称列表
        camera_names = []
        try:
            import subprocess
            result = subprocess.run(
                ['powershell', '-Command', 
                 'Get-PnpDevice -Class Camera -Status OK | Select-Object -ExpandProperty FriendlyName'],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                camera_names = [n.strip() for n in result.stdout.strip().split('\n') if n.strip()]
        except Exception:
            pass
        
        # 根据获取到的摄像头数量来确定扫描范围
        if camera_names:
            for i, name in enumerate(camera_names):
                self.available_cameras.append({'id': i, 'name': name})
        
        if self.available_cameras:
            values = [cam['name'] for cam in self.available_cameras]
            self.camera_combo['values'] = values
            self.camera_combo.current(0)
        else:
            self.camera_combo['values'] = ["未检测到摄像头"]
            self.camera_var.set("未检测到摄像头")
        
        self.status_label.config(text=f"检测到 {len(self.available_cameras)} 个RGB摄像头")
    
    def open_selected_camera(self):
        """打开选中的RGB摄像头"""
        if not self.available_cameras:
            messagebox.showerror("错误", "没有可用的摄像头")
            return
        
        try:
            idx = self.camera_combo.current()
            if idx < 0 or idx >= len(self.available_cameras):
                messagebox.showerror("错误", "请选择一个摄像头")
                return
            
            camera_info = self.available_cameras[idx]
            camera_id = camera_info['id']
            camera_name = camera_info['name']
            if self.player.load_camera(camera_id):
                self.file_label.config(text=camera_name)
                self.status_label.config(text=f"{camera_name} 已连接")
                self.player.play()
                if IR_CAMERA_AVAILABLE:
                    self.ir_frame.pack_forget()
            else:
                messagebox.showerror("错误", f"无法打开 {camera_name}")
        except Exception as e:
            messagebox.showerror("错误", f"打开摄像头失败: {e}")
    
    def refresh_ir_cameras(self):
        """刷新红外摄像头列表"""
        if not IR_CAMERA_AVAILABLE:
            return
        
        self.available_ir_cameras = []
        
        async def get_ir_cameras():
            cameras = []
            try:
                source_groups = await MediaFrameSourceGroup.find_all_async()
                for i, group in enumerate(source_groups):
                    for source_info in group.source_infos:
                        if source_info.source_kind == MediaFrameSourceKind.INFRARED:
                            cameras.append({
                                'index': i,
                                'name': group.display_name,
                                'id': group.id
                            })
                            break
            except Exception as e:
                print(f"枚举红外摄像头失败: {e}")
            return cameras
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.available_ir_cameras = loop.run_until_complete(get_ir_cameras())
            loop.close()
        except Exception as e:
            print(f"获取红外摄像头列表失败: {e}")
        
        if self.available_ir_cameras:
            values = [f"{cam['name']}" for cam in self.available_ir_cameras]
            self.ir_camera_combo['values'] = values
            self.ir_camera_combo.current(0)
        else:
            self.ir_camera_combo['values'] = ["未检测到红外摄像头"]
            self.ir_camera_var.set("未检测到红外摄像头")
        
        self.status_label.config(text=f"检测到 {len(self.available_ir_cameras)} 个红外摄像头")
    
    def open_selected_ir_camera(self):
        """打开选中的红外摄像头"""
        if not IR_CAMERA_AVAILABLE:
            messagebox.showerror("错误", "红外摄像头功能不可用")
            return
        
        if not self.available_ir_cameras:
            messagebox.showerror("错误", "没有可用的红外摄像头")
            return
        
        try:
            idx = self.ir_camera_combo.current()
            if idx < 0 or idx >= len(self.available_ir_cameras):
                messagebox.showerror("错误", "请选择一个红外摄像头")
                return
            
            camera_info = self.available_ir_cameras[idx]
            success, message = self.player.load_ir_camera(idx)
            if success:
                self.file_label.config(text=f"红外: {camera_info['name']}")
                self.status_label.config(text=message)
                self.player.play()
                self.ir_frame.pack(fill=tk.X, pady=5, after=self.file_label.master)
            else:
                messagebox.showerror("错误", message)
        except Exception as e:
            messagebox.showerror("错误", f"打开红外摄像头失败: {e}")
    
    # ==================== 红外摄像头控制 ====================
    
    def on_ir_filter_change(self, event=None):
        """红外帧过滤改变"""
        if self.player.ir_controller is None:
            return
        filter_map = {"全部": IRFrameFilter.NONE, "原始": IRFrameFilter.RAW, "照明": IRFrameFilter.ILLUMINATED}
        self.player.ir_controller.frame_filter = filter_map.get(self.ir_filter_var.get(), IRFrameFilter.NONE)
    
    def on_ir_color_change(self, event=None):
        """红外颜色映射改变"""
        if self.player.ir_controller is None:
            return
        color_map = {"原始": IRMappingMode.NONE, "绿色": IRMappingMode.GREEN,
                     "热力": IRMappingMode.HEAT, "JET": IRMappingMode.JET}
        self.player.ir_controller.mapping_mode = color_map.get(self.ir_color_var.get(), IRMappingMode.NONE)
    
    # ==================== 播放控制 ====================
    
    def toggle_play(self):
        """切换播放/停止状态"""
        if self.player.playing:
            # 正在播放，停止
            self.player.stop()
            self.play_btn.config(text="▶ 播放")
        else:
            # 未播放，开始播放
            self.player.play()
            self.play_btn.config(text="■ 停止")
            # 更新进度条范围
            if self.player.source_type == 'video' and self.player.total_frames > 0:
                self.progress_scale.config(to=self.player.total_frames)
    
    def toggle_loop(self):
        """切换循环播放"""
        self.player.loop = self.loop_var.get()
    
    def on_seek_start(self, event):
        """开始拖动进度条"""
        self.seeking = True
        # 记录拖动前的播放状态，并暂停
        self.was_playing_before_seek = self.player.playing
        if self.player.playing:
            self.player.pause()
    
    def on_seeking(self, event):
        """正在拖动进度条 - 实时预览"""
        if self.player.source_type == 'video':
            frame_idx = int(self.progress_scale.get())
            self.player.seek(frame_idx)
    
    def on_seek_end(self, event):
        """结束拖动进度条"""
        if self.player.source_type == 'video':
            frame_idx = int(self.progress_scale.get())
            self.player.seek(frame_idx)
        self.seeking = False
        # 如果之前在播放，恢复播放
        if hasattr(self, 'was_playing_before_seek') and self.was_playing_before_seek:
            self.player.resume()
    
    # ==================== 变换控制 ====================
    
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
    
    def set_bg_color(self, r, g, b):
        """设置背景颜色 (RGB格式输入，内部转BGR存储)"""
        self.display.background_color = (b, g, r)  # OpenCV使用BGR格式
        # 更新颜色预览
        hex_color = f'#{r:02x}{g:02x}{b:02x}'
        self.bg_color_preview.config(bg=hex_color)
    
    def choose_bg_color(self):
        """打开颜色选择器选择背景颜色"""
        # 获取当前颜色作为初始值
        b, g, r = self.display.background_color
        initial_color = f'#{r:02x}{g:02x}{b:02x}'
        
        color = colorchooser.askcolor(color=initial_color, title="选择背景颜色")
        if color[0] is not None:
            r, g, b = [int(c) for c in color[0]]
            self.set_bg_color(r, g, b)
    
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
    
    # ==================== 配置管理 ====================
    
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
            'monitor_index': self.display.monitor_index,
            'guide_rect_enabled': self.guide_rect_enabled,
            'guide_rect_x': self.guide_rect_x,
            'guide_rect_y': self.guide_rect_y,
            'guide_rect_width': self.guide_rect_width,
            'guide_rect_height': self.guide_rect_height
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
            # 更新颜色预览
            b, g, r = self.display.background_color
            hex_color = f'#{r:02x}{g:02x}{b:02x}'
            self.bg_color_preview.config(bg=hex_color)
        if 'monitor_index' in config:
            self.display.update_monitor(config['monitor_index'])
            self.update_monitor_list()
        if 'guide_rect_enabled' in config:
            self.guide_rect_enabled = config['guide_rect_enabled']
            self.guide_rect_var.set(config['guide_rect_enabled'])
        if 'guide_rect_x' in config:
            self.guide_rect_x = config['guide_rect_x']
            self.guide_x_var.set(config['guide_rect_x'])
        if 'guide_rect_y' in config:
            self.guide_rect_y = config['guide_rect_y']
            self.guide_y_var.set(config['guide_rect_y'])
        if 'guide_rect_width' in config:
            self.guide_rect_width = config['guide_rect_width']
            self.guide_w_var.set(config['guide_rect_width'])
        if 'guide_rect_height' in config:
            self.guide_rect_height = config['guide_rect_height']
            self.guide_h_var.set(config['guide_rect_height'])
    
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
        """快速保存配置"""
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'flexi_view_config.json')
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.get_config(), f, indent=2, ensure_ascii=False)
            self.status_label.config(text="配置已快速保存")
        except Exception as e:
            messagebox.showerror("错误", f"快速保存失败: {e}")
    
    def quick_load_config(self):
        """快速加载配置"""
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'flexi_view_config.json')
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
    
    # ==================== 显示控制 ====================
    
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
    
    # ==================== 预览控制 ====================
    
    def toggle_preview_mode(self):
        """切换预览模式"""
        self.preview_show_processed = not self.preview_show_processed
        if self.preview_show_processed:
            self.preview_toggle_btn.config(text="显示: 处理后")
        else:
            self.preview_toggle_btn.config(text="显示: 原始")
    
    def on_preview_scale_change(self, value=None):
        """预览大小滑动条改变（固定16:9比例）"""
        w = int(self.preview_scale_var.get())
        h = int(w * 9 / 16)  # 16:9 比例
        self.preview_size = (w, h)
        self.preview_canvas.config(width=w, height=h)
        self.preview_size_label.config(text=f"{w}x{h}")
    
    # ==================== 辅助框控制 ====================
    
    def on_guide_rect_toggle(self):
        """切换辅助框显示"""
        self.guide_rect_enabled = self.guide_rect_var.get()
    
    def on_guide_pos_change(self, value=None):
        """辅助框位置改变"""
        self.guide_rect_x = self.guide_x_var.get()
        self.guide_rect_y = self.guide_y_var.get()
    
    def on_guide_size_change(self, value=None):
        """辅助框大小改变"""
        self.guide_rect_width = self.guide_w_var.get()
        self.guide_rect_height = self.guide_h_var.get()
    
    # ==================== 快捷键 ====================
    
    def on_key_up(self, event=None):
        new_y = self.offset_y_var.get() - self.offset_step
        self.offset_y_var.set(new_y)
        self.display.offset_y = new_y
    
    def on_key_down(self, event=None):
        new_y = self.offset_y_var.get() + self.offset_step
        self.offset_y_var.set(new_y)
        self.display.offset_y = new_y
    
    def on_key_left(self, event=None):
        new_x = self.offset_x_var.get() - self.offset_step
        self.offset_x_var.set(new_x)
        self.display.offset_x = new_x
    
    def on_key_right(self, event=None):
        new_x = self.offset_x_var.get() + self.offset_step
        self.offset_x_var.set(new_x)
        self.display.offset_x = new_x
    
    def on_shift_key_up(self, event=None):
        new_y = self.guide_y_var.get() - self.offset_step
        self.guide_y_var.set(new_y)
        self.guide_rect_y = new_y
        return "break"
    
    def on_shift_key_down(self, event=None):
        new_y = self.guide_y_var.get() + self.offset_step
        self.guide_y_var.set(new_y)
        self.guide_rect_y = new_y
        return "break"
    
    def on_shift_key_left(self, event=None):
        new_x = self.guide_x_var.get() - self.offset_step
        self.guide_x_var.set(new_x)
        self.guide_rect_x = new_x
        return "break"
    
    def on_shift_key_right(self, event=None):
        new_x = self.guide_x_var.get() + self.offset_step
        self.guide_x_var.set(new_x)
        self.guide_rect_x = new_x
        return "break"
    
    # ==================== 预览更新 ====================
    
    def update_preview(self):
        """更新预览画面"""
        try:
            with self.display.lock:
                current_frame = self.display.frame.copy() if self.display.frame is not None else None
            
            if current_frame is not None:
                preview_w, preview_h = self.preview_size
                
                if self.preview_show_processed:
                    frame = current_frame.copy()
                    h, w = frame.shape[:2]
                    
                    if self.display.mirror_h and self.display.mirror_v:
                        frame = cv2.flip(frame, -1)
                    elif self.display.mirror_h:
                        frame = cv2.flip(frame, 1)
                    elif self.display.mirror_v:
                        frame = cv2.flip(frame, 0)
                    
                    monitor_w = self.display.target_monitor.width
                    monitor_h = self.display.target_monitor.height
                    preview_scale = min(preview_w / monitor_w, preview_h / monitor_h)
                    
                    scaled_w = int(w * self.display.scale * preview_scale)
                    scaled_h = int(h * self.display.scale * preview_scale)
                    
                    if scaled_w > 0 and scaled_h > 0:
                        frame = cv2.resize(frame, (scaled_w, scaled_h), interpolation=cv2.INTER_LINEAR)
                    
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
                    
                    preview_img = np.full((preview_h, preview_w, 3), self.display.background_color, dtype=np.uint8)
                    
                    rh, rw = frame.shape[:2]
                    x = int((preview_w - rw) / 2 + self.display.offset_x * preview_scale)
                    y = int((preview_h - rh) / 2 + self.display.offset_y * preview_scale)
                    
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
                
                preview_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(preview_rgb)
                self.preview_photo = ImageTk.PhotoImage(pil_image)
                
                self.preview_canvas.delete("all")
                self.preview_canvas.create_image(preview_w//2, preview_h//2, 
                                                 image=self.preview_photo, anchor=tk.CENTER)
                
                if self.guide_rect_enabled and self.preview_show_processed:
                    monitor_w = self.display.target_monitor.width
                    monitor_h = self.display.target_monitor.height
                    preview_scale = min(preview_w / monitor_w, preview_h / monitor_h)
                    
                    rect_center_x = preview_w / 2 + self.guide_rect_x * preview_scale
                    rect_center_y = preview_h / 2 + self.guide_rect_y * preview_scale
                    rect_w = self.guide_rect_width * preview_scale
                    rect_h = self.guide_rect_height * preview_scale
                    
                    rect_x1 = rect_center_x - rect_w / 2
                    rect_y1 = rect_center_y - rect_h / 2
                    rect_x2 = rect_center_x + rect_w / 2
                    rect_y2 = rect_center_y + rect_h / 2
                    
                    self.preview_canvas.create_rectangle(
                        rect_x1, rect_y1, rect_x2, rect_y2,
                        outline=self.guide_rect_color, width=2
                    )
            else:
                # 没有媒体源时显示背景色
                preview_w, preview_h = self.preview_size
                self.preview_canvas.delete("all")
                
                # 将背景颜色从BGR转换为十六进制
                bg_color = self.display.background_color
                hex_color = f'#{bg_color[2]:02x}{bg_color[1]:02x}{bg_color[0]:02x}'
                self.preview_canvas.create_rectangle(0, 0, preview_w, preview_h, 
                                                     fill=hex_color, outline='')
                
                # 即使没有媒体源也绘制辅助框
                if self.guide_rect_enabled:
                    monitor_w = self.display.target_monitor.width
                    monitor_h = self.display.target_monitor.height
                    preview_scale = min(preview_w / monitor_w, preview_h / monitor_h)
                    
                    rect_center_x = preview_w / 2 + self.guide_rect_x * preview_scale
                    rect_center_y = preview_h / 2 + self.guide_rect_y * preview_scale
                    rect_w = self.guide_rect_width * preview_scale
                    rect_h = self.guide_rect_height * preview_scale
                    
                    rect_x1 = rect_center_x - rect_w / 2
                    rect_y1 = rect_center_y - rect_h / 2
                    rect_x2 = rect_center_x + rect_w / 2
                    rect_y2 = rect_center_y + rect_h / 2
                    
                    self.preview_canvas.create_rectangle(
                        rect_x1, rect_y1, rect_x2, rect_y2,
                        outline=self.guide_rect_color, width=2
                    )
        except Exception:
            pass
        
        self.root.after(33, self.update_preview)
    
    def update_ui(self):
        """定时更新UI"""
        # 更新播放按钮状态
        if self.player.playing:
            self.play_btn.config(text="■ 停止")
        else:
            self.play_btn.config(text="▶ 播放")
        
        # 更新视频进度条和时间标签（拖动时不更新进度条）
        if self.player.source_type == 'video':
            if self.player.total_frames > 0:
                self.progress_scale.config(to=self.player.total_frames)
            # 只有在不拖动时才更新进度条位置
            if not self.seeking:
                self.progress_var.set(self.player.current_frame_idx)
            # 更新时间标签（显示帧数）
            self.time_label.config(text=f"{self.player.current_frame_idx}/{self.player.total_frames}")
        else:
            self.time_label.config(text="--/--")
        
        self.root.after(100, self.update_ui)
    
    # ==================== 运行 ====================
    
    def run(self):
        """运行控制面板"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()
    
    def on_close(self):
        """关闭程序"""
        self.player.release()
        self.display.stop()
        self.root.destroy()
