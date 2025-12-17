"""
视频播放器模块
负责视频、图像、摄像头和红外摄像头的播放控制
"""

import cv2
import threading
import asyncio
import time

from .ir_camera import IR_CAMERA_AVAILABLE, IRCameraController


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
        self.source_type = None  # 'video', 'image', 'camera', 'ir_camera'
        self.static_frame = None
        self.play_thread = None
        
        # 红外摄像头相关
        self.ir_controller = None
        self.ir_loop = None
    
    def load_video(self, path):
        """加载视频文件"""
        self.stop()  # 先停止播放
        self.stop_ir_camera()  # 确保关闭红外摄像头
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
        self.stop_ir_camera()  # 确保关闭红外摄像头
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
        self.stop()  # 先停止播放
        self.stop_ir_camera()  # 确保关闭红外摄像头
        if self.cap is not None:
            self.cap.release()
        
        self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            return False
        
        self.fps = 30
        self.source_type = 'camera'
        return True
    
    def load_ir_camera(self, device_index=0):
        """加载红外摄像头"""
        if not IR_CAMERA_AVAILABLE:
            return False, "红外摄像头功能不可用（需要安装 winrt 相关包）"
        
        self.stop()
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        
        # 创建红外摄像头控制器
        self.ir_controller = IRCameraController()
        self.ir_loop = asyncio.new_event_loop()
        
        try:
            # 查找设备
            devices = self.ir_loop.run_until_complete(self.ir_controller.find_ir_cameras())
            if not devices:
                self.ir_controller = None
                self.ir_loop.close()
                self.ir_loop = None
                return False, "未找到红外摄像头设备"
            
            # 选择设备
            if device_index >= len(devices):
                device_index = 0
            
            if not self.ir_loop.run_until_complete(self.ir_controller.select_device(device_index)):
                self.ir_controller = None
                self.ir_loop.close()
                self.ir_loop = None
                return False, "无法初始化红外摄像头"
            
            # 开始捕获
            if not self.ir_loop.run_until_complete(self.ir_controller.start()):
                self.ir_controller = None
                self.ir_loop.close()
                self.ir_loop = None
                return False, "无法启动红外摄像头捕获"
            
            self.fps = 30
            self.source_type = 'ir_camera'
            
            return True, f"已连接: {devices[device_index].display_name}"
            
        except Exception as e:
            if self.ir_loop:
                self.ir_loop.close()
                self.ir_loop = None
            self.ir_controller = None
            return False, f"红外摄像头错误: {str(e)}"
    
    def stop_ir_camera(self):
        """停止红外摄像头并释放系统资源"""
        # 先设置标志让播放线程退出
        self.playing = False
        
        # 先停止红外控制器（设置 _running = False，让播放线程可以退出）
        if self.ir_controller is not None and self.ir_loop is not None:
            try:
                # 确保事件循环还在运行
                if not self.ir_loop.is_closed():
                    self.ir_loop.run_until_complete(self.ir_controller.stop())
            except Exception as e:
                print(f"停止红外摄像头时出错: {e}")
        
        # 然后等待播放线程结束
        if self.play_thread is not None:
            self.play_thread.join(timeout=2)
            self.play_thread = None
        
        # 最后关闭事件循环并清理引用
        if self.ir_loop is not None:
            try:
                if not self.ir_loop.is_closed():
                    self.ir_loop.close()
            except:
                pass
            self.ir_loop = None
        
        self.ir_controller = None
    
    def get_ir_devices(self):
        """获取红外摄像头设备列表"""
        if not IR_CAMERA_AVAILABLE:
            return []
        
        temp_controller = IRCameraController()
        temp_loop = asyncio.new_event_loop()
        try:
            devices = temp_loop.run_until_complete(temp_controller.find_ir_cameras())
            return [d.display_name for d in devices]
        except:
            return []
        finally:
            temp_loop.close()
    
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
        frame_duration = 1.0 / self.fps
        
        # 红外摄像头模式
        if self.source_type == 'ir_camera' and self.ir_controller is not None:
            while self.playing and self.ir_controller is not None and self.ir_controller.is_running:
                if self.paused:
                    time.sleep(0.05)
                    continue
                
                start_time = time.time()
                
                frame = self.ir_controller.get_frame()
                if frame is not None:
                    self.display.set_frame(frame)
                
                # 帧率控制
                elapsed = time.time() - start_time
                if elapsed < frame_duration:
                    time.sleep(frame_duration - elapsed)
            return
        
        # 普通摄像头/视频模式
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
        self.stop_ir_camera()
        if self.cap is not None:
            self.cap.release()
