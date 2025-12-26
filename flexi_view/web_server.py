import time
import os
import cv2
import numpy as np
import threading
import asyncio
import uvicorn
import json
import base64
import aiofiles
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from typing import Optional, List
from pydantic import BaseModel

from .display import DisplayWindow
from .player import VideoPlayer
from .ir_camera import IR_CAMERA_AVAILABLE, IRFrameFilter, IRMappingMode

if IR_CAMERA_AVAILABLE:
    from .ir_camera import MediaFrameSourceGroup, MediaFrameSourceKind

# 全局状态
class AppState:
    def __init__(self):
        self.display = DisplayWindow(monitor_index=1)
        self.player = VideoPlayer(self.display)
        self.preview_frame = None
        self.lock = threading.Lock()
        self.running = True
        
        # 辅助框设置
        self.guide_rect_enabled = False
        self.guide_rect_x = 0
        self.guide_rect_y = 0
        self.guide_rect_width = 800
        self.guide_rect_height = 600
        
        # 预览设置
        self.preview_show_processed = True

app_state = AppState()

app = FastAPI()

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 确保上传目录存在
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# 确保配置目录存在
CONFIG_DIR = "configs"
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)

# Pydantic 模型
class DisplayConfig(BaseModel):
    enabled: Optional[bool] = None
    scale: Optional[float] = None
    rotation: Optional[float] = None
    offset_x: Optional[int] = None
    offset_y: Optional[int] = None
    mirror_h: Optional[bool] = None
    mirror_v: Optional[bool] = None
    background_color: Optional[List[int]] = None # [r, g, b]
    monitor_index: Optional[int] = None

class GuideConfig(BaseModel):
    enabled: Optional[bool] = None
    x: Optional[int] = None
    y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None

class PlayRequest(BaseModel):
    filename: str
    loop: bool = True

class SeekRequest(BaseModel):
    frame_index: int

class IRConfig(BaseModel):
    camera_index: int
    filter_mode: Optional[str] = None # "NONE", "RAW", "ILLUMINATED"
    mapping_mode: Optional[str] = None # "NONE", "GREEN", "HEAT", "JET"

class CameraConfig(BaseModel):
    camera_id: int

class Config(BaseModel):
    display: DisplayConfig
    guide: GuideConfig

class ConfigFileRequest(BaseModel):
    filename: str

class SaveConfigRequest(BaseModel):
    filename: str
    config: Config

# API 路由
@app.get("/api/status")
def get_status():
    return {
        "playing": app_state.player.playing,
        "paused": app_state.player.paused,
        "current_frame": app_state.player.current_frame_idx,
        "total_frames": app_state.player.total_frames,
        "fps": app_state.player.fps,
        "source_type": app_state.player.source_type,
        "display": {
            "enabled": app_state.display.running,
            "scale": app_state.display.scale,
            "rotation": app_state.display.rotation,
            "offset_x": app_state.display.offset_x,
            "offset_y": app_state.display.offset_y,
            "mirror_h": app_state.display.mirror_h,
            "mirror_v": app_state.display.mirror_v,
            "background_color": app_state.display.background_color, # BGR
            "monitor_index": app_state.display.monitor_index
        },
        "guide": {
            "enabled": app_state.guide_rect_enabled,
            "x": app_state.guide_rect_x,
            "y": app_state.guide_rect_y,
            "width": app_state.guide_rect_width,
            "height": app_state.guide_rect_height
        },
        "ir_available": IR_CAMERA_AVAILABLE,
        "ir_config": {
            "filter_mode": app_state.player.ir_controller.frame_filter.name if app_state.player.ir_controller else "NONE",
            "mapping_mode": app_state.player.ir_controller.mapping_mode.name if app_state.player.ir_controller else "NONE"
        }
    }

@app.get("/api/files")
def list_files():
    files = []
    for f in os.listdir(UPLOAD_DIR):
        if os.path.isfile(os.path.join(UPLOAD_DIR, f)):
            files.append(f)
    return {"files": files}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
    return {"filename": file.filename, "message": "Upload successful"}

