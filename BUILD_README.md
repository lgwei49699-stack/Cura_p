# Cura 打包文档导航

选择适合您的指南：

---

## 🎯 根据您的情况选择

### 您使用的是 ARM Mac（Apple Silicon, M1/M2/M3）？

📘 **[ARM_MAC_BUILD_GUIDE.md](ARM_MAC_BUILD_GUIDE.md)** ⭐ 必读

**为什么要读**：
- ARM Mac 虚拟机打的 Windows 包**不兼容**大多数 Windows PC
- 本指南教您正确的打包方法

**关键信息**：
```
❌ ARM Mac → 虚拟机 → Windows ARM → ❌ 不兼容大多数 PC
✅ ARM Mac → GitHub Actions → Windows x64 → ✅ 兼容所有 PC
```

---

### 您想使用 GitHub Actions 自动化构建？

📗 **[tools/GITHUB_ACTIONS_GUIDE.md](tools/GITHUB_ACTIONS_GUIDE.md)** ⭐ 推荐

**适用场景**：
- ✅ ARM Mac 用户打 Windows 包（最佳方案）
- ✅ 不想占用本地资源
- ✅ 需要同时打多个平台的包
- ✅ 团队协作

**快速开始**：
1. 推送代码到 GitHub
2. 在 Actions 页面点击 "Run workflow"
3. 下载构建产物

---

### 您在 Windows 上打包？

📙 **[WINDOWS_BUILD_CN.md](WINDOWS_BUILD_CN.md)** - 中文快速指引

**或**

📕 **[tools/BUILD_WINDOWS_GUIDE.md](tools/BUILD_WINDOWS_GUIDE.md)** - 详细指南

**快速命令**：
```batch
:: 环境检查
.\tools\scripts\check_windows_env.bat

:: 完整打包
.\tools\scripts\build_windows.bat

:: 快速打包（无安装程序）
.\tools\scripts\quick_build_windows.bat
```

---

### 您在 macOS 上打包？

📒 **[tools/BUILD_PACKAGE_GUIDE.md](tools/BUILD_PACKAGE_GUIDE.md)** - macOS 打包指南

**快速命令**：
```bash
# 环境检查
./tools/scripts/check_macos_env.sh  # (如果有)

# 完整打包（推荐）
./tools/scripts/build_package_macos.sh

# 快速打包（无 DMG）
./tools/scripts/quick_build_macos.sh
```

---

### 您需要快速查阅命令？

📋 **[tools/QUICK_START.md](tools/QUICK_START.md)** - 命令速查表

---

### 您想了解整体打包流程？

📚 **[tools/PACKAGING_README.md](tools/PACKAGING_README.md)** - 跨平台打包总览

---

## 📊 快速决策流程图

```
开始
  │
  ├─ 您使用的是 ARM Mac？
  │   └─ 是 → 【ARM_MAC_BUILD_GUIDE.md】⭐ 必读
  │
  ├─ 想使用云端自动构建？
  │   └─ 是 → 【GITHUB_ACTIONS_GUIDE.md】⭐ 推荐
  │
  ├─ 在 Windows 上打包？
  │   └─ 是 → 【WINDOWS_BUILD_CN.md】或【BUILD_WINDOWS_GUIDE.md】
  │
  ├─ 在 macOS 上打包？
  │   └─ 是 → 【BUILD_PACKAGE_GUIDE.md】
  │
  └─ 只想快速查命令？
      └─ 是 → 【QUICK_START.md】
```

---

## 📚 完整文档列表

### 核心指南

| 文档 | 说明 | 推荐度 |
|------|------|--------|
| `ARM_MAC_BUILD_GUIDE.md` | **ARM Mac 专用指南** | ⭐⭐⭐⭐⭐ (ARM Mac 必读) |
| `GITHUB_ACTIONS_GUIDE.md` | **GitHub Actions 教程** | ⭐⭐⭐⭐⭐ (自动化必备) |
| `WINDOWS_BUILD_CN.md` | Windows 快速指引（中文） | ⭐⭐⭐⭐⭐ |
| `BUILD_WINDOWS_GUIDE.md` | Windows 详细指南 | ⭐⭐⭐⭐ |
| `BUILD_PACKAGE_GUIDE.md` | macOS 打包指南 | ⭐⭐⭐⭐⭐ |

### 参考文档

| 文档 | 说明 |
|------|------|
| `QUICK_START.md` | 快速参考卡片 |
| `PACKAGING_README.md` | 跨平台打包总览 |
| `WINDOWS_BUILD_FILES.md` | Windows 打包文件清单 |
| `API_CONFIG.md` | API 配置说明 |

