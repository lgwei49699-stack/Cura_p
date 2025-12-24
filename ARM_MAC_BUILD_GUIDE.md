# ARM Mac (Apple Silicon) 打包指南

**重要提示**: 您的 Mac 是 ARM 架构（Apple Silicon），打包 Windows 程序需要特别注意兼容性问题。

---

## ⚠️ 关键问题：架构兼容性

### 问题说明

```
ARM Mac
  ↓
虚拟机 (Parallels/VMware)
  ↓
Windows 11 ARM 版本
  ↓
打包出来的程序
  ↓
❌ 只能在 Windows ARM 设备上运行
❌ 不能在普通的 Windows 10/11 PC 上运行（x64 架构）
```

**现实情况**:
- 99% 的 Windows PC 使用 x64 架构
- 只有极少数设备（如 Surface Pro X）使用 ARM 架构
- **在 ARM Mac 虚拟机中打的 Windows 包，大多数用户无法使用**

---

## ✅ 推荐方案

### 方案一：GitHub Actions（最推荐）⭐⭐⭐⭐⭐

**优势**：
- ✅ 使用真实的 **x64 Windows** 环境
- ✅ 打包出的程序**兼容所有 Windows PC**
- ✅ 完全免费（公开仓库）
- ✅ 不占用本地资源
- ✅ 可以同时打 macOS 和 Windows 包

**使用步骤**：

#### 1. 推送代码到 GitHub

```bash
cd /Users/zhouwude/Desktop/project/CuraClient/Cura_p

# 如果还没有 Git 仓库
git init
git add .
git commit -m "Add build workflows"

# 添加远程仓库（替换为您的地址）
git remote add origin https://github.com/YOUR_USERNAME/Cura_p.git
git push -u origin main
```

#### 2. 在 GitHub 上触发构建

1. 打开 GitHub 仓库页面
2. 点击 **"Actions"** 标签
3. 选择 **"Build Windows Package"**
4. 点击 **"Run workflow"**
5. 选择 **Environment**: `production`
6. 点击绿色的 **"Run workflow"** 按钮

#### 3. 等待构建（60-120 分钟）

您可以：
- ☕ 喝杯咖啡
- 💼 继续其他工作
- 📱 收到邮件通知后再回来

#### 4. 下载构建产物

1. 构建完成后，点击完成的 workflow
2. 滚动到底部 **"Artifacts"**
3. 下载：
   - `cura-windows-x64-installer` - **安装程序（推荐）**
   - `cura-windows-x64-app` - 应用程序目录

**结果**: ✅ 获得真正的 **x64 Windows** 安装包，兼容所有 Windows 10/11 PC

**详细教程**: 见 `tools/GITHUB_ACTIONS_GUIDE.md`

---

### 方案二：云服务器（备选）⭐⭐⭐

租用 **x64 Windows** 云服务器进行构建。

#### 推荐服务商

| 服务商 | 费用 | 配置 |
|--------|------|------|
| **Azure** | ~$0.5-1/小时 | Windows Server 2022 x64 |
| **AWS EC2** | ~$0.4-0.8/小时 | Windows Server x64 |
| **阿里云** | ~¥0.5-1/小时 | Windows Server x64 |

#### 使用步骤

```bash
# 1. 在 Mac 上安装 Microsoft Remote Desktop
brew install --cask microsoft-remote-desktop

# 2. 租用云服务器（选择 x64 Windows）
# 3. 使用 Remote Desktop 连接
# 4. 在云服务器上运行打包脚本

# 将项目上传到云服务器
scp -r Cura_p user@cloud-server-ip:/path/

# 远程连接后
cd C:\path\to\Cura_p
.\tools\scripts\build_windows.bat
```

**成本**: 每次构建约 $1-2（按小时计费）

---

### 方案三：借用 Intel Mac 或 Windows PC（实用）⭐⭐⭐⭐

如果您有朋友/同事有 **Intel Mac** 或 **Windows PC**：

#### Intel Mac

```bash
# 在 Intel Mac 上可以运行 x64 虚拟机
# 打包出的是标准 x64 Windows 程序

# 1. 安装 Parallels/VirtualBox
# 2. 安装 Windows 11 x64 版本
# 3. 运行打包脚本
.\tools\scripts\build_windows.bat
```

#### Windows PC

```bash
# 直接在 Windows PC 上打包
# 这是最直接的方式

cd C:\path\to\Cura_p
.\tools\scripts\build_windows.bat
```

---

## 📊 方案对比（ARM Mac 用户）

| 方案 | 兼容性 | 成本 | 时间 | 难度 | 推荐度 |
|------|--------|------|------|------|--------|
| **GitHub Actions** | ✅ x64 | 免费 | 60-120 min | ⭐ | ⭐⭐⭐⭐⭐ |
| **云服务器 (x64)** | ✅ x64 | ~$1-2/次 | 45-115 min | ⭐⭐ | ⭐⭐⭐ |
| **Intel Mac 虚拟机** | ✅ x64 | 无 | 45-115 min | ⭐⭐ | ⭐⭐⭐⭐ |
| **Windows PC** | ✅ x64 | 无 | 45-115 min | ⭐ | ⭐⭐⭐⭐⭐ |
| **ARM Mac 虚拟机** | ❌ ARM | ~$99/年 | 45-115 min | ⭐⭐ | ❌ 不推荐 |

