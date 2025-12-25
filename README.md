# FlexiView - 灵活的视频/图像显示控制程序# FlexiView - 灵活的视频/图像显示控制程序



FlexiView 是一个基于 Python 和 Web 技术的专业显示控制工具，专为需要在第二显示器上精确控制视频、图像或摄像头画面的场景设计。它提供了强大的实时变换功能（缩放、旋转、镜像、位移）和便捷的 Web 控制界面。一个可以在另一块显示屏上播放视频或图像的 Python 程序，支持控制显示的大小、位置和旋转角度。



## ✨ 主要功能## 功能特点



### 📺 多媒体支持- 🖥️ **多显示器支持**: 自动检测所有连接的显示器，可选择任意显示器作为输出

- **视频播放**: 支持 MP4, AVI, MKV, MOV 等主流格式，支持循环播放、进度跳转。- 🎬 **视频播放**: 支持 MP4、AVI、MKV、MOV 等常见视频格式

- **图像显示**: 支持 JPG, PNG, BMP 等常见图片格式。- 🖼️ **图像显示**: 支持 JPG、PNG、BMP 等图像格式

- **摄像头输入**: 支持 USB 摄像头实时画面。- 📷 **摄像头输入**: 支持实时摄像头画面

- **红外摄像头**: 专为 Windows Hello 红外摄像头优化，支持帧过滤（原始/照明）和伪彩色映射（热力图/绿色/Jet）。- � **红外摄像头支持**: 支持 Windows Hello 红外摄像头，包含帧过滤、颜色映射等功能

- �🔄 **旋转控制**: 支持 0-360° 任意角度旋转

### 🎮 强大的显示控制- 📐 **缩放控制**: 支持 0.1x - 3x 缩放

- **实时变换**:- ↔️ **位置控制**: 支持 X/Y 方向位移调整

  - 🔄 **旋转**: 0-360° 任意角度实时旋转。- 🎨 **背景颜色**: 可自定义背景颜色（黑色、白色、绿幕等）

  - 🔍 **缩放**: 0.1x - 5.0x 无级缩放。- ⏯️ **播放控制**: 播放、暂停、停止、循环播放

  - ↔️ **位移**: X/Y 轴像素级精确位移，支持长按连续移动。

  - 🪞 **镜像**: 支持水平和垂直镜像翻转。## 安装

- **多显示器管理**: 自动识别所有连接的显示器，一键切换输出屏幕。

- **背景控制**: 自定义背景颜色，支持一键清空显示（黑屏/纯色）。1. 确保已安装 Python 3.8+

- **辅助功能**: 可调节的辅助框（Guide Rect），用于定位和对齐。

2. 安装依赖包：

### ⚙️ 配置管理```bash

- **保存/加载**: 将当前的显示参数（缩放、位置、旋转等）保存为配置文件。pip install -r requirements.txt

- **导入/导出**: 支持配置文件的上传和下载，方便在不同设备间迁移。```



### 🌐 Web 控制界面### 红外摄像头功能（可选）

- 现代化的 React UI，响应式设计。

- 支持局域网内多设备控制（手机/平板/PC）。红外摄像头功能仅在 Windows 平台可用。需要安装额外的 winrt 依赖：



## 🚀 快速开始```bash

pip install winrt-Windows.Devices.Enumeration winrt-Windows.Media.Capture winrt-Windows.Media.Capture.Frames winrt-Windows.Graphics.Imaging winrt-Windows.Foundation winrt-Windows.Foundation.Collections winrt-Windows.Storage.Streams

### 环境要求```

- Windows 10/11 (推荐)

- Python 3.8+## 使用方法

- Node.js 16+ (仅用于构建前端)

### 1. 构建前端 (Web UI)

### 1. 安装后端依赖

本项目使用 React + Vite 构建 Web 界面。首次运行前需要构建前端资源：

```bash

pip install -r requirements.txt```bash

```cd frontend

npm install

若需使用红外摄像头功能，请安装额外依赖：npm run build

```bashcd ..

pip install winrt-Windows.Devices.Enumeration winrt-Windows.Media.Capture winrt-Windows.Media.Capture.Frames winrt-Windows.Graphics.Imaging winrt-Windows.Foundation winrt-Windows.Foundation.Collections winrt-Windows.Storage.Streams```

```

### 2. 运行程序

### 2. 构建前端界面

```bash

```bashpython flexi_view.py

cd frontend```

npm install

npm run build程序启动后，访问 `http://localhost:8000` 即可使用 Web 控制面板。

cd ..

