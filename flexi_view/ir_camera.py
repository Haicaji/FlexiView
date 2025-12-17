"""
红外摄像头模块
支持 Windows 平台的红外摄像头捕获和处理
"""

import cv2
import numpy as np
from enum import Enum
from threading import Lock
from queue import Queue, Empty

# Windows Runtime 红外摄像头支持（仅 Windows 平台可用）
IR_CAMERA_AVAILABLE = False
MediaFrameSourceGroup = None
MediaFrameSourceKind = None

try:
    from winrt.windows.media.capture import (
        MediaCapture,
        MediaCaptureInitializationSettings,
        MediaCaptureSharingMode,
        StreamingCaptureMode,
        MediaCaptureMemoryPreference,
    )
    from winrt.windows.media.capture.frames import (
        MediaFrameSourceGroup,
        MediaFrameSourceKind,
        MediaFrameReaderAcquisitionMode,
    )
    from winrt.windows.graphics.imaging import (
        SoftwareBitmap,
        BitmapPixelFormat,
        BitmapBufferAccessMode,
    )
    IR_CAMERA_AVAILABLE = True
except ImportError:
    pass  # 红外摄像头功能不可用


class IRFrameFilter(Enum):
    """帧过滤模式
    
    红外摄像头会交替发送照明帧和原始帧：
    - 照明帧：红外 LED 开启时捕获
    - 原始帧：红外 LED 关闭时捕获
    """
    NONE = 0        # 不过滤，显示所有帧
    RAW = 1         # 仅显示原始帧（LED 关闭）
    ILLUMINATED = 2  # 仅显示照明帧（LED 开启）
    
    def next(self):
        """获取下一个过滤模式"""
        members = list(self.__class__)
        idx = (self.value + 1) % len(members)
        return members[idx]
    
    @property
    def display_name(self):
        """显示名称"""
        names = {
            IRFrameFilter.NONE: "全部",
            IRFrameFilter.RAW: "原始",
            IRFrameFilter.ILLUMINATED: "照明"
        }
        return names.get(self, "全部")


class IRMappingMode(Enum):
    """颜色映射模式"""
    NONE = 0        # 原始灰度
    GREEN = 1       # 绿色映射
    HEAT = 2        # 热力图
    JET = 3         # Jet 色彩映射
    
    def next(self):
        """获取下一个映射模式"""
        members = list(self.__class__)
        idx = (self.value + 1) % len(members)
        return members[idx]
    
    @property
    def display_name(self):
        """显示名称"""
        names = {
            IRMappingMode.NONE: "原始",
            IRMappingMode.GREEN: "绿色",
            IRMappingMode.HEAT: "热力",
            IRMappingMode.JET: "JET"
        }
        return names.get(self, "原始")


