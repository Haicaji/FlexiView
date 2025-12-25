import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { Play, Pause, Square, Upload, RefreshCw, Monitor, Move, Maximize, RotateCw, ArrowRight, ArrowLeft, ArrowUp, ArrowDown, Camera, Video, Image as ImageIcon, Save, FileDown, Settings, Trash2, Download, X } from 'lucide-react';

const API_BASE = '/api';

// Helper hook for long press
function useLongPress(callback = () => {}, ms = 100) {
  const [startLongPress, setStartLongPress] = useState(false);
  const timerRef = useRef(null);

  useEffect(() => {
    if (startLongPress) {
      timerRef.current = setInterval(callback, ms);
    } else {
      clearInterval(timerRef.current);
    }

    return () => {
      clearInterval(timerRef.current);
    };
  }, [startLongPress, callback, ms]);

  return {
    onMouseDown: () => {
        callback(); // Trigger once immediately
        setStartLongPress(true);
    },
    onMouseUp: () => setStartLongPress(false),
    onMouseLeave: () => setStartLongPress(false),
    onTouchStart: () => {
        callback();
        setStartLongPress(true);
    },
    onTouchEnd: () => setStartLongPress(false),
  };
}

const ContinuousButton = ({ onClick, children, className }) => {
    const longPressProps = useLongPress(onClick, 50); // 50ms interval
    return (
        <button {...longPressProps} className={className}>
            {children}
        </button>
    );
};