```### 3. 功能说明



### 3. 启动程序- **Web 控制面板**: 在浏览器中控制播放、显示设置。

- **文件上传**: 通过 Web 界面上传视频或图片到服务器。

```bash- **多端控制**: 只要在同一局域网内，其他设备也可以通过 `http://<服务器IP>:8000` 进行控制。

python flexi_view.py

```## 旧版说明 (Tkinter)



启动成功后，浏览器访问 `http://localhost:8000` 即可进入控制台。原有的 Tkinter 界面已被 Web UI 取代。核心逻辑保留在 `flexi_view` 包中。



## 📂 目录结构## 控制说明



```### 媒体源

FlexiView/- **打开视频**: 选择本地视频文件

├── configs/              # 保存的配置文件 (.json)- **打开图片**: 选择本地图像文件

├── uploads/              # 上传的媒体文件- **打开摄像头**: 使用电脑摄像头作为输入源

├── flexi_view/           # 后端核心代码- **红外摄像头**: 使用 Windows Hello 红外摄像头（需安装额外依赖）

│   ├── player.py         # 视频播放逻辑

│   ├── display.py        # OpenCV 显示逻辑### 红外摄像头设置

│   ├── ir_camera.py      # 红外摄像头驱动- **帧过滤**: 选择显示全部帧、仅原始帧（LED关闭）或仅照明帧（LED开启）

│   └── web_server.py     # FastAPI 服务端- **颜色映射**: 原始灰度、绿色映射、热力图或 JET 色彩映射

├── frontend/             # React 前端源码

├── flexi_view.py         # 程序入口### 显示器

└── requirements.txt      # Python 依赖- 选择要用于显示的显示器

```- 点击"刷新显示器列表"更新检测到的显示器



## 📝 使用说明### 播放控制

- **播放/暂停**: 切换播放状态

1.  **连接显示器**: 确保第二显示器已连接并扩展桌面。- **停止**: 停止播放并回到开头

2.  **选择媒体**: 在“文件”标签页上传并播放视频/图片，或在“摄像头”标签页连接设备。- **循环播放**: 启用/禁用视频循环

3.  **开启投影**: 在右侧“显示设置”中勾选“投影”开关，画面将出现在目标显示器上。

4.  **调整画面**: 使用滑块和按钮调整画面的大小、角度和位置。### 变换控制

5.  **保存配置**: 点击“配置管理”图标，保存当前调试好的参数，以便下次直接加载。- **缩放**: 调整显示大小 (0.1x - 3x)

- **旋转**: 调整旋转角度 (-180° - 180°)

## ⚠️ 注意事项- **X偏移**: 水平位置调整

- **Y偏移**: 垂直位置调整

- **红外摄像头**: 仅支持兼容 Windows Hello 的红外摄像头设备。- **快捷旋转**: 一键旋转到 0°、90°、180°、270°

- **性能**: 高分辨率视频或高帧率摄像头可能会占用较高的 CPU/GPU 资源，建议根据硬件配置调整。- **重置变换**: 恢复所有变换为默认值



## 📄 许可证### 背景颜色

- 选择显示区域外的背景颜色

MIT License

## 快捷键

- **ESC**: 在显示窗口中按 ESC 键可关闭显示窗口

## 技术架构

- **控制端**: 使用 Tkinter 构建的 GUI 控制面板
- **显示端**: 使用 OpenCV 的全屏窗口
- **视频处理**: OpenCV 进行视频读取和图像变换
- **红外摄像头**: 使用 Windows Runtime API 访问红外帧数据
- **多线程**: 显示和控制分离，保证流畅性

## 项目结构

```
FlexiView/
├── flexi_view.py           # 主入口文件
├── flexi_view/             # 核心模块包
│   ├── __init__.py         # 包初始化和导出
│   ├── control_panel.py    # GUI 控制面板
│   ├── display.py          # 显示窗口管理
│   ├── player.py           # 视频/图像/摄像头播放器
│   └── ir_camera.py        # 红外摄像头控制
├── requirements.txt        # 依赖库
├── flexi_view_config.json  # 快速保存的配置文件
└── README.md               # 项目说明
```

## 依赖库

- `opencv-python`: 视频/图像处理
- `numpy`: 数组计算
- `screeninfo`: 多显示器检测
- `Pillow`: 图像处理
- `tkinter`: GUI 界面（Python 内置）
- `winrt-*`: Windows Runtime 绑定（红外摄像头功能，可选）

## 注意事项

1. 确保有两块或以上的显示器连接
2. 如果显示器列表不正确，点击"刷新显示器列表"
3. 首次运行时先点击"启动显示窗口"，再加载媒体
4. 某些高分辨率视频可能需要较好的显卡性能
5. 红外摄像头功能仅支持 Windows 平台
6. 部分电脑可能没有红外摄像头硬件

## License

MIT License
