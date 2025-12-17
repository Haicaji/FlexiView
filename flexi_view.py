#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FlexiView - 灵活的视频/图像显示控制程序
支持在另一块显示屏上播放视频或图像，可控制大小、位置和旋转角度
支持红外摄像头（Windows平台）

主入口文件
"""

from flexi_view import ControlPanel


def main():
    """程序入口"""
    app = ControlPanel()
    app.run()


if __name__ == "__main__":
    main()