const ConfigManager = ({ status, onClose }) => {
    const [configs, setConfigs] = useState([]);
    const [newConfigName, setNewConfigName] = useState('');
    const fileInputRef = useRef(null);

    useEffect(() => {
        fetchConfigs();
    }, []);

    const fetchConfigs = async () => {
        try {
            const res = await axios.get(`${API_BASE}/configs`);
            setConfigs(res.data.files);
        } catch (err) {
            console.error(err);
        }
    };

    const handleSave = async () => {
        if (!newConfigName) return;
        try {
            const config = {
                display: {
                    enabled: status.display.enabled,
                    scale: status.display.scale,
                    rotation: status.display.rotation,
                    offset_x: status.display.offset_x,
                    offset_y: status.display.offset_y,
                    mirror_h: status.display.mirror_h,
                    mirror_v: status.display.mirror_v,
                    background_color: status.display.background_color,
                    monitor_index: status.display.monitor_index
                },
                guide: {
                    enabled: status.guide.enabled,
                    x: status.guide.x,
                    y: status.guide.y,
                    width: status.guide.width,
                    height: status.guide.height
                }
            };
            await axios.post(`${API_BASE}/configs/save`, { filename: newConfigName, config });
            setNewConfigName('');
            fetchConfigs();
            alert("保存成功");
        } catch (err) {
            alert("保存失败");
        }
    };

    const handleLoad = async (filename) => {
        try {
            await axios.post(`${API_BASE}/configs/load`, { filename });
            alert("加载成功");
            onClose(); // Close modal on success? Maybe keep open.
        } catch (err) {
            alert("加载失败");
        }
    };

    const handleDelete = async (filename) => {
        if (!confirm(`确定删除 ${filename}?`)) return;
        try {
            await axios.delete(`${API_BASE}/configs/${filename}`);
            fetchConfigs();
        } catch (err) {
            alert("删除失败");
        }
    };

    const handleUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const formData = new FormData();
        formData.append('file', file);
        try {
            await axios.post(`${API_BASE}/configs/upload`, formData);
            fetchConfigs();
        } catch (err) {
            alert("上传失败");
        }
    };

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-md">
                <div className="flex justify-between items-center mb-4">
                    <h2 className="text-xl font-bold flex items-center gap-2"><Settings size={20}/> 配置管理</h2>
                    <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded"><X size={20}/></button>
                </div>

                <div className="mb-6">
                    <label className="block text-sm font-medium text-gray-700 mb-2">保存当前配置</label>
                    <div className="flex gap-2">
                        <input 
                            type="text" 
                            placeholder="配置名称" 
                            value={newConfigName}
                            onChange={(e) => setNewConfigName(e.target.value)}
                            className="flex-1 border rounded px-3 py-2"
                        />
                        <button onClick={handleSave} className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">保存</button>
                    </div>
                </div>

                <div className="mb-4">
                    <div className="flex justify-between items-center mb-2">
                        <label className="block text-sm font-medium text-gray-700">已保存配置</label>
                        <div className="flex gap-2">
                            <input 
                                type="file" 
                                ref={fileInputRef}
                                onChange={handleUpload}
                                className="hidden" 
                                accept=".json"
                            />
                            <button onClick={() => fileInputRef.current.click()} className="text-sm text-blue-600 hover:underline flex items-center gap-1"><Upload size={14}/> 上传</button>
                        </div>
                    </div>
                    <div className="border rounded-lg max-h-60 overflow-y-auto divide-y">
                        {configs.length === 0 && <div className="p-4 text-center text-gray-500 text-sm">暂无配置</div>}
                        {configs.map(f => (
                            <div key={f} className="p-3 flex justify-between items-center hover:bg-gray-50">
                                <span className="text-sm truncate">{f}</span>
                                <div className="flex gap-1">
                                    <button onClick={() => handleLoad(f)} className="p-1.5 text-green-600 hover:bg-green-50 rounded" title="加载"><FileDown size={16}/></button>
                                    <a href={`${API_BASE}/configs/download/${f}`} download className="p-1.5 text-blue-600 hover:bg-blue-50 rounded" title="下载"><Download size={16}/></a>
                                    <button onClick={() => handleDelete(f)} className="p-1.5 text-red-600 hover:bg-red-50 rounded" title="删除"><Trash2 size={16}/></button>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};

function App() {
  const [status, setStatus] = useState(null);
  const [files, setFiles] = useState([]);
  const [cameras, setCameras] = useState([]);
  const [irCameras, setIrCameras] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [activeTab, setActiveTab] = useState('files'); // 'files', 'camera', 'ir'
  const [isSeeking, setIsSeeking] = useState(false);
  const [seekValue, setSeekValue] = useState(0);
  const [showConfigManager, setShowConfigManager] = useState(false);
  const fileInputRef = useRef(null);

  // Fetch status periodically
  useEffect(() => {
    const interval = setInterval(fetchStatus, 1000);
    fetchStatus();
    fetchFiles();
    fetchCameras();
    fetchIrCameras();
    return () => clearInterval(interval);
  }, []);

  // Sync seek value with status when not seeking
  useEffect(() => {
    if (status && !isSeeking) {
        setSeekValue(status.current_frame);
    }
  }, [status, isSeeking]);

  const fetchStatus = async () => {
    try {
      const res = await axios.get(`${API_BASE}/status`);
      setStatus(res.data);
    } catch (err) {
      console.error("Failed to fetch status", err);
    }
  };

  const fetchFiles = async () => {
    try {
      const res = await axios.get(`${API_BASE}/files`);
      setFiles(res.data.files);
    } catch (err) {
      console.error("Failed to fetch files", err);
    }
  };

  const fetchCameras = async () => {
    try {
      const res = await axios.get(`${API_BASE}/cameras`);
      setCameras(res.data.cameras);
    } catch (err) {
      console.error("Failed to fetch cameras", err);
    }
  };

  const fetchIrCameras = async () => {
    try {
      const res = await axios.get(`${API_BASE}/ir_cameras`);
      if (res.data.available) {
        setIrCameras(res.data.cameras);
      }
    } catch (err) {
      console.error("Failed to fetch IR cameras", err);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    try {
      await axios.post(`${API_BASE}/upload`, formData);
      fetchFiles();
    } catch (err) {
      alert("上传失败");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const playFile = async (filename) => {
    try {
      await axios.post(`${API_BASE}/play`, { filename });
      fetchStatus();
    } catch (err) {
      alert("播放文件失败");
    }
  };

  const playCamera = async (cameraId) => {
    try {
      await axios.post(`${API_BASE}/play_camera`, { camera_id: cameraId });
      fetchStatus();
    } catch (err) {
      alert("播放摄像头失败");
    }
  };

  const playIrCamera = async (cameraIndex) => {
    try {
      await axios.post(`${API_BASE}/play_ir`, { camera_index: cameraIndex });
      fetchStatus();
    } catch (err) {
      alert("播放红外摄像头失败");
    }
  };

  const updateIrConfig = async (config) => {
    try {
      await axios.post(`${API_BASE}/ir_config`, config);
    } catch (err) {
      console.error(err);
    }
  };

  const controlPlayback = async (action) => {
    try {
      await axios.post(`${API_BASE}/${action}`);
      fetchStatus();
    } catch (err) {
      console.error(err);
    }
  };

  const updateDisplay = async (config) => {
    try {
      await axios.post(`${API_BASE}/display`, config);
      fetchStatus();
    } catch (err) {
      console.error(err);
    }
  };

  const clearDisplay = async () => {
    try {
      await axios.post(`${API_BASE}/clear`);
      fetchStatus();
    } catch (err) {
      console.error(err);
    }
  };
  
  const updateGuide = async (config) => {
    try {
      await axios.post(`${API_BASE}/guide`, config);
      fetchStatus();
    } catch (err) {
      console.error(err);
    }
  };

  const saveConfig = async () => {
    try {
      // Construct config object from current status
      const config = {
        display: {
            scale: status.display.scale,
            rotation: status.display.rotation,
            offset_x: status.display.offset_x,
            offset_y: status.display.offset_y,
            mirror_h: status.display.mirror_h,
            mirror_v: status.display.mirror_v,
            background_color: status.display.background_color,
            monitor_index: status.display.monitor_index
        },
        guide: {
            enabled: status.guide.enabled,
            x: status.guide.x,
            y: status.guide.y,
            width: status.guide.width,
            height: status.guide.height
        }
      };
      await axios.post(`${API_BASE}/config`, config);
      alert("配置已保存");
    } catch (err) {
      alert("保存配置失败");
    }
  };

  const loadConfig = async () => {
    try {
      await axios.post(`${API_BASE}/load_config`);
      fetchStatus();
      alert("配置已加载");
    } catch (err) {
      alert("加载配置失败");
    }
  };

  const handleSeekChange = (e) => {
    setSeekValue(parseInt(e.target.value));
  };

  const handleSeekStart = () => {
    setIsSeeking(true);
  };

  const handleSeekCommit = async (e) => {
    // Use the value from the event if available, otherwise current state
    const val = e.target.value ? parseInt(e.target.value) : seekValue;
    setIsSeeking(false);
    setSeekValue(val);
    try {
        await axios.post(`${API_BASE}/seek`, { frame_index: val });
        fetchStatus();
    } catch (err) {
        console.error(err);
    }
  };

  if (!status) return <div className="p-10 text-center">加载中...</div>;

  return (
    <div className="min-h-screen p-4 md:p-8 max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">
      
      {/* Left Column: Preview & Playback */}
      <div className="lg:col-span-2 space-y-6">
        <div className="bg-white rounded-xl shadow-lg overflow-hidden">
          <div className="bg-gray-800 p-2 flex justify-between items-center text-white">
            <h2 className="font-semibold flex items-center gap-2"><Monitor size={18}/> 预览</h2>
            <span className="text-xs bg-gray-700 px-2 py-1 rounded">实时</span>
          </div>
          <div className="aspect-video bg-black relative flex items-center justify-center">
            <img 
              src={`${API_BASE}/preview`} 
              alt="Preview" 
              className="max-w-full max-h-full object-contain"
            />
          </div>
          
          {/* Playback Controls */}
          <div className="p-4 border-t flex items-center justify-between bg-gray-50 gap-4">
            <button 
              onClick={() => controlPlayback('pause')}
              className="p-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition flex-shrink-0"
              title={status.paused ? "继续" : "暂停"}
            >
              {status.paused ? <Play size={20} /> : <Pause size={20} />}
            </button>
            
            {status.source_type === 'video' ? (
                <div className="flex-1 flex items-center gap-2">
                    <span className="text-xs text-gray-500 w-10 text-right">{seekValue}</span>
                    <input 
                        type="range" 
                        min="0" 
                        max={status.total_frames} 
                        value={seekValue}
                        onChange={handleSeekChange}
                        onMouseDown={handleSeekStart}
                        onMouseUp={handleSeekCommit}
                        onTouchStart={handleSeekStart}
                        onTouchEnd={handleSeekCommit}
                        className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                    />
                    <span className="text-xs text-gray-500 w-10">{status.total_frames}</span>
                </div>
            ) : (
                <div className="flex-1 text-sm text-gray-600 text-center">
                  {status.playing ? (
                    <span>
                      {status.source_type === 'camera' && `摄像头实时`}
                      {status.source_type === 'ir_camera' && `红外摄像头实时`}
                      {status.source_type === 'image' && `图片显示`}
                    </span>
                  ) : (
                    <span>已停止</span>
                  )}
                </div>
            )}
          </div>
        </div>

        {/* Source Manager */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <div className="flex border-b mb-4">
            <button 
              className={`px-4 py-2 font-medium ${activeTab === 'files' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500 hover:text-gray-700'}`}
              onClick={() => setActiveTab('files')}
            >
              文件
            </button>
            <button 
              className={`px-4 py-2 font-medium ${activeTab === 'camera' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500 hover:text-gray-700'}`}
              onClick={() => setActiveTab('camera')}
            >
              摄像头
            </button>
            {status.ir_available && (
              <button 
                className={`px-4 py-2 font-medium ${activeTab === 'ir' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500 hover:text-gray-700'}`}
                onClick={() => setActiveTab('ir')}
              >
                红外摄像头
              </button>
            )}
          </div>

          {activeTab === 'files' && (
            <div>
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold flex items-center gap-2"><Upload size={20}/> 文件列表</h2>
                <div className="flex gap-2">
                  <input 
                    type="file" 
                    ref={fileInputRef}
                    onChange={handleUpload}
                    className="hidden" 
                    id="file-upload"
                  />
                  <label 
                    htmlFor="file-upload"
                    className={`cursor-pointer px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition flex items-center gap-2 ${uploading ? 'opacity-50' : ''}`}
                  >
                    <Upload size={16} /> {uploading ? '上传中...' : '上传'}
                  </label>
                  <button onClick={fetchFiles} className="p-2 bg-gray-200 rounded hover:bg-gray-300">
                    <RefreshCw size={16} />
                  </button>
                </div>
              </div>
              
              <div className="max-h-60 overflow-y-auto border rounded-lg divide-y">
                {files.length === 0 && <div className="p-4 text-center text-gray-500">暂无文件</div>}
                {files.map(file => (
                  <div key={file} className="p-3 hover:bg-gray-50 flex justify-between items-center">
                    <span className="truncate flex items-center gap-2">
                      {file.match(/\.(jpg|jpeg|png|bmp|gif)$/i) ? <ImageIcon size={16}/> : <Video size={16}/>}
                      {file}
                    </span>
                    <button 
                      onClick={() => playFile(file)}
                      className="px-3 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 text-sm font-medium"
                    >
                      播放
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'camera' && (
            <div>
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold flex items-center gap-2"><Camera size={20}/> RGB 摄像头</h2>
                <button onClick={fetchCameras} className="p-2 bg-gray-200 rounded hover:bg-gray-300">
                  <RefreshCw size={16} />
                </button>
              </div>
              <div className="space-y-2">
                {cameras.length === 0 && <div className="p-4 text-center text-gray-500">未检测到摄像头</div>}
                {cameras.map(cam => (
                  <div key={cam.id} className="p-3 border rounded hover:bg-gray-50 flex justify-between items-center">
                    <span>{cam.name}</span>
                    <button 
                      onClick={() => playCamera(cam.id)}
                      className="px-3 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 text-sm font-medium"
                    >
                      连接
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'ir' && (
            <div>
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold flex items-center gap-2"><Camera size={20}/> 红外摄像头</h2>
                <button onClick={fetchIrCameras} className="p-2 bg-gray-200 rounded hover:bg-gray-300">
                  <RefreshCw size={16} />
                </button>
              </div>
              
              <div className="space-y-4">
                <div className="space-y-2">
                  {irCameras.length === 0 && <div className="p-4 text-center text-gray-500">未检测到红外摄像头</div>}
                  {irCameras.map(cam => (
                    <div key={cam.id} className="p-3 border rounded hover:bg-gray-50 flex justify-between items-center">
                      <span>{cam.name}</span>
                      <button 
                        onClick={() => playIrCamera(cam.index)}
                        className="px-3 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 text-sm font-medium"
                      >
                        连接
                      </button>
                    </div>
                  ))}
                </div>

                {status.source_type === 'ir_camera' && (
                  <div className="border-t pt-4 grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">过滤模式</label>
                      <select 
                        className="w-full border rounded p-2"
                        onChange={(e) => updateIrConfig({ camera_index: 0, filter_mode: e.target.value })}
                      >
                        <option value="NONE">全部帧</option>
                        <option value="RAW">仅原始帧</option>
                        <option value="ILLUMINATED">仅照明帧</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">颜色映射</label>
                      <select 
                        className="w-full border rounded p-2"
                        onChange={(e) => updateIrConfig({ camera_index: 0, mapping_mode: e.target.value })}
                      >
                        <option value="NONE">原始</option>
                        <option value="GREEN">绿色</option>
                        <option value="HEAT">热力图</option>
                        <option value="JET">Jet</option>
                      </select>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right Column: Controls */}
      <div className="space-y-6">
        
        {/* Display Settings */}
        <div className="bg-white rounded-xl shadow-lg p-6 space-y-4">
          <div className="flex justify-between items-center">
             <h2 className="text-xl font-bold flex items-center gap-2"><Maximize size={20}/> 显示设置</h2>
             <div className="flex gap-2 items-center">
                <label className="relative inline-flex items-center cursor-pointer mr-2" title="开启/关闭投影窗口">
                  <input 
                    type="checkbox" 
                    checked={status.display.enabled}
                    onChange={(e) => updateDisplay({ enabled: e.target.checked })}
                    className="sr-only peer" 
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  <span className="ml-2 text-sm font-medium text-gray-900">投影</span>
                </label>
                <div className="h-6 w-px bg-gray-300 mx-1"></div>
                <button onClick={() => setShowConfigManager(true)} className="p-2 text-blue-600 hover:bg-blue-50 rounded" title="配置管理"><Settings size={18}/></button>
             </div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">缩放: {status.display.scale.toFixed(2)}</label>
            <input 
              type="range" min="0.1" max="5" step="0.1"
              value={status.display.scale}
              onChange={(e) => updateDisplay({ scale: parseFloat(e.target.value) })}
              className="w-full"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">旋转: {status.display.rotation}°</label>
            <input 
              type="range" min="0" max="360" step="1"
              value={status.display.rotation}
              onChange={(e) => updateDisplay({ rotation: parseFloat(e.target.value) })}
              className="w-full"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">X 偏移</label>
              <input 
                type="number" 
                value={status.display.offset_x}
                onChange={(e) => updateDisplay({ offset_x: parseInt(e.target.value) })}
                className="w-full border rounded px-2 py-1"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Y 偏移</label>
              <input 
                type="number" 
                value={status.display.offset_y}
                onChange={(e) => updateDisplay({ offset_y: parseInt(e.target.value) })}
                className="w-full border rounded px-2 py-1"
              />
            </div>
          </div>

          {/* Display Position Controls */}
          <div className="grid grid-cols-3 gap-2 items-center justify-items-center">
              <div></div>
              <ContinuousButton onClick={() => updateDisplay({ offset_y: status.display.offset_y - 5 })} className="p-2 bg-gray-100 rounded hover:bg-gray-200"><ArrowUp size={16}/></ContinuousButton>
              <div></div>
              <ContinuousButton onClick={() => updateDisplay({ offset_x: status.display.offset_x - 5 })} className="p-2 bg-gray-100 rounded hover:bg-gray-200"><ArrowLeft size={16}/></ContinuousButton>
              <div className="text-xs text-gray-500">位置</div>
              <ContinuousButton onClick={() => updateDisplay({ offset_x: status.display.offset_x + 5 })} className="p-2 bg-gray-100 rounded hover:bg-gray-200"><ArrowRight size={16}/></ContinuousButton>
              <div></div>
              <ContinuousButton onClick={() => updateDisplay({ offset_y: status.display.offset_y + 5 })} className="p-2 bg-gray-100 rounded hover:bg-gray-200"><ArrowDown size={16}/></ContinuousButton>
              <div></div>
          </div>

          <div className="flex gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input 
                type="checkbox" 
                checked={status.display.mirror_h}
                onChange={(e) => updateDisplay({ mirror_h: e.target.checked })}
                className="rounded text-blue-600"
              />
              <span>水平镜像</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input 
                type="checkbox" 
                checked={status.display.mirror_v}
                onChange={(e) => updateDisplay({ mirror_v: e.target.checked })}
                className="rounded text-blue-600"
              />
              <span>垂直镜像</span>
            </label>
          </div>

          <div className="flex items-center gap-2">
             <label className="text-sm font-medium text-gray-700">背景颜色</label>
             <input 
                type="color"
                value={`#${status.display.background_color.map(c => c.toString(16).padStart(2, '0')).join('')}`}
                onChange={(e) => {
                    const hex = e.target.value;
                    const r = parseInt(hex.slice(1, 3), 16);
                    const g = parseInt(hex.slice(3, 5), 16);
                    const b = parseInt(hex.slice(5, 7), 16);
                    updateDisplay({ background_color: [r, g, b] });
                }}
                className="h-8 w-16 p-0 border-0 rounded cursor-pointer"
             />
          </div>
          
          <div className="flex gap-2">
            <button 
                onClick={clearDisplay}
                className="flex-1 py-2 bg-red-100 text-red-700 rounded hover:bg-red-200 text-sm font-medium flex items-center justify-center gap-2"
            >
                <Square size={16}/> 清空显示
            </button>
            <button 
                onClick={() => updateDisplay({ scale: 1.0, rotation: 0, offset_x: 0, offset_y: 0, mirror_h: false, mirror_v: false })}
                className="flex-1 py-2 bg-gray-200 rounded hover:bg-gray-300 text-sm font-medium"
            >
                重置显示
            </button>
          </div>
        </div>

        {/* Guide Rect */}
        <div className="bg-white rounded-xl shadow-lg p-6 space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-bold flex items-center gap-2"><Move size={20}/> 辅助框</h2>
            <label className="relative inline-flex items-center cursor-pointer">
              <input 
                type="checkbox" 
                checked={status.guide.enabled}
                onChange={(e) => updateGuide({ enabled: e.target.checked })}
                className="sr-only peer" 
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>

          {status.guide.enabled && (
            <div className="space-y-3">
               <div className="grid grid-cols-3 gap-2 items-center justify-items-center">
                  <div></div>
                  <ContinuousButton onClick={() => updateGuide({ y: status.guide.y - 5 })} className="p-2 bg-gray-100 rounded hover:bg-gray-200"><ArrowUp size={16}/></ContinuousButton>
                  <div></div>
                  <ContinuousButton onClick={() => updateGuide({ x: status.guide.x - 5 })} className="p-2 bg-gray-100 rounded hover:bg-gray-200"><ArrowLeft size={16}/></ContinuousButton>
                  <div className="text-xs text-gray-500">位置</div>
                  <ContinuousButton onClick={() => updateGuide({ x: status.guide.x + 5 })} className="p-2 bg-gray-100 rounded hover:bg-gray-200"><ArrowRight size={16}/></ContinuousButton>
                  <div></div>
                  <ContinuousButton onClick={() => updateGuide({ y: status.guide.y + 5 })} className="p-2 bg-gray-100 rounded hover:bg-gray-200"><ArrowDown size={16}/></ContinuousButton>
                  <div></div>
               </div>
               
               <div className="grid grid-cols-2 gap-2">
                 <div>
                    <label className="text-xs text-gray-500">宽度</label>
                    <input 
                      type="number" 
                      value={status.guide.width}
                      onChange={(e) => updateGuide({ width: parseInt(e.target.value) })}
                      className="w-full border rounded px-2 py-1 text-sm"
                    />
                 </div>
                 <div>
                    <label className="text-xs text-gray-500">高度</label>
                    <input 
                      type="number" 
                      value={status.guide.height}
                      onChange={(e) => updateGuide({ height: parseInt(e.target.value) })}
                      className="w-full border rounded px-2 py-1 text-sm"
                    />
                 </div>
               </div>
            </div>
          )}
        </div>
      </div>

      {/* Config Manager Modal */}
      {showConfigManager && <ConfigManager status={status} onClose={() => setShowConfigManager(false)} />}
    </div>
  );
}

export default App;