class IRCameraController:
    """红外摄像头控制器
    
    负责：
    - 设备发现和选择
    - 帧捕获和处理
    - 帧过滤和颜色映射
    """

    def __init__(self):
        if not IR_CAMERA_AVAILABLE:
            raise RuntimeError("红外摄像头功能不可用（需要安装 winrt 相关包）")
        
        # 媒体捕获相关
        self._media_capture = None
        self._frame_reader = None
        self._lock = Lock()
        self._running = False
        
        # 帧队列
        self._frame_queue = Queue(maxsize=2)
        self._last_frame = None
        
        # 设备信息
        self._devices = []
        self._current_device_index = 0
        self._frame_width = 640
        self._frame_height = 480
        
        # 处理选项
        self._frame_filter = IRFrameFilter.NONE
        self._mapping_mode = IRMappingMode.NONE
        self._is_illuminated = False

    # ==================== 属性 ====================
    
    @property
    def frame_filter(self) -> IRFrameFilter:
        return self._frame_filter
    
    @frame_filter.setter
    def frame_filter(self, value: IRFrameFilter):
        self._frame_filter = value

    @property
    def mapping_mode(self) -> IRMappingMode:
        return self._mapping_mode
    
    @mapping_mode.setter
    def mapping_mode(self, value: IRMappingMode):
        self._mapping_mode = value

    @property
    def devices(self) -> list:
        return self._devices

    @property
    def current_device_index(self) -> int:
        return self._current_device_index

    @property
    def frame_size(self) -> tuple:
        return (self._frame_width, self._frame_height)

    @property
    def is_running(self) -> bool:
        return self._running

    # ==================== 设备管理 ====================

    async def find_ir_cameras(self) -> list:
        """查找所有红外摄像头设备"""
        if not IR_CAMERA_AVAILABLE:
            return []
        
        self._devices = []
        devices = await MediaFrameSourceGroup.find_all_async()
        
        for device in devices:
            source_infos = device.source_infos
            if source_infos and len(source_infos) > 0:
                for source_info in source_infos:
                    if source_info.source_kind == MediaFrameSourceKind.INFRARED:
                        self._devices.append(device)
                        break
        
        return self._devices

    def get_device_names(self) -> list:
        """获取设备名称列表"""
        return [d.display_name for d in self._devices]

    async def select_device(self, index: int, exclusive: bool = False) -> bool:
        """选择指定索引的设备"""
        if not IR_CAMERA_AVAILABLE:
            return False
        
        if index < 0 or index >= len(self._devices):
            return False
        
        # 停止当前捕获
        if self._frame_reader is not None:
            await self.stop()
        
        device = self._devices[index]
        self._current_device_index = index
        
        # 初始化 MediaCapture
        self._media_capture = MediaCapture()
        
        settings = MediaCaptureInitializationSettings()
        settings.source_group = device
        settings.sharing_mode = (MediaCaptureSharingMode.EXCLUSIVE_CONTROL 
                                 if exclusive else MediaCaptureSharingMode.SHARED_READ_ONLY)
        settings.streaming_capture_mode = StreamingCaptureMode.VIDEO
        settings.memory_preference = MediaCaptureMemoryPreference.CPU
        
        try:
            await self._media_capture.initialize_with_settings_async(settings)
        except Exception:
            if exclusive:
                # 尝试共享模式
                settings.sharing_mode = MediaCaptureSharingMode.SHARED_READ_ONLY
                await self._media_capture.initialize_with_settings_async(settings)
            else:
                raise
        
        # 获取帧源
        frame_sources = self._media_capture.frame_sources
        if not frame_sources:
            return False
        
        frame_source = next(iter(frame_sources.values()), None)
        if frame_source is None:
            return False
        
        # 选择最佳格式
        supported_formats = frame_source.supported_formats
        if supported_formats and len(supported_formats) > 0:
            best_format = max(
                supported_formats,
                key=lambda f: f.video_format.width * f.video_format.height
            )
            await frame_source.set_format_async(best_format)
            self._frame_width = best_format.video_format.width
            self._frame_height = best_format.video_format.height
        
        # 创建帧读取器
        self._frame_reader = await self._media_capture.create_frame_reader_async(frame_source)
        self._frame_reader.acquisition_mode = MediaFrameReaderAcquisitionMode.REALTIME
        self._frame_reader.add_frame_arrived(self._on_frame_arrived)
        
        return True

    # ==================== 捕获控制 ====================

    async def start(self) -> bool:
        """开始捕获"""
        if self._frame_reader is None:
            return False
        
        self._running = True
        await self._frame_reader.start_async()
        return True

    async def stop(self):
        """停止捕获并释放系统资源"""
        self._running = False
        
        if self._frame_reader is not None:
            try:
                await self._frame_reader.stop_async()
            except:
                pass
            self._frame_reader = None
        
        if self._media_capture is not None:
            self._media_capture = None

    async def pause(self):
        """暂停捕获（不关闭程序）"""
        if self._frame_reader is not None:
            await self._frame_reader.stop_async()

    async def resume(self):
        """恢复捕获"""
        if self._frame_reader is not None:
            await self._frame_reader.start_async()

    def get_frame(self):
        """获取最新帧（返回 BGR 格式）"""
        try:
            frame = self._frame_queue.get_nowait()
        except Empty:
            frame = self._last_frame
        
        if frame is not None:
            # 转换为 BGR 格式
            if frame.shape[2] == 4:  # BGRA
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        
        return frame

    # ==================== 帧处理 ====================

    def _on_frame_arrived(self, reader, args):
        """帧到达回调"""
        if not self._running:
            return
            
        with self._lock:
            try:
                self._process_frame(reader)
            except Exception:
                pass

    def _process_frame(self, reader):
        """处理帧数据"""
        media_frame = reader.try_acquire_latest_frame()
        if media_frame is None:
            return
        
        try:
            video_frame = media_frame.video_media_frame
            if video_frame is None:
                return
            
            # 检查照明状态
            self._check_illumination(video_frame)
            
            # 应用帧过滤
            if not self._should_display_frame():
                return
            
            # 处理位图
            bitmap = video_frame.software_bitmap
            if bitmap is not None:
                frame = self._convert_bitmap_to_frame(bitmap)
                if frame is not None:
                    self._update_frame(frame)
        finally:
            media_frame.close()

    def _check_illumination(self, video_frame):
        """检查帧是否为照明帧"""
        try:
            ir_frame = video_frame.infrared_media_frame
            if ir_frame is not None:
                self._is_illuminated = ir_frame.is_illuminated
        except:
            self._is_illuminated = False

    def _should_display_frame(self) -> bool:
        """根据过滤器判断是否显示当前帧"""
        if self._frame_filter == IRFrameFilter.NONE:
            return True
        if self._frame_filter == IRFrameFilter.RAW:
            return not self._is_illuminated
        if self._frame_filter == IRFrameFilter.ILLUMINATED:
            return self._is_illuminated
        return True

    def _convert_bitmap_to_frame(self, bitmap):
        """将 SoftwareBitmap 转换为 numpy 数组"""
        try:
            converted = SoftwareBitmap.convert(bitmap, BitmapPixelFormat.BGRA8)
            buffer = converted.lock_buffer(BitmapBufferAccessMode.READ)
            reference = buffer.create_reference()
            
            data = bytes(reference)
            frame = np.frombuffer(data, dtype=np.uint8).copy()
            frame = frame.reshape((converted.pixel_height, converted.pixel_width, 4))
            
            buffer.close()
            converted.close()
            bitmap.close()
            
            return frame
        except:
            return None

    def _update_frame(self, frame):
        """更新帧队列"""
        # 应用颜色映射
        frame = self._apply_color_mapping(frame)
        
        # 保存最后一帧
        self._last_frame = frame.copy()
        
        # 更新队列
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except Empty:
                break
        
        try:
            self._frame_queue.put_nowait(frame)
        except:
            pass

    def _apply_color_mapping(self, frame):
        """应用颜色映射"""
        if self._mapping_mode == IRMappingMode.NONE:
            return frame
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        
        if self._mapping_mode == IRMappingMode.GREEN:
            result = np.zeros_like(frame)
            result[:, :, 1] = gray  # 绿色通道
            result[:, :, 3] = 255   # Alpha
            return result
        
        elif self._mapping_mode == IRMappingMode.HEAT:
            colored = cv2.applyColorMap(gray, cv2.COLORMAP_HOT)
            return cv2.cvtColor(colored, cv2.COLOR_BGR2BGRA)
        
        elif self._mapping_mode == IRMappingMode.JET:
            colored = cv2.applyColorMap(gray, cv2.COLORMAP_JET)
            return cv2.cvtColor(colored, cv2.COLOR_BGR2BGRA)
        
        return frame
