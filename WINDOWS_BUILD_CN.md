# Windows 平台打包快速指引

---

## 📋 准备工作

### 1. 环境检查

运行环境检查脚本，确保所有依赖已安装：

```batch
.\tools\scripts\check_windows_env.bat
```

或使用 PowerShell：

```powershell
.\tools\scripts\check_windows_env.ps1
```

### 2. 必需软件

✅ **必需**：
- Python 3.11.x
- Visual Studio 2022 (含 C++ 开发工具)
- Conan 2.7+

⚪ **可选**（用于创建安装程序）：
- NSIS (推荐)
- WiX Toolset

### 3. 快速安装依赖

```powershell
# 安装 Conan
pip install conan>=2.7.0

# 安装打包工具
pip install pyinstaller==6.11.1 pyinstaller-hooks-contrib

# 安装项目依赖
pip install pycryptodome esdk-obs-python pyyaml jinja2 semver
```

---

## 🚀 开始打包

### 方式一：一键打包（推荐）

#### 使用批处理脚本
```batch
cd C:\path\to\Cura_p
.\tools\scripts\build_windows.bat
```

#### 或使用 PowerShell
```powershell
cd C:\path\to\Cura_p
.\tools\scripts\build_windows.ps1
```

**预计时间**: 45-115 分钟（首次打包）

**输出文件**:
- `deploy\dist\UltiMaker-Cura\UltiMaker-Cura.exe` - 应用程序
- `deploy\dist\UltiMaker-Cura-5.11.0-Windows-X64.exe` - 安装程序

---

### 方式二：快速打包（无安装程序）

适合开发测试，跳过安装程序创建：

```batch
.\tools\scripts\quick_build_windows.bat
```

**预计时间**: 30-90 分钟

**输出文件**:
- `deploy\dist\UltiMaker-Cura\UltiMaker-Cura.exe`

---

### 方式三：手动分步打包

#### 步骤 1: Conan Deploy（最耗时）
```powershell
# 清理旧文件
Remove-Item -Recurse -Force deploy, dist -ErrorAction SilentlyContinue

# 运行 Conan Deploy (20-60 分钟)
conan install . --deployer=full_deploy --deployer-folder=deploy --build=missing -c tools.system.package_manager:mode=install
```

#### 步骤 2: 激活虚拟环境
```powershell
.\build\build\generators\virtual_python_env.bat
```

#### 步骤 3: 安装 PyInstaller 依赖
```powershell
pip install pyinstaller==6.11.1 pyinstaller-hooks-contrib
pip install pycryptodome esdk-obs-python pyyaml
```

#### 步骤 4: PyInstaller 打包（5-15 分钟）
```powershell
cd deploy
pyinstaller UltiMaker-Cura.spec -y
```

#### 步骤 5: 测试应用
```powershell
.\dist\UltiMaker-Cura\UltiMaker-Cura.exe
```

#### 步骤 6: 创建安装程序（可选）
```powershell
cd ..
python packaging\NSIS\create_windows_installer.py `
    --source_path . `
    --dist_path deploy\dist `
    --filename "UltiMaker-Cura-5.11.0-Windows-X64.exe" `
    --version "5.11.0"
```

---

## 🌐 环境配置

### QA 环境（默认）
```batch
set CURA_ENV=qa
deploy\dist\UltiMaker-Cura\UltiMaker-Cura.exe
```

**API 端点**:
- 认证: `https://qa-datacenter.gongfudou.com`
- 业务: `https://qa-appgw.gongfudou.com`

### 生产环境
```batch
set CURA_ENV=production
deploy\dist\UltiMaker-Cura\UltiMaker-Cura.exe
```

**API 端点**:
- 认证: `https://dcenter.kfb-1.com`
- 业务: `https://print.wisebeginner3d.com`

配置文件: `cura/config.py`

---

## 🐛 常见问题

### ❌ `conan` 命令未找到
```powershell
pip install conan>=2.7.0
```

### ❌ Conan Deploy 失败
```powershell
# 清理缓存重试
conan remove "*" -c
conan install . --deployer=full_deploy --deployer-folder=deploy --build=missing
```

### ❌ `virtual_python_env.bat` 不存在
确保 Conan Deploy 成功完成，该文件应该在：
```
build\build\generators\virtual_python_env.bat
```

### ❌ PyInstaller 打包失败
```powershell
# 查看详细日志
cd deploy
pyinstaller UltiMaker-Cura.spec -y --log-level=DEBUG
```