---

## 🎯 快速决策树

```
您有 ARM Mac，想打 Windows 包
    ↓
有 GitHub 账号？
    ├─ 是 → 【使用 GitHub Actions】⭐⭐⭐⭐⭐
    │        免费，100% 兼容
    │
    └─ 否 → 有朋友/同事有 Intel Mac 或 Windows PC？
             ├─ 是 → 【借用机器打包】⭐⭐⭐⭐⭐
             │        最简单直接
             │
             └─ 否 → 预算充足？
                      ├─ 是 → 【租用云服务器】⭐⭐⭐
                      │        按小时付费，灵活
                      │
                      └─ 否 → 【创建 GitHub 账号】⭐⭐⭐⭐⭐
                               使用 GitHub Actions
                               公开仓库完全免费
```

---

## 💡 我的建议

### 如果您是个人开发者

**推荐**: GitHub Actions

```bash
# 1. 创建 GitHub 账号（免费）
# 2. 推送代码
git push origin main

# 3. 在 Actions 页面点击 "Run workflow"
# 4. 等待 60-120 分钟
# 5. 下载 x64 安装包
```

**优点**:
- 完全免费
- 100% 兼容所有 Windows PC
- 不需要购买任何软件
- 不占用本地资源

### 如果您是团队开发

**推荐**: GitHub Actions + 自动化

```yaml
# 配置自动构建
on:
  push:
    branches: [ main ]

# 推送代码自动触发构建
# 团队成员都可以下载
```

---

## ⚠️ 不要做的事

### ❌ 不要在 ARM Mac 上使用虚拟机打 Windows 包

```
ARM Mac + Parallels + Windows ARM
  ↓
打包出 ARM Windows 程序
  ↓
❌ 大多数 Windows 用户无法使用
❌ 浪费时间和金钱
```

**原因**:
- Parallels Desktop 在 ARM Mac 上只能运行 Windows ARM
- Windows ARM 虽然有 x64 模拟，但打包出的是原生 ARM 程序
- 99% 的 Windows PC 使用 x64 架构，无法运行 ARM 程序

---

## 📚 相关文档

### 必读文档（按顺序）

1. **本文档** - ARM Mac 专用指南
2. `tools/GITHUB_ACTIONS_GUIDE.md` - GitHub Actions 详细教程
3. `tools/BUILD_WINDOWS_GUIDE.md` - Windows 打包完整指南

### 其他文档

- `WINDOWS_BUILD_CN.md` - Windows 打包快速指引
- `tools/QUICK_START.md` - 快速参考
- `tools/PACKAGING_README.md` - 跨平台打包总览

---

## 🆘 常见问题

### Q: 我已经买了 Parallels，能用吗？

**A**: 可以用来打 **macOS** 包，但**不能**用来打通用的 **Windows** 包。

```
ARM Mac + Parallels
  ├─ ✅ 打 macOS ARM 包（可用）
  └─ ❌ 打 Windows x64 包（不兼容）
```

### Q: Windows ARM 版本不能模拟 x64 吗？

**A**: 可以**运行** x64 程序（模拟），但打包时生成的是**原生 ARM** 程序。

```
Windows ARM 版本
  ├─ ✅ 可以运行 x64 程序（通过模拟）
  └─ ❌ 打包生成的是 ARM 程序（不兼容 x64 PC）
```

### Q: GitHub Actions 要钱吗？

**A**: 公开仓库**完全免费**，私有仓库有免费额度。

| 仓库类型 | 免费额度 | 推荐 |
|---------|---------|------|
| 公开仓库 | 无限制 | ⭐⭐⭐⭐⭐ |
| 私有仓库 | 2000 分钟/月 | ⭐⭐⭐⭐ |

一次完整构建约 90 分钟，免费额度可以构建约 20 次/月。

### Q: 构建要多久？

**A**: 

| 平台 | 首次构建 | 有缓存 |
|------|---------|--------|
| Windows x64 | 60-120 min | 30-60 min |
| macOS ARM | 40-90 min | 20-50 min |

### Q: 我的代码是私有的，能用 GitHub Actions 吗？

**A**: 可以，私有仓库也能用，只是有免费额度限制。

---

## ✅ 开始使用

### 最简单的 3 步

```bash
# 1. 推送代码到 GitHub
git push origin main

# 2. 在 GitHub 网页上点击 "Run workflow"

# 3. 等待完成，下载 x64 安装包
```

就是这么简单！🎉

---

## 📞 获取帮助

如果遇到问题：

1. 查看 `tools/GITHUB_ACTIONS_GUIDE.md` 详细教程
2. 查看 GitHub Actions 运行日志
3. 搜索错误信息

---

**最后更新**: 2025-12-24  
**适用于**: ARM Mac (Apple Silicon, M1/M2/M3)  
**推荐方案**: GitHub Actions ⭐⭐⭐⭐⭐

