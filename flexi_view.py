#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FlexiView - 灵活的视频/图像显示控制程序
支持在另一块显示屏上播放视频或图像，可控制大小、位置和旋转角度
支持红外摄像头（Windows平台）

主入口文件
"""

from flexi_view.web_server import run_server


def main():
    """程序入口"""
    print("Starting FlexiView Web Server...")
    print("Please ensure you have built the frontend: cd frontend && npm install && npm run build")
    print("Access the UI at http://localhost:8000")
    run_server()


if __name__ == "__main__":
    main()