@app.post("/api/play")
def play_file(req: PlayRequest):
    file_path = os.path.join(UPLOAD_DIR, req.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # 停止当前的
    app_state.player.stop()
    
    # 加载新的
    # 判断是图片还是视频
    ext = os.path.splitext(req.filename)[1].lower()
    if ext in ['.jpg', '.jpeg', '.png', '.bmp']:
        if app_state.player.load_image(file_path):
            app_state.player.play()
            return {"message": "Playing image"}
    else:
        if app_state.player.load_video(file_path):
            app_state.player.loop = req.loop
            app_state.player.play()
            return {"message": "Playing video"}
            
    raise HTTPException(status_code=400, detail="Failed to load file")

@app.post("/api/stop")
def stop_play():
    app_state.player.stop()
    return {"message": "Stopped"}

@app.post("/api/pause")
def pause_play():
    if app_state.player.playing:
        if app_state.player.paused:
            app_state.player.resume()
        else:
            app_state.player.pause()
    return {"message": "Toggled pause", "paused": app_state.player.paused}

@app.post("/api/seek")
def seek_video(req: SeekRequest):
    if app_state.player.source_type == 'video':
        app_state.player.seek(req.frame_index)
    return {"message": "Seeked"}

@app.post("/api/display")
def update_display(config: DisplayConfig):
    if config.enabled is not None:
        if config.enabled and not app_state.display.running:
             display_thread = threading.Thread(target=app_state.display.display_loop, daemon=True)
             display_thread.start()
        elif not config.enabled and app_state.display.running:
             app_state.display.stop()

    if config.scale is not None:
        app_state.display.scale = config.scale
    if config.rotation is not None:
        app_state.display.rotation = config.rotation
    if config.offset_x is not None:
        app_state.display.offset_x = config.offset_x
    if config.offset_y is not None:
        app_state.display.offset_y = config.offset_y
    if config.mirror_h is not None:
        app_state.display.mirror_h = config.mirror_h
    if config.mirror_v is not None:
        app_state.display.mirror_v = config.mirror_v
    if config.background_color is not None:
        # 前端传RGB，后端存BGR
        r, g, b = config.background_color
        app_state.display.background_color = (b, g, r)
    if config.monitor_index is not None:
        app_state.display.update_monitor(config.monitor_index)
        
    return {"message": "Display updated"}

@app.post("/api/clear")
def clear_display():
    app_state.player.clear()
    return {"message": "Display cleared"}

@app.post("/api/guide")
def update_guide(config: GuideConfig):
    if config.enabled is not None:
        app_state.guide_rect_enabled = config.enabled
    if config.x is not None:
        app_state.guide_rect_x = config.x
    if config.y is not None:
        app_state.guide_rect_y = config.y
    if config.width is not None:
        app_state.guide_rect_width = config.width
    if config.height is not None:
        app_state.guide_rect_height = config.height
    return {"message": "Guide updated"}

@app.get("/api/cameras")
def list_cameras():
    available_cameras = []
    # OpenCV暴力检测0~10
    for idx in range(0, 11):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if cap.isOpened():
            name = f"Camera {idx}"
            available_cameras.append({'id': idx, 'name': name})
            cap.release()
    return {"cameras": available_cameras}

@app.get("/api/monitors")
def list_monitors():
    """获取所有可用的显示器列表"""
    monitor_info = app_state.display.get_monitor_info()
    monitors = [{"index": idx, "name": name} for idx, name in monitor_info]
    return {"monitors": monitors}

@app.post("/api/play_camera")
def play_camera(config: CameraConfig):
    if app_state.player.load_camera(config.camera_id):
        app_state.player.play()
        return {"message": f"Playing camera {config.camera_id}"}
    raise HTTPException(status_code=400, detail="Failed to load camera")

@app.get("/api/ir_cameras")
def list_ir_cameras():
    if not IR_CAMERA_AVAILABLE:
        return {"available": False, "cameras": []}
    
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
        # 在新线程中运行异步循环，避免阻塞主线程
        # 注意：FastAPI 本身是异步的，但 winrt 需要在特定线程模型下运行
        # 这里简单起见，直接运行
        # 更好的做法可能是维护一个全局的 IR 管理器
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        cameras = loop.run_until_complete(get_ir_cameras())
        loop.close()
        return {"available": True, "cameras": cameras}
    except Exception as e:
        print(f"获取红外摄像头列表失败: {e}")
        return {"available": True, "cameras": []}

@app.post("/api/play_ir")
def play_ir(config: IRConfig):
    if not IR_CAMERA_AVAILABLE:
        raise HTTPException(status_code=400, detail="IR Camera not available")
    
    success, message = app_state.player.load_ir_camera(config.camera_index)
    if success:
        app_state.player.play()
        # 设置初始参数
        if config.filter_mode:
             filter_map = {"NONE": IRFrameFilter.NONE, "RAW": IRFrameFilter.RAW, "ILLUMINATED": IRFrameFilter.ILLUMINATED}
             if app_state.player.ir_controller:
                 app_state.player.ir_controller.frame_filter = filter_map.get(config.filter_mode, IRFrameFilter.NONE)
        
        if config.mapping_mode:
            color_map = {"NONE": IRMappingMode.NONE, "GREEN": IRMappingMode.GREEN, "HEAT": IRMappingMode.HEAT, "JET": IRMappingMode.JET}
            if app_state.player.ir_controller:
                app_state.player.ir_controller.mapping_mode = color_map.get(config.mapping_mode, IRMappingMode.NONE)

        return {"message": message}
    else:
        raise HTTPException(status_code=400, detail=message)

@app.post("/api/ir_config")
def update_ir_config(config: IRConfig):
    if not IR_CAMERA_AVAILABLE or not app_state.player.ir_controller:
        return {"message": "IR controller not active"}

    if config.filter_mode:
            filter_map = {"NONE": IRFrameFilter.NONE, "RAW": IRFrameFilter.RAW, "ILLUMINATED": IRFrameFilter.ILLUMINATED}
            app_state.player.ir_controller.frame_filter = filter_map.get(config.filter_mode, IRFrameFilter.NONE)
    
    if config.mapping_mode:
        color_map = {"NONE": IRMappingMode.NONE, "GREEN": IRMappingMode.GREEN, "HEAT": IRMappingMode.HEAT, "JET": IRMappingMode.JET}
        app_state.player.ir_controller.mapping_mode = color_map.get(config.mapping_mode, IRMappingMode.NONE)
        
    return {"message": "IR config updated"}

@app.get("/api/config")
def get_config():
    return {
        "display": {
            "scale": app_state.display.scale,
            "rotation": app_state.display.rotation,
            "offset_x": app_state.display.offset_x,
            "offset_y": app_state.display.offset_y,
            "mirror_h": app_state.display.mirror_h,
            "mirror_v": app_state.display.mirror_v,
            "background_color": app_state.display.background_color,
            "monitor_index": app_state.display.monitor_index
        },
        "guide": {
            "enabled": app_state.guide_rect_enabled,
            "x": app_state.guide_rect_x,
            "y": app_state.guide_rect_y,
            "width": app_state.guide_rect_width,
            "height": app_state.guide_rect_height
        }
    }

@app.post("/api/config")
def save_config(config: Config):
    # 保存到文件
    config_data = config.dict()
    # 转换颜色格式 BGR -> RGB (如果需要) 或者保持一致
    # 这里直接保存
    try:
        with open("flexi_view_config.json", "w") as f:
            json.dump(config_data, f, indent=4)
        return {"message": "Config saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/load_config")
def load_config():
    try:
        if os.path.exists("flexi_view_config.json"):
            with open("flexi_view_config.json", "r") as f:
                config_data = json.load(f)
            
            # 应用配置
            display_conf = config_data.get("display", {})
            if "scale" in display_conf: app_state.display.scale = display_conf["scale"]
            if "rotation" in display_conf: app_state.display.rotation = display_conf["rotation"]
            if "offset_x" in display_conf: app_state.display.offset_x = display_conf["offset_x"]
            if "offset_y" in display_conf: app_state.display.offset_y = display_conf["offset_y"]
            if "mirror_h" in display_conf: app_state.display.mirror_h = display_conf["mirror_h"]
            if "mirror_v" in display_conf: app_state.display.mirror_v = display_conf["mirror_v"]
            if "background_color" in display_conf: app_state.display.background_color = tuple(display_conf["background_color"])
            if "monitor_index" in display_conf: app_state.display.update_monitor(display_conf["monitor_index"])
            
            guide_conf = config_data.get("guide", {})
            if "enabled" in guide_conf: app_state.guide_rect_enabled = guide_conf["enabled"]
            if "x" in guide_conf: app_state.guide_rect_x = guide_conf["x"]
            if "y" in guide_conf: app_state.guide_rect_y = guide_conf["y"]
            if "width" in guide_conf: app_state.guide_rect_width = guide_conf["width"]
            if "height" in guide_conf: app_state.guide_rect_height = guide_conf["height"]
            
            return {"message": "Config loaded"}
        else:
            return {"message": "No config file found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/configs")
def list_configs():
    files = []
    for f in os.listdir(CONFIG_DIR):
        if f.endswith(".json"):
            files.append(f)
    return {"files": files}

@app.post("/api/configs/save")
def save_named_config(req: SaveConfigRequest):
    filename = req.filename
    if not filename.endswith(".json"):
        filename += ".json"
    
    file_path = os.path.join(CONFIG_DIR, filename)
    config_data = req.config.dict()
    
    try:
        with open(file_path, "w") as f:
            json.dump(config_data, f, indent=4)
        return {"message": "Config saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/configs/load")
def load_named_config(req: ConfigFileRequest):
    file_path = os.path.join(CONFIG_DIR, req.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Config file not found")
        
    try:
        with open(file_path, "r") as f:
            config_data = json.load(f)
        
        # 应用配置
        display_conf = config_data.get("display", {})
        if "enabled" in display_conf:
            if display_conf["enabled"] and not app_state.display.running:
                 display_thread = threading.Thread(target=app_state.display.display_loop, daemon=True)
                 display_thread.start()
            elif not display_conf["enabled"] and app_state.display.running:
                 app_state.display.stop()

        if "scale" in display_conf: app_state.display.scale = display_conf["scale"]
        if "rotation" in display_conf: app_state.display.rotation = display_conf["rotation"]
        if "offset_x" in display_conf: app_state.display.offset_x = display_conf["offset_x"]
        if "offset_y" in display_conf: app_state.display.offset_y = display_conf["offset_y"]
        if "mirror_h" in display_conf: app_state.display.mirror_h = display_conf["mirror_h"]
        if "mirror_v" in display_conf: app_state.display.mirror_v = display_conf["mirror_v"]
        if "background_color" in display_conf: app_state.display.background_color = tuple(display_conf["background_color"])
        if "monitor_index" in display_conf: app_state.display.update_monitor(display_conf["monitor_index"])
        
        guide_conf = config_data.get("guide", {})
        if "enabled" in guide_conf: app_state.guide_rect_enabled = guide_conf["enabled"]
        if "x" in guide_conf: app_state.guide_rect_x = guide_conf["x"]
        if "y" in guide_conf: app_state.guide_rect_y = guide_conf["y"]
        if "width" in guide_conf: app_state.guide_rect_width = guide_conf["width"]
        if "height" in guide_conf: app_state.guide_rect_height = guide_conf["height"]
        
        return {"message": "Config loaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/configs/upload")
async def upload_config(file: UploadFile = File(...)):
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files allowed")
        
    file_path = os.path.join(CONFIG_DIR, file.filename)
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
    return {"filename": file.filename, "message": "Upload successful"}

@app.get("/api/configs/download/{filename}")
def download_config(filename: str):
    file_path = os.path.join(CONFIG_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)

@app.delete("/api/configs/{filename}")
def delete_config(filename: str):
    file_path = os.path.join(CONFIG_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"message": "Deleted"}
    raise HTTPException(status_code=404, detail="File not found")

def generate_preview():
    while True:
        # 获取当前帧
        raw_frame = None
        
        # 获取显示器信息用于生成背景
        monitor = app_state.display.target_monitor
        monitor_w = monitor.width
        monitor_h = monitor.height
        
        with app_state.display.lock:
            if app_state.display.frame is not None:
                raw_frame = app_state.display.frame.copy()
        
        if raw_frame is not None:
            # 获取经过变换后的完整画面 (WYSIWYG)
            frame = app_state.display.transform_frame(raw_frame)
        else:
            # 如果没有帧，显示背景色
            frame = np.full((monitor_h, monitor_w, 3), 
                            app_state.display.background_color, dtype=np.uint8)
        
        # 缩放到预览大小 (800x450)
        preview_w, preview_h = 800, 450
        
        # 计算缩放比例
        scale_x = preview_w / monitor_w
        scale_y = preview_h / monitor_h
        
        # 缩放画面
        frame_resized = cv2.resize(frame, (preview_w, preview_h))
        
        # 绘制辅助框
        if app_state.guide_rect_enabled:
            # 辅助框坐标是相对于显示器中心的偏移
            # 转换到预览坐标系
            
            rect_center_x = preview_w / 2 + app_state.guide_rect_x * scale_x
            rect_center_y = preview_h / 2 + app_state.guide_rect_y * scale_y
            
            rect_w = app_state.guide_rect_width * scale_x
            rect_h = app_state.guide_rect_height * scale_y
            
            x1 = int(rect_center_x - rect_w / 2)
            y1 = int(rect_center_y - rect_h / 2)
            x2 = int(rect_center_x + rect_w / 2)
            y2 = int(rect_center_y + rect_h / 2)
            
            cv2.rectangle(frame_resized, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
        # 编码为 JPEG
        ret, buffer = cv2.imencode('.jpg', frame_resized)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(0.03) # 约 30 FPS

@app.get("/api/preview")
def video_feed():
    return StreamingResponse(generate_preview(), media_type="multipart/x-mixed-replace; boundary=frame")

# 挂载前端静态文件
# 假设前端构建在 frontend/dist
if os.path.exists("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")

def run_server():
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    run_server()
