"""
显示窗口模块
负责在第二显示器上显示视频/图像
"""

import cv2
import numpy as np
import threading
import screeninfo


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
        self.monitor_changed = False # 标记显示器是否改变

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
        self.monitor_changed = True
    
    def get_monitor_info(self):
        """获取所有显示器信息"""
        return [(i, f"显示器 {i+1}: {m.width}x{m.height} @ ({m.x}, {m.y})") 
                for i, m in enumerate(self.monitors)]
    
    def create_window(self):
        """创建显示窗口"""
        # 尝试使用不同的后端，或者不指定后端
        try:
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        except cv2.error:
            # 如果默认后端失败，尝试不带标志
            cv2.namedWindow(self.window_name)
        
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
            if self.monitor_changed:
                self.create_window()
                self.monitor_changed = False

            with self.lock:
                current_frame = self.frame.copy() if self.frame is not None else None
            
            if current_frame is not None:
                display_frame = self.transform_frame(current_frame)
                if display_frame is not None:
                    cv2.imshow(self.window_name, display_frame)
            else:
                # 显示背景颜色
                bg = np.full((self.target_monitor.height, self.target_monitor.width, 3), 
                            self.background_color, dtype=np.uint8)
                cv2.imshow(self.window_name, bg)
            
            key = cv2.waitKey(16)  # ~60fps
            if key == 27:  # ESC键退出
                self.running = False
        
        cv2.destroyWindow(self.window_name)
    
    def stop(self):
        """停止显示"""
        self.running = False