---

## 🔧 可用脚本

### Windows 脚本

| 脚本 | 用途 |
|------|------|
| `tools/scripts/check_windows_env.bat` | 检查 Windows 环境 |
| `tools/scripts/build_windows.bat` | 完整打包（含安装程序） |
| `tools/scripts/build_windows.ps1` | PowerShell 完整打包 |
| `tools/scripts/quick_build_windows.bat` | 快速打包（无安装程序） |

### macOS 脚本

| 脚本 | 用途 |
|------|------|
| `tools/scripts/build_package_macos.sh` | 完整打包（含 DMG） |
| `tools/scripts/quick_build_macos.sh` | 快速打包（无 DMG） |

### GitHub Actions Workflows

| Workflow | 用途 |
|----------|------|
| `.github/workflows/build-windows.yml` | 自动构建 Windows x64 包 |
| `.github/workflows/build-macos.yml` | 自动构建 macOS 包 |

---

## 🎯 推荐阅读顺序

### 新手路径

1. **确认您的平台**
   - ARM Mac → `ARM_MAC_BUILD_GUIDE.md`
   - Windows → `WINDOWS_BUILD_CN.md`
   - macOS (Intel) → `BUILD_PACKAGE_GUIDE.md`

2. **了解自动化构建**
   - `GITHUB_ACTIONS_GUIDE.md`

3. **快速查阅命令**
   - `QUICK_START.md`

### 进阶路径

1. **深入理解打包流程**
   - `PACKAGING_README.md`
   - `BUILD_WINDOWS_GUIDE.md`

2. **自定义构建流程**
   - 查看 `.github/workflows/` 中的配置
   - 查看 `tools/scripts/` 中的脚本

3. **配置 API 环境**
   - `API_CONFIG.md`
   - `cura/config.py`

---

## 💡 常见场景

### 场景 1: 我有 ARM Mac，想打 Windows 包

```
1. 阅读: ARM_MAC_BUILD_GUIDE.md
2. 选择: GitHub Actions（推荐）
3. 跟随: GITHUB_ACTIONS_GUIDE.md
4. 结果: 获得兼容所有 Windows PC 的 x64 安装包
```

### 场景 2: 我在 Windows 上，想本地打包

```
1. 阅读: WINDOWS_BUILD_CN.md
2. 运行: .\tools\scripts\check_windows_env.bat
3. 执行: .\tools\scripts\build_windows.bat
4. 结果: deploy\dist\ 中获得安装包
```

### 场景 3: 我想自动化构建

```
1. 阅读: GITHUB_ACTIONS_GUIDE.md
2. 推送: git push origin main
3. 触发: 在 GitHub Actions 页面点击 "Run workflow"
4. 结果: 自动构建，下载产物
```

### 场景 4: 我在 macOS 上打包

```
1. 阅读: BUILD_PACKAGE_GUIDE.md
2. 运行: ./tools/scripts/build_package_macos.sh
3. 结果: deploy/dist/ 中获得 .app 和 .dmg
```

---

## 🌐 API 环境配置

所有平台都支持通过环境变量切换 API 环境：

### QA 环境（默认）
```bash
# macOS/Linux
export CURA_ENV=qa

# Windows
set CURA_ENV=qa
```

### 生产环境
```bash
# macOS/Linux
export CURA_ENV=production

# Windows
set CURA_ENV=production
```

详见：`API_CONFIG.md`

---

## ✅ 检查清单

打包前：
- [ ] 确认 Python 3.11.x 已安装
- [ ] 确认 Conan 2.7+ 已安装
- [ ] 确认开发工具已安装（VS 2022 / Xcode）
- [ ] 阅读了相应平台的指南

打包后：
- [ ] 应用程序可以正常启动
- [ ] Explorer 3 打印机可以加载
- [ ] 登录功能正常
- [ ] 云端导入/上传功能正常
- [ ] 切片功能正常

---

## 🆘 获取帮助

遇到问题时：

1. **查阅相关文档**（见上方列表）
2. **查看脚本输出的错误信息**
3. **查看应用日志**：
   - macOS: `~/Library/Application Support/cura/5.11/cura.log`
   - Windows: `%APPDATA%\cura\5.11\cura.log`
4. **查看 GitHub Actions 运行日志**（如使用云端构建）

---

## 📈 版本信息

- **Cura 版本**: 5.11.0
- **Python 版本**: 3.11.x
- **Conan 版本**: 2.7+
- **PyInstaller 版本**: 6.11.1

---

**最后更新**: 2025-12-24  
**支持平台**: macOS (ARM64/X64), Windows (X64)

