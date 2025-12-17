"""
FlexiView - 灵活的视频/图像显示控制程序
支持在另一块显示屏上播放视频或图像，可控制大小、位置和旋转角度
支持红外摄像头（Windows平台）
"""

__version__ = "1.0.0"
__author__ = "Haicaji"

from .display import DisplayWindow
from .player import VideoPlayer
from .control_panel import ControlPanel
from .ir_camera import IR_CAMERA_AVAILABLE, IRFrameFilter, IRMappingMode

if IR_CAMERA_AVAILABLE:
    from .ir_camera import IRCameraController