### ❌ 缺少 Visual C++ 编译器
安装 Visual Studio 2022：
1. 下载：https://visualstudio.microsoft.com/downloads/
2. 选择 "Desktop development with C++"
3. 重新运行打包脚本

### ❌ NSIS 命令未找到
1. 下载 NSIS：https://nsis.sourceforge.io/Download
2. 安装到默认路径
3. 添加到 PATH：
   ```powershell
   $env:Path += ";C:\Program Files (x86)\NSIS"
   ```

### ❌ 应用运行时崩溃
查看日志：
```powershell
type %APPDATA%\cura\5.11\cura.log
```

---

## 📂 输出文件结构

```
deploy/
├── dist/
│   ├── UltiMaker-Cura/                             # 应用程序目录
│   │   ├── UltiMaker-Cura.exe                      # ✅ 主程序
│   │   ├── share/
│   │   │   ├── cura/
│   │   │   │   ├── resources/                      # Cura 资源
│   │   │   │   │   ├── definitions/               # 打印机定义
│   │   │   │   │   ├── materials/                 # 材料配置
│   │   │   │   │   └── qml/                       # QML 界面
│   │   │   │   └── plugins/                       # Cura 插件
│   │   │   └── uranium/
│   │   │       ├── qml/                            # Uranium QML 组件
│   │   │       └── plugins/                        # Uranium 插件
│   │   ├── CuraEngine.exe                          # 切片引擎
│   │   └── ... (Python DLL 和依赖库)
│   │
│   └── UltiMaker-Cura-5.11.0-Windows-X64.exe       # ✅ NSIS 安装程序
```

---

## ✅ 验收测试

打包完成后，请测试以下功能：

- [ ] ✅ 应用程序可以正常启动
- [ ] ✅ 界面正常显示，无 QML 错误
- [ ] ✅ 可以添加 Explorer 3 打印机
- [ ] ✅ 登录功能正常（测试 QA 和生产环境）
- [ ] ✅ 云端导入/上传配置功能正常
- [ ] ✅ G-code 上传功能正常
- [ ] ✅ 切片功能正常（CuraEngine 正常工作）
- [ ] ✅ 3D 预览和视图正常
- [ ] ✅ 应用程序可以正常退出

---

## 📚 详细文档

- 📘 **完整打包指南**: `tools/BUILD_WINDOWS_GUIDE.md`
- 📗 **快速参考**: `tools/QUICK_START.md`
- 📕 **打包总览**: `tools/PACKAGING_README.md`
- 📙 **API 配置**: `API_CONFIG.md`

---

## 📊 打包时间参考

| 步骤 | 预计时间 | 说明 |
|------|---------|------|
| Conan Deploy | 20-60 分钟 | 首次打包，下载依赖 |
| PyInstaller | 5-15 分钟 | 打包应用程序 |
| NSIS 安装程序 | 2-5 分钟 | 创建安装程序 |
| **总计** | **30-80 分钟** | 有缓存时更快 |

*再次打包（有缓存）约 15-30 分钟*

---

## 🎯 快速命令汇总

```batch
:: 1. 环境检查
.\tools\scripts\check_windows_env.bat

:: 2. 完整打包
.\tools\scripts\build_windows.bat

:: 3. 快速打包（无安装程序）
.\tools\scripts\quick_build_windows.bat

:: 4. 测试应用（QA 环境）
set CURA_ENV=qa
deploy\dist\UltiMaker-Cura\UltiMaker-Cura.exe

:: 5. 测试应用（生产环境）
set CURA_ENV=production
deploy\dist\UltiMaker-Cura\UltiMaker-Cura.exe

:: 6. 查看日志
type %APPDATA%\cura\5.11\cura.log

:: 7. 清理（重新开始）
rmdir /s /q deploy dist build
```

---

## 💡 提示

1. **首次打包时间较长**：Conan 需要下载和编译依赖，请耐心等待
2. **使用 SSD**：可以显著提升打包速度
3. **网络加速**：配置 Conan 远程镜像可以加快下载
4. **保留缓存**：不要删除 `build/` 目录，下次打包会更快
5. **虚拟环境**：始终在激活虚拟环境后运行 PyInstaller

---

## 🆘 需要帮助？

如果遇到问题，请提供：

1. Windows 版本（Win 10/11）
2. Python 版本：`python --version`
3. Conan 版本：`conan --version`
4. 错误信息或日志
5. 使用的打包脚本
6. 具体步骤

---

**最后更新**: 2025-12-24  
**适用版本**: Cura 5.11.0  
**平台**: Windows 10/11 (x64)

