# 配置上传处理器

import json
import os
import uuid
import tempfile
from typing import Optional, Dict, Any, Callable

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, pyqtProperty, QUrl, QUrlQuery, QTimer, Qt
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from UM.Logger import Logger
from UM.Application import Application
from UM.Message import Message
from cura.GCodeUploadByToken import GCodeUploadByToken
from cura.config import OBS_TOKEN_URL, CONFIG_ADD_URL, DEVICE_SLICE_TYPE_URL


class ConfigUploadHandler(QObject):
    """处理切片配置的上传"""
    
    # 信号定义
    uploadSuccess = pyqtSignal()
    uploadFailed = pyqtSignal(str, arguments=["errorMessage"])
    isExplorer3MachineChanged = pyqtSignal()
    cloudConfigsFetched = pyqtSignal(list, arguments=["configs"])
    cloudConfigsFetchFailed = pyqtSignal(str, arguments=["errorMessage"])
    
    # 常量：关键参数列表（用于验证和调试）
    KEY_MONITORING_PARAMS = [
        "layer_height", "wall_thickness", "wall_line_count", 
        "xy_offset", "horizontal_expansion", "infill_sparse_density", "infill_pattern"
    ]
    
    # 常量：需要强制保存的关键参数
    CRITICAL_SETTINGS = [
        # 基础层高和壁厚
        "layer_height",
        "wall_thickness",
        "xy_offset",
        "horizontal_expansion",
        # 顶底层
        "roofing_layer_count",
        "flooring_layer_count",
        "top_layers",
        "bottom_layers",
        "top_thickness",
        "bottom_thickness",
        "top_bottom_thickness",
        # 填充
        "infill_sparse_density",
        "infill_pattern",
        "infill_line_distance",
        "infill_sparse_thickness",
        # 温度
        "material_print_temperature",
        "material_bed_temperature",
        # 速度
        "speed_print",
        "skirt_brim_speed",
        # 加速度和抖动
        "jerk_enabled",
        # 回抽和Z抬升 (per_extruder 设置)
        "retraction_enable",
        "retraction_amount",
        "retraction_speed",
        "retraction_combing",
        "retraction_hop_enabled",
        "retraction_hop",
        "retraction_hop_only_when_collides",
        # 冷却风扇 (per_extruder 设置)
        "cool_fan_enabled",
        "cool_fan_speed",
        "cool_fan_speed_min",
        "cool_fan_speed_max",
        # 支撑
        "support_infill_rate",
        "support_material_flow",
        "speed_support_interface",
        "support_enable",
        "support_type"
    ]
    
    # 常量：per-extruder 设置（这些设置不应该从挤出头合并到全局）
    PER_EXTRUDER_SETTINGS = {
        "cool_fan_speed", "cool_fan_speed_min", "cool_fan_speed_max",
        "cool_fan_enabled",
        "retraction_enable", "retraction_amount", "retraction_speed",
        "retraction_combing", "retraction_hop_enabled", "retraction_hop",
        "retraction_hop_only_when_collides"
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._application = Application.getInstance()
        self._is_explorer3_machine = False
        self._machine_signal_connected = False
        
        # 调试模式开关（生产环境可设为 False）
        self._debug_mode = True  # 设为 False 可减少日志输出
        
        # 初始化网络管理器
        self.network_manager = QNetworkAccessManager(self)
        self.reply_obs_token = None
        self.reply_save_config = None
        self.reply_fetch_configs = None
        self._token_callback = None
        
        # 初始化上传器
        self._uploader = GCodeUploadByToken(self)
        self._uploader.uploadFinished.connect(self._onUploadFinished)
        self._uploader.uploadError.connect(self._onUploadError)
        
        # 临时文件路径和配置信息
        self._temp_config_file = None
        self._current_config_name = ""
        self._current_config_remarks = ""
        
        # 云端配置导入相关
        self._current_import_config_name = ""
        self.reply_download_config = None
        self._importing_message = None  # 导入中的加载提示
        self._import_state = None  # 批处理导入状态
        
        # 延迟连接 MachineManager 信号，等应用初始化完成
        self._application.engineCreatedSignal.connect(self._onEngineCreated)
    
    def _onEngineCreated(self):
        """应用引擎创建完成后连接 MachineManager 信号"""
        if self._machine_signal_connected:
            return
        
        try:
            machine_manager = self._application.getMachineManager()
            if machine_manager:
                machine_manager.activeMachineIdChanged.connect(self._onMachineChanged)
                self._machine_signal_connected = True
                
                # 初始化时也使用延迟检查，确保 MachineManager 完全就绪
                QTimer.singleShot(100, self._doInitialCheck)
        except Exception as e:
            Logger.logException("e", f"连接 MachineManager 信号失败: {str(e)}")
    
    def _doInitialCheck(self):
        """初始化时的延迟检查"""
        self._is_explorer3_machine = self._checkIsExplorer3()
        self.isExplorer3MachineChanged.emit()
    
    def _onMachineChanged(self):
        """机器切换时检查并发出信号，让 QML 更新可见性"""
        # 使用延迟检查（100ms），确保 MachineManager 的 activeMachine 已经更新
        QTimer.singleShot(100, self._doMachineCheck)
    
    def _doMachineCheck(self):
        """延迟执行的机器检查（确保 activeMachine 已更新）"""
        old_value = self._is_explorer3_machine
        self._is_explorer3_machine = self._checkIsExplorer3()
        
        # 只有当值改变时才发出信号，避免不必要的 QML 更新
        if old_value != self._is_explorer3_machine:
        self.isExplorer3MachineChanged.emit()
    
    def _log_debug(self, message: str):
        """条件性调试日志"""
        if self._debug_mode:
            Logger.log("d", message)
    
    def _log_key_params(self, global_stack, container, prefix: str = ""):
        """记录关键参数的值（用于调试）"""
        if not self._debug_mode:
            return
        
        for key in self.KEY_MONITORING_PARAMS:
            try:
                value = container.getProperty(key, "value") if container else None
                stack_value = global_stack.getProperty(key, "value") if global_stack else None
                if value is not None or stack_value is not None:
                    Logger.log("d", f"{prefix}{key}: container={value}, stack={stack_value}")
            except Exception as e:
                Logger.log("w", f"{prefix}无法读取 {key}: {str(e)}")
    
    def _prepareForSave(self) -> Optional[tuple]:
        """
        准备保存操作，检查必要的前置条件
        
        :return: (global_stack, global_quality_changes) 或 None
        """
        machine_manager = self._application.getMachineManager()
        if not machine_manager:
            Logger.log("w", "无法获取 MachineManager")
            return None
        
        global_stack = machine_manager.activeMachine
        if not global_stack:
            Logger.log("w", "无法获取 activeMachine")
            return None
        
        global_quality_changes = global_stack.qualityChanges
        if not global_quality_changes or global_quality_changes.getId() == "empty_quality_changes":
            Logger.log("w", "当前没有自定义质量配置，跳过强制保存")
            return None
        
        return (global_stack, global_quality_changes)
    
    def _logCurrentStateBeforeSave(self, global_stack, global_quality_changes):
        """记录保存前的当前状态（调试用）"""
        Logger.log("d", " 当前状态检查（强制保存前）：")
        Logger.log("d", "  [全局配置]")
        
        for key in self.CRITICAL_SETTINGS:
            try:
                final_value = global_stack.getProperty(key, "value")
                qc_value = global_quality_changes.getProperty(key, "value")
                user_value = global_stack.userChanges.getProperty(key, "value")
                
                if final_value is not None or qc_value is not None or user_value is not None:
                    Logger.log("d", f"    {key}:")
                    Logger.log("d", f"      final={final_value}, qc={qc_value}, user={user_value}")
            except Exception as e:
                Logger.log("w", f"    无法检查 {key}: {str(e)}")
        
        # 检查挤出头配置
        Logger.log("d", "  [挤出头配置]")
        for extruder in global_stack.extruderList:
            extruder_qc = extruder.qualityChanges
            if extruder_qc and extruder_qc.getId() != "empty_quality_changes":
                Logger.log("d", f"    Extruder {extruder.getMetaDataEntry('position')}: {extruder_qc.getId()}")
                for key in ["infill_sparse_density", "infill_pattern", "cool_fan_speed", "retraction_hop"]:
                    try:
                        ext_qc_value = extruder_qc.getProperty(key, "value")
                        if ext_qc_value is not None:
                            Logger.log("d", f"      {key} = {ext_qc_value}")
                    except Exception as e:
                        pass
    
    def _verifySaveResults(self, global_stack, global_quality_changes):
        """验证保存结果（调试用）"""
        Logger.log("d", "=" * 60)
        Logger.log("d", " 验证：检查关键参数是否真的保存成功")
        Logger.log("d", "=" * 60)
        Logger.log("d", "  [全局配置]")
        
        for key in self.CRITICAL_SETTINGS:
            try:
                final_value = global_stack.getProperty(key, "value")
                qc_value = global_quality_changes.getProperty(key, "value")
                user_value = global_stack.userChanges.getProperty(key, "value")
                
                if final_value is not None or qc_value is not None:
                    Logger.log("d", f"    {key}:")
                    Logger.log("d", f"      - final={final_value}, qc={qc_value}, user={user_value}")
                    
                    if qc_value != final_value and user_value != final_value:
                        Logger.log("w", f"  警告：{key} 的最终值 ({final_value}) 没有保存到任何全局容器中！")
            except Exception as e:
                Logger.log("w", f"    无法验证 {key}: {str(e)}")
        
        # 验证挤出头配置
        Logger.log("d", "  [挤出头配置]")
        for extruder in global_stack.extruderList:
            extruder_qc = extruder.qualityChanges
            if extruder_qc and extruder_qc.getId() != "empty_quality_changes":
                Logger.log("d", f"    Extruder {extruder.getMetaDataEntry('position')}: {extruder_qc.getId()}")
                for key in ["infill_sparse_density", "infill_pattern", "cool_fan_speed", "retraction_hop"]:
                    try:
                        ext_value = extruder_qc.getProperty(key, "value")
                        if ext_value is not None:
                            Logger.log("d", f"      {key} = {ext_value}")
                    except Exception as e:
                        pass
    
    def _mergeExtruderSettingsToGlobal(self, global_stack, global_quality_changes) -> int:
        """
        将挤出头配置中的非 per_extruder 设置合并到全局配置
        
        :return: 合并的设置数量
        """
        merged_count = 0
        
        self._log_debug("检查挤出头配置并合并非 per_extruder 设置...")
        
        for extruder in global_stack.extruderList:
            extruder_qc = extruder.qualityChanges
            if extruder_qc and extruder_qc.getId() != "empty_quality_changes":
                extruder_pos = extruder.getMetaDataEntry('position')
                self._log_debug(f"  检查 Extruder {extruder_pos}: {extruder_qc.getId()}")
                
                # 只合并非 per_extruder 的设置
                for key in self.CRITICAL_SETTINGS:
                    # 跳过 per_extruder 设置
                    if key in self.PER_EXTRUDER_SETTINGS:
                        continue
                    
                    try:
                        ext_value = extruder_qc.getProperty(key, "value")
                        if ext_value is not None:
                            # 挤出头配置中有这个值，检查是否需要复制到全局配置
                            global_qc_value = global_quality_changes.getProperty(key, "value")
                            if ext_value != global_qc_value:
                                self._log_debug(f"    发现挤出头配置中的值: {key} = {ext_value}")
                                global_quality_changes.setProperty(key, "value", ext_value)
                                merged_count += 1
                                self._log_debug(f" 已复制到全局配置: {key} = {global_qc_value} → {ext_value}")
                    except Exception as e:
                        Logger.log("w", f"    无法合并 {key}: {str(e)}")
        
        return merged_count
    
    def _saveCriticalSettings(self, global_stack, global_quality_changes) -> tuple[int, int]:
        """
        保存关键参数到 qualityChanges
        
        :return: (saved_count, skipped_count)
        """
        saved_count = 0
        skipped_count = 0
        
        for key in self.CRITICAL_SETTINGS:
            try:
                # 获取当前最终计算值
                final_value = global_stack.getProperty(key, "value")
                
                # 获取各个容器中的值
                qc_value = global_quality_changes.getProperty(key, "value")
                user_value = global_stack.userChanges.getProperty(key, "value")
                
                # 优先级：userChanges > final_value (如果 userChanges 有值，说明用户修改过)
                value_to_save = user_value if user_value is not None else final_value
                
                # 如果值不同，强制保存
                if value_to_save != qc_value:
                    # 尝试保存到 qualityChanges
                    global_quality_changes.setProperty(key, "value", value_to_save)
                    
                    # 验证是否真的保存成功
                    saved_value = global_quality_changes.getProperty(key, "value")
                    if saved_value == value_to_save:
                        saved_count += 1
                        source = "userChanges" if user_value is not None else "final"
                        self._log_debug(f" 保存成功: {key} = {qc_value} → {value_to_save} (from {source})")
                        
                        # 如果是从 userChanges 复制过来的，清空 userChanges 中的这个设置
                        if user_value is not None:
                            try:
                                global_stack.userChanges.removeInstance(key)
                                self._log_debug(f"     (已从 userChanges 移除)")
                            except Exception as e:
                                Logger.log("w", f"无法从 userChanges 移除 {key}: {str(e)}")
                    else:
                        skipped_count += 1
                        self._log_debug(f"  保存被忽略: {key} (可能是只读属性)")
                else:
                    self._log_debug(f"  ✓ 参数已最新: {key} = {value_to_save}")
                
            except Exception as e:
                Logger.log("w", f"无法保存设置 {key}: {str(e)}")
        
        return saved_count, skipped_count
    
    def _saveConfigToFile(self, all_settings: str, config_name: str, remarks: str) -> str:
        """
        保存配置到txt文件
        
        :param all_settings: all_settings_string
        :param config_name: 配置名称
        :param remarks: 备注
        :return: 保存的文件路径
        """
        # 生成UUID文件名
        file_uuid = str(uuid.uuid4())
        filename = f"{file_uuid}.txt"
        
        # 创建临时目录（如果不存在）
        temp_dir = tempfile.gettempdir()
        cura_config_dir = os.path.join(temp_dir, "cura_configs")
        os.makedirs(cura_config_dir, exist_ok=True)
        
        # 完整文件路径
        file_path = os.path.join(cura_config_dir, filename)
        
        # 保存文件（UTF-8无BOM）
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                # 直接写入配置字符串，不添加头部信息
                f.write(all_settings)
            
            Logger.log("i", f"配置已保存: {file_path}")
            self._temp_config_file = file_path
            return file_path
            
        except Exception as e:
            Logger.logException("e", f"写入配置文件失败: {str(e)}")
            raise
    
    def _onUploadFinished(self, success: bool, response_data: Dict):
        """上传完成回调"""
        try:
            if success:
                file_url = response_data.get('file_url', '')
                if file_url:
                    Logger.log("i", f" 配置上传成功！文件地址: {file_url}")
                    # 调用服务器 API 保存配置信息
                    self._saveConfigToServer(file_url)
                else:
                    Logger.log("i", f"配置上传成功: {response_data}")
                    self.uploadSuccess.emit()
            else:
                error_msg = response_data.get('error', '未知错误')
                Logger.log("e", f"配置上传失败: {error_msg}")
                self.uploadFailed.emit(error_msg)
                # 显示失败提示
                self._showMessage("上传失败", f"配置 '{self._current_config_name}' 上传失败：{error_msg}")
        finally:
            # 清理临时文件（可选，也可以保留用于调试）
            # if self._temp_config_file and os.path.exists(self._temp_config_file):
            #     try:
            #         os.remove(self._temp_config_file)
            #         Logger.log("d", f"已删除临时文件: {self._temp_config_file}")
            #     except Exception as e:
            #         Logger.log("w", f"删除临时文件失败: {str(e)}")
            pass
    
    def _onUploadError(self, error_message: str):
        """上传错误回调"""
        Logger.log("e", f"配置上传错误: {error_message}")
        self.uploadFailed.emit(error_message)
        # 显示错误提示
        self._showMessage("上传错误", f"配置 '{self._current_config_name}' 上传错误：{error_message}")
    
    def _saveConfigToServer(self, file_url: str):
        """
        保存配置信息到服务器
        
        :param file_url: 配置文件的 CDN URL
        """
        try:
            # 构建请求数据
            file_name = os.path.basename(file_url)
            request_data = {
                "name": self._current_config_name,
                "configFileUrl": file_url,
                "configFileName": file_name,
                "deviceType": "EP3",  # 固定值
                "info": self._current_config_remarks,
                "sliceType": "cura"  # 固定值
            }
            
            Logger.log("d", f"保存配置到服务器: {request_data}")
            
            # 构建请求
            url = QUrl(CONFIG_ADD_URL)
            request = QNetworkRequest(url)
            
            # 设置 Header
            auth_token = self._application.get_auth_token()
            if auth_token:
                request.setRawHeader(b"Authorization", auth_token.encode('utf-8'))
            request.setRawHeader(b"Biz", b"ZXBMan")
            request.setRawHeader(b"Content-Type", b"application/json")
            
            # 发送请求
            json_data = json.dumps(request_data).encode('utf-8')
            self.reply_save_config = self.network_manager.post(request, json_data)
            self.reply_save_config.finished.connect(self._onSaveConfigResponse)
            
        except Exception as e:
            Logger.logException("e", f"保存配置到服务器失败: {str(e)}")
            # 即使保存失败，也认为上传成功（文件已上传）
            self.uploadSuccess.emit()
            # 显示警告（文件已上传但保存信息失败）
            self._showMessage("上传完成", f"配置 '{self._current_config_name}' 文件已上传，但保存信息异常")
    
    def _onSaveConfigResponse(self):
        """处理保存配置到服务器的响应"""
        if not self.reply_save_config:
            return
        
        try:
            if self.reply_save_config.error() == QNetworkReply.NetworkError.NoError:
                data = self.reply_save_config.readAll()
                response_data = json.loads(data.data().decode('utf-8'))
                Logger.log("d", f"保存配置响应: {response_data}")
                
                if response_data.get("msg") == "success" or response_data.get("code") == 0:
                    Logger.log("i", " 配置信息已保存到服务器")
                    self.uploadSuccess.emit()
                    # 显示成功提示
                    self._showMessage("上传成功", f"配置 '{self._current_config_name}' 上传成功！")
                else:
                    error_msg = response_data.get("msg", "保存配置失败")
                    Logger.log("e", f"保存配置到服务器失败: {error_msg}")
                    # 即使保存失败，也认为上传成功（文件已上传）
                    self.uploadSuccess.emit()
                    # 显示警告（文件已上传但保存信息失败）
                    self._showMessage("上传完成", f"配置 '{self._current_config_name}' 文件已上传，但保存信息失败")
            else:
                err_str = self.reply_save_config.errorString()
                Logger.log("e", f"保存配置到服务器网络错误: {err_str}")
                # 即使保存失败，也认为上传成功（文件已上传）
                self.uploadSuccess.emit()
                # 显示警告（文件已上传但保存信息失败）
                self._showMessage("上传完成", f"配置 '{self._current_config_name}' 文件已上传，但保存信息失败")
        except Exception as e:
            Logger.logException("e", f"处理保存配置响应时出错: {str(e)}")
            self.uploadSuccess.emit()
            # 显示警告（文件已上传但处理响应异常）
            self._showMessage("上传完成", f"配置 '{self._current_config_name}' 文件已上传，但处理响应异常")
        finally:
            self.reply_save_config.deleteLater()
            self.reply_save_config = None
    
    def _getUploadToken(self, callback: Callable[[Dict[str, Any]], None] = None):
        """
        获取OBS上传令牌
        
        :param callback: 获取成功后的回调函数
        """
        self._token_callback = callback
        url = QUrl(OBS_TOKEN_URL)
        
        query = QUrlQuery()
        
        # 配置文件使用txt后缀
        rule_code = "print3dPermanently"
        if rule_code:
            query.addQueryItem("ruleCode", rule_code)
 
        suffix = "txt"  # 配置文件使用txt后缀
        if suffix:
            query.addQueryItem("suffix", suffix)
        
        url.setQuery(query)
        request = QNetworkRequest(url)
        
        # 获取认证token
        biz = "ZXBMan"
        try:
            from cura.CuraApplication import CuraApplication
            auth_token = CuraApplication.getInstance().get_auth_token()
            request.setRawHeader(b"Authorization", auth_token.encode('utf-8'))
            request.setRawHeader(b"Biz", biz.encode("utf-8"))
        except Exception as e:
            Logger.logException("e", f"获取认证token失败: {str(e)}")
            if callback:
                callback(None)
            return
        
        Logger.log("d", f"请求OBS令牌: {url.toString()}")
        self.reply_obs_token = self.network_manager.get(request)
        self.reply_obs_token.finished.connect(self._onObsTokenResponse)
    
    def _onObsTokenResponse(self):
        """处理OBS令牌响应"""
        try:
            if self.reply_obs_token.error() == QNetworkReply.NetworkError.NoError:
                data = self.reply_obs_token.readAll()      
                response_data = json.loads(data.data().decode('utf-8'))
                Logger.log("d", f"OBS令牌响应: {response_data}")
                
                if response_data.get("msg") == "success":
                    # 解析令牌数据
                    token_data = response_data.get("data", {})
                    header_data = {
                        'obs_url': token_data.get("host"),
                        'cdn': token_data.get("cdn"),
                        'key': token_data.get("key"), 
                        'policy': token_data.get("policy"),
                        'signature': token_data.get("signature"),
                        'AccessKeyId': token_data.get("accessid")
                    }
                    Logger.log("i", "OBS令牌获取成功")
                    
                    # 调用回调
                    if self._token_callback:
                        self._token_callback(header_data)
                else:
                    Logger.log("e", f"OBS令牌请求失败: {response_data.get('msg')}")
                    if self._token_callback:
                        self._token_callback(None)
            else:
                err_str = self.reply_obs_token.errorString()
                Logger.log("e", f"OBS令牌请求错误: {err_str}")
                if self._token_callback:
                    self._token_callback(None)
                    
        except Exception as e:
            Logger.logException("e", f"处理OBS令牌响应时出错: {str(e)}")
            if self._token_callback:
                self._token_callback(None)
        finally:
            if self.reply_obs_token:
                self.reply_obs_token.deleteLater()
                self.reply_obs_token = None
    
    @pyqtSlot(str, str)
    def uploadConfig(self, config_name: str, remarks: str):
        """
        上传配置到云端
        
        重要说明：
        - 上传时只会上传**已保存的配置**（qualityChanges）
        - **不会自动包含UI上未保存的修改**
        - 如果用户修改了参数但没有点击"保存"，这些修改**不会被上传**
        - 如果用户想上传最新修改，应该先点"保存"，然后再点"上传"
        
        :param config_name: 配置名称
        :param remarks: 备注
        """
        # 保存配置信息，用于后续保存到服务器
        self._current_config_name = config_name
        self._current_config_remarks = remarks
        
        try:
            # 步骤0：触发UI失去焦点，确保所有正在编辑的值被提交
            self._log_debug("=" * 60)
            self._log_debug(" 步骤0：触发UI失去焦点（blurSettings）")
            self._log_debug("=" * 60)
            
            machine_manager = self._application.getMachineManager()
            if machine_manager:
                try:
                    # 触发焦点丢失信号，强制UI提交当前正在编辑的值
                    machine_manager.blurSettings.emit()
                    self._log_debug("已触发 blurSettings 信号")
                    
                    # 使用定时器延迟执行，避免阻塞UI线程
                    QTimer.singleShot(100, lambda: self._continueUploadAfterBlur(config_name, remarks))
                    return  # 成功设置定时器，立即返回
                except Exception as e:
                    Logger.logException("w", f"触发 blurSettings 失败: {str(e)}")
                    # 出错则不使用定时器，直接执行
            else:
                Logger.log("w", "无法获取 MachineManager")
            
            # 没有 MachineManager 或出错时，直接继续执行（不使用定时器）
            self._continueUploadAfterBlur(config_name, remarks)
            
        except Exception as e:
            Logger.logException("e", f"上传配置失败: {str(e)}")
            self.uploadFailed.emit(str(e))
    
    def _continueUploadAfterBlur(self, config_name: str, remarks: str):
        """
        在 UI 失去焦点后继续上传流程
        
        说明：
        - 上传时只上传已保存的配置（qualityChanges）
        - 不会自动合并UI上未保存的修改
        - 如果用户想上传最新修改，应该先点"保存"，然后再点"上传"
        """
        try:
            # 步骤1：保存所有容器到磁盘（确保已保存的配置被持久化）
            self._log_debug("=" * 60)
            self._log_debug(" 步骤1：保存已保存的配置到磁盘")
            self._log_debug("=" * 60)
            self._forceSaveAndReloadContainers()
            
            # 步骤0.6：合并 userChanges 到 qualityChanges（确保用户修改被保存）
            self._log_debug("=" * 60)
            self._log_debug("步骤0.6：合并 userChanges 到 qualityChanges")
            self._log_debug("=" * 60)
            self._mergeUserChangesToQualityChanges()
            
            # 步骤1：强制保存：在导出前确保所有UI当前值被保存
            self._log_debug("=" * 60)
            self._log_debug("🔄 步骤1：强制保存当前UI显示的参数到 qualityChanges")
            self._log_debug("=" * 60)
            self._forceSaveCurrentSettings()
            
            self._log_debug("=" * 60)
            self._log_debug(" 步骤2：读取并导出所有配置")
            self._log_debug("=" * 60)
            
            # 获取当前的切片参数
            config_data = self._collectSliceSettings()
            
            if not config_data:
                Logger.log("e", "Failed to collect slice settings")
                self.uploadFailed.emit("无法获取切片参数")
                return
            
            # 添加配置名称和备注
            config_data["name"] = config_name
            config_data["remarks"] = remarks
            
            # 获取 all_settings_string
            all_settings = config_data.get('all_settings_string', '')
            
            if not all_settings:
                Logger.log("e", "all_settings_string 为空")
                self.uploadFailed.emit("配置字符串为空")
                return
            
            # 保存到临时txt文件
            try:
                config_file_path = self._saveConfigToFile(all_settings, config_name, remarks)
                Logger.log("i", f"配置已保存到: {config_file_path}")
            except Exception as e:
                Logger.logException("e", f"保存配置文件失败: {str(e)}")
                self.uploadFailed.emit(f"保存配置文件失败: {str(e)}")
                return
            
            # 获取OBS上传令牌并上传
            def on_token_received(header_data):
                if not header_data or not header_data.get('obs_url'):
                    Logger.log("e", "获取上传令牌失败")
                    self.uploadFailed.emit("获取上传令牌失败")
                    return
                
                # 上传txt文件到OBS
                Logger.log("i", f"开始上传配置文件: {config_file_path}")
                self._uploader.upload_gcode(config_file_path, header_data)
            
            # 请求OBS上传令牌
            self._getUploadToken(on_token_received)
            
        except Exception as e:
            Logger.logException("e", f"上传配置失败: {str(e)}")
            self.uploadFailed.emit(str(e))
    
    def _collectSliceSettings(self) -> Optional[Dict[str, Any]]:
        """
        收集当前的切片设置参数
        
        :return: 包含所有切片参数的字典
        """
        try:
            machine_manager = self._application.getMachineManager()
            global_stack = machine_manager.activeMachine
            
            if not global_stack:
                Logger.log("w", "No active machine found")
                return None
            
            # 调试：显示当前激活的质量配置
            if self._debug_mode:
                Logger.log("d", "=" * 60)
                Logger.log("d", "当前激活的配置信息：")
                Logger.log("d", "=" * 60)
                Logger.log("d", f"  Machine: {global_stack.getName()} ({global_stack.getId()})")
                Logger.log("d", f"  Definition: {global_stack.definition.getId()}")
                
                # 显示质量配置
                quality = global_stack.quality
                if quality:
                    Logger.log("d", f"  Quality (base): {quality.getName()} ({quality.getId()})")
                    Logger.log("d", f"    - quality_type: {quality.getMetaDataEntry('quality_type')}")
                else:
                    Logger.log("d", "  Quality (base): None")
                
                # 显示自定义质量配置
                quality_changes = global_stack.qualityChanges
                if quality_changes and quality_changes.getId() != "empty_quality_changes":
                    Logger.log("d", f"  QualityChanges (custom): {quality_changes.getName()} ({quality_changes.getId()})")
                    Logger.log("d", f"    - 包含的设置数量: {len(list(quality_changes.getAllKeys()))}")
                    # 显示关键设置的值
                    for key in self.KEY_MONITORING_PARAMS:
                        qc_value = quality_changes.getProperty(key, "value")
                        if qc_value is not None:
                            Logger.log("d", f"    - {key}: {qc_value}")
                else:
                    Logger.log("d", "  QualityChanges (custom): None (使用默认质量配置)")
                
                # 显示 userChanges
                user_changes = global_stack.userChanges
                if user_changes:
                    user_keys = list(user_changes.getAllKeys())
                    Logger.log("d", f"  UserChanges: {len(user_keys)} 个设置")
                    if user_keys:
                        Logger.log("d", f"    - 包含的设置: {', '.join(user_keys[:10])}{' ...' if len(user_keys) > 10 else ''}")
                    # 显示关键设置的值
                    for key in self.KEY_MONITORING_PARAMS:
                        user_value = user_changes.getProperty(key, "value")
                        if user_value is not None:
                            Logger.log("d", f"    - {key}: {user_value}")
                else:
                    Logger.log("d", "  UserChanges: None")
                
                Logger.log("d", "=" * 60)
            
            # 收集机器信息
            config_data = {
                "machine": {
                    "id": global_stack.getId(),
                    "name": global_stack.getName(),
                    "definition": global_stack.definition.getId()
                },
                "settings": {}
            }
            
            # 获取所有可见的设置
            setting_definitions = global_stack.definition.findDefinitions()
            
            for setting_definition in setting_definitions:
                setting_key = setting_definition.key
                
                # 获取设置值（考虑继承链）
                setting_value = global_stack.getProperty(setting_key, "value")
                
                # 收集所有设置（包括默认值）- 与 CuraEngine 的 getAllSettingsString() 一致
                    config_data["settings"][setting_key] = {
                        "value": setting_value,
                        "label": setting_definition.label,
                        "type": setting_definition.type,
                        "unit": setting_definition.unit if hasattr(setting_definition, 'unit') else None
                    }
            
            # 收集材料信息
            extruders = global_stack.extruderList
            config_data["extruders"] = []
            
            for extruder in extruders:
                extruder_data = {
                    "position": extruder.getMetaDataEntry("position"),
                    "material": extruder.material.getName() if extruder.material else None,
                    "settings": {}
                }
                
                # 收集挤出头特定的设置（所有设置，包括默认值）
                for setting_definition in extruder.definition.findDefinitions():
                    setting_key = setting_definition.key
                    setting_value = extruder.getProperty(setting_key, "value")
                    
                        extruder_data["settings"][setting_key] = {
                            "value": setting_value,
                            "label": setting_definition.label
                        }
                
                config_data["extruders"].append(extruder_data)
            
            # 收集质量配置信息
            quality_container = global_stack.quality
            if quality_container:
                config_data["quality"] = {
                    "id": quality_container.getId(),
                    "name": quality_container.getName(),
                    "type": quality_container.getMetaDataEntry("quality_type")
                }
            
            # 收集意图信息
            intent_container = global_stack.intent
            if intent_container:
                config_data["intent"] = {
                    "id": intent_container.getId(),
                    "name": intent_container.getName()
                }
            
            # 添加 CuraEngine 命令行格式的字符串（与 scene.getAllSettingsString() 一致）
            config_data["all_settings_string"] = self._generateAllSettingsString(global_stack)
            
            return config_data
            
        except Exception as e:
            Logger.logException("e", f"收集切片设置失败: {str(e)}")
            return None
    
    def _generateAllSettingsString(self, global_stack) -> str:
        """
        生成 CuraEngine 格式的所有设置字符串
        
        """
        try:
            output = []
            
            # 1. 全局设置（Global settings）
            setting_definitions = global_stack.definition.findDefinitions()
            for setting_definition in setting_definitions:
                setting_key = setting_definition.key
                
                # 获取最终解析值
                setting_value = global_stack.getProperty(setting_key, "value")
                
                # 调试关键参数 - 显示所有可能的值来源
                if self._debug_mode and setting_key in self.KEY_MONITORING_PARAMS:
                    user_value = global_stack.userChanges.getProperty(setting_key, "value")
                    quality_changes_value = global_stack.qualityChanges.getProperty(setting_key, "value")
                    quality_value = global_stack.quality.getProperty(setting_key, "value")
                    
                    Logger.log("d", f" 导出设置: {setting_key} = {setting_value}")
                    Logger.log("d", f"   - userChanges: {user_value}")
                    Logger.log("d", f"   - qualityChanges: {quality_changes_value}")
                    Logger.log("d", f"   - quality: {quality_value}")
                    Logger.log("d", f"   - final (实际导出): {setting_value}")
                    
                    # 显示定义信息
                    setting_def = global_stack.getSettingDefinition(setting_key)
                    if setting_def:
                        default_formula = setting_def.default_value
                        if isinstance(default_formula, str) and len(str(default_formula)) > 0:
                            formula_preview = str(default_formula)[:80]
                            Logger.log("d", f"   - 定义公式: {formula_preview}{'...' if len(str(default_formula)) > 80 else ''}")
                
                # 转换为字符串并转义引号
                value_str = str(setting_value).replace('"', '\\"')
                output.append(f'-s {setting_key}="{value_str}"')
            
            # 2. 每个挤出头的设置（Per-extruder settings）
            extruders = global_stack.extruderList
            for extruder_nr, extruder in enumerate(extruders):
                output.append(f'-e{extruder_nr}')
                for setting_definition in extruder.definition.findDefinitions():
                    setting_key = setting_definition.key
                    setting_value = extruder.getProperty(setting_key, "value")
                    value_str = str(setting_value).replace('"', '\\"')
                    output.append(f'-s {setting_key}="{value_str}"')
            
            # 3. Mesh group 设置（Per-mesh-group settings）
            # CuraEngine 的格式：-g mesh_group_settings -e0 -l "mesh_index" mesh_settings
            output.append('-g')  # 第一个 mesh group
            
            # 获取场景中的所有模型
            scene = self._application.getController().getScene()
            scene_root = scene.getRoot()
            
            # 遍历所有mesh节点
            mesh_index = 0
            for node in scene_root.getAllChildren():
                # 只处理实际的mesh节点（有MeshData的）
                if node.getMeshData() and node.isEnabled():
                    # 获取mesh使用的挤出头
                    extruder_nr = 0
                    if node.callDecoration("getActiveExtruderPosition"):
                        extruder_nr = int(node.callDecoration("getActiveExtruderPosition"))
                    
                    # 输出mesh级别的设置
                    output.append(f'-e{extruder_nr}')
                    output.append(f'-l "{mesh_index}"')
                    
                    # Mesh级别的设置（per-object settings）
                    # 注意：这里可能需要获取mesh特定的设置覆盖
                    mesh_stack = node.callDecoration("getStack")
                    if mesh_stack and mesh_stack.definition and hasattr(mesh_stack.definition, 'findDefinitions'):
                        for setting_definition in mesh_stack.definition.findDefinitions():
                            setting_key = setting_definition.key
                            setting_value = mesh_stack.getProperty(setting_key, "value")
                            value_str = str(setting_value).replace('"', '\\"')
                            output.append(f'-s {setting_key}="{value_str}"')
                    else:
                        # 如果没有mesh特定的设置，至少输出extruder_nr
                        output.append(f'-s extruder_nr="{extruder_nr}"')
                    
                    mesh_index += 1
            
            return ' '.join(output)
            
        except Exception as e:
            Logger.logException("e", f"生成设置字符串失败: {str(e)}")
            return ""
    
    def _forceSaveAndReloadContainers(self):
        """
        强制保存所有容器到磁盘并重新加载
        这确保我们读取到的是最新的值
        """
        try:
            from UM.Settings.ContainerRegistry import ContainerRegistry
            registry = ContainerRegistry.getInstance()
            
            self._log_debug("开始保存所有脏容器...")
            # 保存所有修改过的容器（这是同步操作，完成后即可继续）
            registry.saveDirtyContainers()
            self._log_debug(" 所有容器已保存")
            
            # 重新加载当前质量配置
            if self._debug_mode:
                machine_manager = self._application.getMachineManager()
                global_stack = machine_manager.activeMachine
                if global_stack:
                    quality_changes = global_stack.qualityChanges
                    if quality_changes and quality_changes.getId() != "empty_quality_changes":
                        Logger.log("d", f"读取最新的质量配置: {quality_changes.getId()}")
                        
                        # 打印关键参数的最新值
                        Logger.log("d", " 保存后的关键参数值：")
                        Logger.log("d", "  [全局配置]")
                        self._log_key_params(global_stack, quality_changes, "    ")
                        
                        # 检查挤出头配置
                        Logger.log("d", "  [挤出头配置]")
                        for extruder in global_stack.extruderList:
                            extruder_qc = extruder.qualityChanges
                            if extruder_qc and extruder_qc.getId() != "empty_quality_changes":
                                Logger.log("d", f"    Extruder {extruder.getMetaDataEntry('position')}: {extruder_qc.getId()}")
                                for key in ["infill_sparse_density", "infill_pattern"]:
                                    try:
                                        ext_qc_value = extruder_qc.getProperty(key, "value")
                                        ext_stack_value = extruder.getProperty(key, "value")
                                        if ext_qc_value is not None:
                                            Logger.log("d", f"      {key}: qc={ext_qc_value}, stack={ext_stack_value}")
                                    except Exception as e:
                                        Logger.log("w", f"      无法读取 {key}: {str(e)}")
                            
        except Exception as e:
            Logger.logException("e", f"保存和重新加载容器失败: {str(e)}")
    
    def _mergeUserChangesToQualityChanges(self):
        """
        将 userChanges 中的所有修改合并到 qualityChanges 中
        这确保了用户的所有修改都被保存到自定义质量配置中
        """
        try:
            machine_manager = self._application.getMachineManager()
            global_stack = machine_manager.activeMachine
            if not global_stack:
                Logger.log("w", "无法获取 activeMachine")
                return
            
            user_changes = global_stack.userChanges
            if not user_changes:
                self._log_debug("userChanges 为空，无需合并")
                return
            
            user_keys = list(user_changes.getAllKeys())
            if not user_keys:
                self._log_debug("userChanges 中没有设置，无需合并")
                return
            
            self._log_debug(f"发现 {len(user_keys)} 个用户修改，开始合并到 qualityChanges")
            
            # 获取或创建 qualityChanges 容器
            global_quality_changes = global_stack.qualityChanges
            if not global_quality_changes or global_quality_changes.getId() == "empty_quality_changes":
                Logger.log("w", "当前没有激活的自定义质量配置")
                Logger.log("w", "用户的修改在 userChanges 中，但没有自定义配置来保存它们！")
                Logger.log("w", "这些修改将直接从 userChanges 中导出")
                return
            
            # 合并所有用户修改到 qualityChanges
            merged_count = 0
            for key in user_keys:
                try:
                    user_value = user_changes.getProperty(key, "value")
                    if user_value is not None:
                        # 保存到 qualityChanges
                        global_quality_changes.setProperty(key, "value", user_value)
                        merged_count += 1
                        
                        # 记录关键参数
                        if self._debug_mode and key in self.KEY_MONITORING_PARAMS:
                            Logger.log("d", f" 合并: {key} = {user_value}")
                except Exception as e:
                    Logger.log("w", f"无法合并 {key}: {str(e)}")
            
            if merged_count > 0:
                Logger.log("i", f" 成功合并 {merged_count} 个设置从 userChanges 到 qualityChanges")
                
                # 触发信号刷新
                global_quality_changes.sendPostponedEmits()
                
                # 验证合并结果（仅在调试模式）
                if self._debug_mode:
                    Logger.log("d", " 验证合并结果（关键参数）：")
                    self._log_key_params(global_stack, global_quality_changes, "  ")
                
                # 不清空 userChanges，让它保持现状
                # 因为清空可能会导致 UI 更新问题
            else:
                self._log_debug("没有设置需要合并")
                
        except Exception as e:
            Logger.logException("e", f"合并 userChanges 失败: {str(e)}")
    
    def _forceSaveCurrentSettings(self):
        """
        强制保存当前UI显示的所有参数到 qualityChanges
        
        这个方法在导出配置前调用，确保UI中显示的所有值都被保存。
        特别是那些有公式（fx）计算的参数，它们的当前值可能还没有保存到容器中。
        """
        try:
            # 准备保存操作
            result = self._prepareForSave()
            if not result:
                return
            
            global_stack, global_quality_changes = result
            self._log_debug(f"开始强制保存到 qualityChanges: {global_quality_changes.getId()}")
            
            # 检查当前状态（仅在调试模式）
            if self._debug_mode:
                self._logCurrentStateBeforeSave(global_stack, global_quality_changes)
            
            # 保存关键参数
            saved_count, skipped_count = self._saveCriticalSettings(global_stack, global_quality_changes)
            
            # 检查挤出头配置，合并非 per_extruder 设置到全局配置
            extra_count = self._mergeExtruderSettingsToGlobal(global_stack, global_quality_changes)
            saved_count += extra_count
            
            # 触发信号刷新
            if saved_count > 0:
                global_quality_changes.sendPostponedEmits()
                Logger.log("i", f" 强制保存完成，共更新 {saved_count} 个参数（跳过 {skipped_count} 个只读属性）")
            else:
                self._log_debug("所有参数已是最新，无需保存")
            
            # 验证保存结果（仅在调试模式）
            if self._debug_mode:
                self._verifySaveResults(global_stack, global_quality_changes)
            
        except Exception as e:
            Logger.logException("e", f"强制保存失败: {str(e)}")
    
    def _checkIsExplorer3(self) -> bool:
        """
        内部方法：检查当前机器是否是 Explorer 3
        
        :return: 如果是 Explorer 3 则返回 True
        """
        try:
            machine_manager = self._application.getMachineManager()
            if not machine_manager:
                return False
                
            global_stack = machine_manager.activeMachine
            if not global_stack:
                return False
            
            # 检查机器定义 ID (来自文件名 explorer_3.def.json)
            definition = global_stack.definition
            definition_id = definition.getId() if definition else ""
            
            # 简单匹配：definition_id 等于 "explorer_3"
            return definition_id == "explorer_3"
            
        except Exception as e:
            Logger.logException("e", f"ConfigUploadHandler: 检查机器类型失败: {str(e)}")
            return False
    
    @pyqtProperty(bool, notify=isExplorer3MachineChanged)
    def isExplorer3Machine(self) -> bool:
        """
        QML 属性：检查当前机器是否是 Explorer 3
        
        :return: 如果是 Explorer 3 则返回 True
        """
        return self._is_explorer3_machine
    
    @pyqtSlot()
    def fetchCloudConfigs(self):
        """获取云端配置列表"""
        try:
            url = QUrl(DEVICE_SLICE_TYPE_URL)
            request = QNetworkRequest(url)
            
            # 设置 Header
            auth_token = self._application.get_auth_token()
            if auth_token:
                request.setRawHeader(b"Authorization", auth_token.encode('utf-8'))
            request.setRawHeader(b"Biz", b"ZXBMan")
            
            Logger.log("d", f"请求云端配置列表: {url.toString()}")
            
            self.reply_fetch_configs = self.network_manager.get(request)
            self.reply_fetch_configs.finished.connect(self._onFetchConfigsResponse)
            
        except Exception as e:
            Logger.logException("e", f"获取云端配置列表失败: {str(e)}")
            self.cloudConfigsFetchFailed.emit(str(e))
    
    def _onFetchConfigsResponse(self):
        """处理获取配置列表的响应"""
        if not self.reply_fetch_configs:
            return
        
        try:
            if self.reply_fetch_configs.error() == QNetworkReply.NetworkError.NoError:
                data = self.reply_fetch_configs.readAll()
                response_data = json.loads(data.data().decode('utf-8'))
                Logger.log("d", f"配置列表响应: {response_data}")
                
                if response_data.get("msg") == "success" or response_data.get("code") == 0:
                    # 解析配置列表
                    configs = []
                    data_list = response_data.get("data", [])
                    
                    for device_item in data_list:
                        device_type = device_item.get("deviceType", "")
                        if device_type != "EP3":
                            continue
                        
                        slice_types = device_item.get("sliceTypes", [])
                        for slice_type_item in slice_types:
                            slice_type = slice_type_item.get("sliceType", "")
                            if slice_type != "cura":
                                continue
                            
                            slice_confs = slice_type_item.get("sliceConfs", [])
                            for conf in slice_confs:
                                configs.append({
                                    "id": conf.get("id", ""),
                                    "name": conf.get("name", ""),
                                    "configFileUrl": conf.get("configFileUrl", ""),
                                    "configFileName": conf.get("configFileName", ""),
                                    "info": conf.get("info", ""),
                                    "systemConfig": conf.get("systemConfig", 0)
                                })
                    
                    Logger.log("i", f"获取到 {len(configs)} 个配置")
                    self.cloudConfigsFetched.emit(configs)
                else:
                    error_msg = response_data.get("msg", "获取配置列表失败")
                    Logger.log("e", f"获取配置列表失败: {error_msg}")
                    self.cloudConfigsFetchFailed.emit(error_msg)
            else:
                err_str = self.reply_fetch_configs.errorString()
                Logger.log("e", f"获取配置列表网络错误: {err_str}")
                self.cloudConfigsFetchFailed.emit(err_str)
        except Exception as e:
            Logger.logException("e", f"处理配置列表响应时出错: {str(e)}")
            self.cloudConfigsFetchFailed.emit(str(e))
        finally:
            self.reply_fetch_configs.deleteLater()
            self.reply_fetch_configs = None
    
    @pyqtSlot(str, str)
    def importCloudConfig(self, config_url: str, config_name: str):
        """
        导入云端配置
        
        :param config_url: 配置文件URL
        :param config_name: 配置名称
        """
        Logger.log("i", f"开始导入云端配置: {config_name} - {config_url}")
        
        if not config_url:
            Logger.log("e", "配置文件URL为空，无法导入")
            return
        
        # 保存当前配置信息，用于下载完成后处理
        self._current_import_config_name = config_name
        
        # 发起下载请求
        url = QUrl(config_url)
        request = QNetworkRequest(url)
        
        # 添加认证头
        auth_token = Application.getInstance().get_auth_token()
        if auth_token:
            request.setRawHeader(b"Authorization", auth_token.encode('utf-8'))
        request.setRawHeader(b"Biz", "ZXBMan".encode("utf-8"))
        
        self.reply_download_config = self.network_manager.get(request)
        self.reply_download_config.finished.connect(self._onConfigDownloaded)
        
        Logger.log("d", f"正在下载配置文件: {config_url}")
    
    def _onConfigDownloaded(self):
        """配置文件下载完成的回调"""
        if not self.reply_download_config:
            return
        
        try:
            if self.reply_download_config.error() == QNetworkReply.NetworkError.NoError:
                # 读取配置文件内容
                config_content = bytes(self.reply_download_config.readAll()).decode('utf-8')
                Logger.log("d", f"配置文件下载成功，内容长度: {len(config_content)}")
                
                #  显示"正在导入配置..."加载提示
                self._showImportingMessage()
                
                #  强制刷新UI，确保加载提示立即显示
                Application.getInstance().processEvents()
                
                # 延迟 300ms 执行，给足够时间让用户看到加载提示
                # 虽然导入操作本身需要 500ms，但至少用户能看到"正在处理"的反馈
                QTimer.singleShot(300, lambda: self._applyConfigSettings(config_content, self._current_import_config_name))
            else:
                error_string = self.reply_download_config.errorString()
                Logger.log("e", f"配置文件下载失败: {error_string}")
                self._showMessage("配置导入失败", f"下载配置文件失败: {error_string}")
        
        except Exception as e:
            Logger.log("e", f"处理下载的配置文件时出错: {str(e)}")
            import traceback
            Logger.log("e", traceback.format_exc())
            self._showMessage("配置导入失败", f"处理配置文件时出错: {str(e)}")
        
        finally:
            self.reply_download_config.deleteLater()
            self.reply_download_config = None
    
    def _applyConfigSettings(self, config_content: str, config_name: str):
        """
        解析配置并通过 Cura 标准 API 导入
        
        :param config_content: 配置文件内容（-s setting=value 格式）
        :param config_name: 配置名称
        """
        try:
            Logger.log("d", f"开始处理配置: {config_name}")
            
            # 解析配置内容
            settings = self._parseConfigContent(config_content)
            
            if not settings:
                Logger.log("e", "未能从配置文件中解析出任何设置")
                self._showMessage("配置导入失败", "配置文件格式无效或为空")
                return
            
            Logger.log("d", f"解析出 {len(settings)} 个设置项")
            
            # 获取当前机器
            machine_manager = Application.getInstance().getMachineManager()
            global_stack = machine_manager.activeMachine
            
            if not global_stack:
                Logger.log("e", "没有活动的打印机")
                self._showMessage("配置导入失败", "请先选择一台打印机")
                return
            
            # 过滤出当前打印机支持的设置，并排除机器定义参数
            definition = global_stack.definition
            valid_settings = {}
            
            for setting_key, setting_value in settings.items():
                # 跳过机器参数（这些应该由机器定义提供）
                if setting_key.startswith("machine_"):
                    continue
                
                # 获取设置定义
                setting_definition = definition.findDefinitions(key=setting_key)
                if setting_definition:
                    setting_def = setting_definition[0]
                    
                    # 不要过滤有公式的设置！
                    # 很多设置虽然有默认计算公式，但用户可以覆盖
                    # 例如：wall_thickness, wall_line_count, speed_print 等
                    # 只有当设置完全不可编辑时才跳过（但这种情况很少）
                    
                    valid_settings[setting_key] = setting_value
            
            Logger.log("i", f"过滤后有 {len(valid_settings)}/{len(settings)} 个有效设置（已排除机器参数和数组值）")
            
            if not valid_settings:
                Logger.log("e", "没有找到任何兼容的设置")
                self._showMessage("配置导入失败", "该配置与当前打印机不兼容")
                return
            
            # 让UI有机会更新（显示进度条动画）
            Application.getInstance().processEvents()
            
            # 创建临时配置文件并导入
            self._importViaProfileFile(valid_settings, config_name, global_stack)
            
        except Exception as e:
            Logger.logException("e", f"配置导入失败: {str(e)}")
            self._showMessage("配置导入失败", f"应用配置时出错: {str(e)}")
        finally:
            # 无论成功还是失败，都隐藏加载提示
            self._hideImportingMessage()
    
    def _parseConfigContent(self, content: str) -> dict:
        """
        解析配置文件内容（-s setting=value 格式）
        
        :param content: 配置文件内容
        :return: 设置字典 {setting_key: value}
        """
        import re
        
        settings = {}
        
        # 匹配 -s setting="value" 或 -s setting=value 格式
        pattern = r'-s\s+(\w+)=(?:"([^"]*)"|([^\s]+))'
        matches = re.findall(pattern, content)
        
        for match in matches:
            setting_key = match[0]
            # match[1] 是引号内的值，match[2] 是不带引号的值
            setting_value_str = match[1] if match[1] else match[2]
            
            # 尝试转换为合适的类型
            setting_value = self._convertSettingValue(setting_value_str)
            settings[setting_key] = setting_value
        
        return settings
    
    def _convertSettingValue(self, value_str: str):
        """
        将字符串值转换为合适的类型
        
        :param value_str: 字符串值
        :return: 转换后的值
        """
        # 处理空字符串
        if not value_str or value_str == "":
            return ""
        
        # 尝试转换为布尔值（严格匹配，避免 "False" 被当作其他类型）
        if value_str.lower() == "true":
            return True
        elif value_str.lower() == "false":
            return False
        
        # 尝试转换为整数
        try:
            # 先尝试直接转换
            return int(value_str)
        except ValueError:
            pass
        
        # 尝试转换为浮点数
        try:
            return float(value_str)
        except ValueError:
            pass
        
        # 保持为字符串
        return value_str
    
    def _createQualityChanges(self, name: str, global_stack, extruder_stack=None):
        """
        创建一个新的 qualityChanges 容器

        """
        from UM.Settings.ContainerRegistry import ContainerRegistry
        from UM.Settings.InstanceContainer import InstanceContainer
        from cura.Machines.ContainerTree import ContainerTree
        
        container_registry = ContainerRegistry.getInstance()
        base_id = global_stack.definition.getId() if extruder_stack is None else extruder_stack.getId()
        new_id = base_id + "_" + name
        new_id = new_id.lower().replace(" ", "_")
        new_id = container_registry.uniqueName(new_id)
        
        # 创建新的 quality_changes 容器
        quality_changes = InstanceContainer(new_id)
        quality_changes.setName(name)
        quality_changes.setMetaDataEntry("type", "quality_changes")
        
        # 设置 quality_type
        quality_type = global_stack.quality.getMetaDataEntry("quality_type", "normal")
        quality_changes.setMetaDataEntry("quality_type", quality_type)
        
        # 设置 intent_category（如果有）
        intent_category = global_stack.intent.getMetaDataEntry("intent_category")
        if intent_category:
            quality_changes.setMetaDataEntry("intent_category", intent_category)
        
        # 如果是为挤出头创建，添加 position
        if extruder_stack is not None:
            position = extruder_stack.getMetaDataEntry("position")
            if position is not None:
                quality_changes.setMetaDataEntry("position", position)
        
        # 设置 definition
        machine_definition_id = ContainerTree.getInstance().machines[global_stack.definition.getId()].quality_definition
        quality_changes.setDefinition(machine_definition_id)
        
        # 设置版本
        quality_changes.setMetaDataEntry("setting_version", self._application.SettingVersion)
        
        # 添加到注册表
        container_registry.addContainer(quality_changes)
        
        Logger.log("d", f"创建 qualityChanges 容器: {new_id} (extruder: {extruder_stack is not None})")
        
        return quality_changes
    
    def _importViaProfileFile(self, settings: Dict[str, Any], config_name: str, global_stack):
        """
        通过创建临时配置文件并使用 Cura 标准 API 导入
        这是最安全的方式，避免直接操作容器导致的信号问题
        
        :param settings: 设置字典
        :param config_name: 配置名称
        :param global_stack: 全局容器栈
        """
        import configparser
        from UM.Settings.ContainerRegistry import ContainerRegistry
        
        Logger.log("i", f"开始通过标准 API 导入配置 '{config_name}'")
        
        # 1. 创建 INI 格式的配置内容
        config = configparser.ConfigParser()
        config.optionxform = str  # 保持键的大小写
        
        # 设置元数据
        config["general"] = {
            "version": "4",
            "name": config_name,
            "definition": global_stack.definition.getId()
        }
        
        config["metadata"] = {
            "type": "quality_changes",
            "quality_type": "normal",
            "setting_version": "20"
        }
        
        # 设置值 - 根据定义来正确序列化
        config["values"] = {}
        definition = global_stack.definition
        
        for key, value in settings.items():
            # 跳过数组类型的值（如 "[100]"）
            value_str = str(value)
            if value_str.startswith("[") and value_str.endswith("]"):
                Logger.log("d", f"跳过数组类型设置: {key}={value}")
                continue
            
            # 获取设置定义以确定正确的类型
            setting_defs = definition.findDefinitions(key=key)
            if not setting_defs:
                continue
            
            setting_def = setting_defs[0]
            setting_type = setting_def.type
            
            # 根据类型正确序列化
            if setting_type == "bool":
                # 布尔值：转换为 "True" 或 "False"
                if isinstance(value, bool):
                    config["values"][key] = "True" if value else "False"
                elif isinstance(value, str):
                    config["values"][key] = "True" if value.lower() in ("true", "1", "yes") else "False"
                else:
                    config["values"][key] = "True" if value else "False"
                    
            elif setting_type in ("int", "optional_extruder"):
                # 整数类型：确保转换为整数
                try:
                    if isinstance(value, str) and value.lower() in ("false", "true"):
                        # 如果是布尔字符串，转换为 0 或 1
                        config["values"][key] = "1" if value.lower() == "true" else "0"
                    else:
                        config["values"][key] = str(int(float(value)))
                except (ValueError, TypeError):
                    Logger.log("w", f"无法将 {key}={value} 转换为整数，跳过")
                    continue
                    
            elif setting_type == "float":
                # 浮点数类型
                try:
                    config["values"][key] = str(float(value))
                except (ValueError, TypeError):
                    Logger.log("w", f"无法将 {key}={value} 转换为浮点数，跳过")
                    continue
                    
            elif setting_type in ("str", "enum", "category"):
                # 字符串类型：直接存储
                config["values"][key] = str(value)
            else:
                # 未知类型：尝试智能转换
                config["values"][key] = str(value)
        
        # 2. 写入临时文件
        temp_dir = tempfile.gettempdir()
        temp_filename = f"cura_import_{uuid.uuid4()}.inst.cfg"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                config.write(f)
            
            Logger.log("d", f"临时配置文件已创建: {temp_path}")
            
            # 3. 使用 Cura 的 InstanceContainer 来加载配置
            from UM.Settings.InstanceContainer import InstanceContainer
            
            # 创建新的配置容器
            profile_id = ContainerRegistry.getInstance().uniqueName(config_name)
            profile = InstanceContainer(profile_id)
            profile.setMetaDataEntry("type", "quality_changes")
            profile.setMetaDataEntry("quality_type", "normal")
            profile.setMetaDataEntry("definition", global_stack.definition.getId())
            profile.setName(config_name)
            
            # 反序列化配置
            with open(temp_path, 'r', encoding='utf-8') as f:
                serialized = f.read()
            profile.deserialize(serialized, temp_filename)
            
            # 4. 直接将配置值应用到 qualityChanges，保持自定义配置名称
            machine_manager = Application.getInstance().getMachineManager()
            
            # 先清空 userChanges，避免冲突
            user_changes = global_stack.userChanges
            user_keys = list(user_changes.getAllKeys())
            if user_keys:
                Logger.log("w", f"导入将覆盖 {len(user_keys)} 个未保存的用户修改")
                self._log_debug(f"  被覆盖的设置: {', '.join(user_keys[:10])}{' ...' if len(user_keys) > 10 else ''}")
            
            self._log_debug("清空 userChanges 中的所有设置")
            for key in user_keys:
                user_changes.removeInstance(key, postpone_emit=True)
            
            # 获取或创建 qualityChanges 容器
            global_quality_changes = global_stack.qualityChanges
            if not global_quality_changes or global_quality_changes.getId() == "empty_quality_changes":
                # 创建新的自定义质量配置
                Logger.log("d", f"创建新的自定义质量配置: {config_name}")
                global_quality_changes = self._createQualityChanges(config_name, global_stack, None)
                
                # 设置到 global_stack
                global_stack.setQualityChanges(global_quality_changes)
                
                # 为每个挤出头创建 qualityChanges
                for extruder in global_stack.extruderList:
                    extruder_qc = self._createQualityChanges(config_name, global_stack, extruder)
                    extruder.setQualityChanges(extruder_qc)
                
                Logger.log("d", f"创建完成: {global_quality_changes.getId()}")
            else:
                Logger.log("d", f"使用现有 qualityChanges: {global_quality_changes.getId()}")
            
            # 使用批处理异步导入，避免阻塞主线程
            all_keys = list(profile.getAllKeys())
            self._import_state = {
                'profile': profile,
                'all_keys': all_keys,
                'global_stack': global_stack,
                'global_quality_changes': global_quality_changes,
                'user_changes': user_changes,
                'machine_manager': machine_manager,
                'config_name': config_name,
                'settings': settings,
                'current_index': 0,
                'applied_count': 0,
                'temp_path': temp_path
            }
            
            Logger.log("i", f"开始批处理导入 {len(all_keys)} 个设置...")
            # 开始第一批处理
            self._processBatchImport()
            # 批处理导入会在完成后调用 _finishBatchImport
            return
            
        except Exception as e:
            Logger.logException("e", f"导入配置时出错: {str(e)}")
            self._hideImportingMessage()
            raise
    
    def _finalRefresh(self, global_stack, config_name: str, applied_count: int, total_count: int):
        """
        延迟刷新：在导入完成100ms后再次刷新UI
        
        :param global_stack: 全局堆栈
        :param config_name: 配置名称
        :param applied_count: 已应用设置数量
        :param total_count: 总设置数量
        """
        try:
            machine_manager = Application.getInstance().getMachineManager()
            
            # 再次触发信号
            machine_manager.activeStackValueChanged.emit()
            self._log_debug("===延迟刷新：再次触发 activeStackValueChanged===")
            
            # 最终验证（仅在调试模式）
            if self._debug_mode:
                Logger.log("d", "=== 延迟验证（100ms后）===")
                global_quality_changes = global_stack.qualityChanges
                self._log_key_params(global_stack, global_quality_changes, "  ")
            
            # 显示最终消息
            quality_name = global_quality_changes.getName() if global_quality_changes else "未知"
            self._showMessage(
                "配置导入成功",
                f"配置 '{config_name}' 已成功导入到 '{quality_name}'\n"
                f"成功应用了 {applied_count} 个设置\n\n"
                f" 设置已保存到当前质量配置"
            )
            
        except Exception as e:
            Logger.logException("e", f"延迟刷新时出错: {str(e)}")
    
    def _showMessage(self, title: str, message: str):
        """显示消息给用户"""
        Message(text=message, title=title).show()
    
    def _showImportingMessage(self):
        """显示"正在导入配置..."加载提示"""
        # 先隐藏之前的提示（如果有）
        self._hideImportingMessage()
        
        # 创建并显示新的加载提示（不显示进度条）
        self._importing_message = Message(
            text="正在解析和应用 600+ 个设置，请稍候...",
            title=" 正在导入配置",
            lifetime=0,  # 不自动关闭
            dismissable=False  # 不可手动关闭
        )
        # 不设置进度条，避免UI卡顿
        # self._importing_message.setProgress(-1)
        self._importing_message.show()
        Logger.log("d", " 显示导入加载提示")
    
    def _hideImportingMessage(self):
        """隐藏"正在导入配置..."加载提示"""
        if self._importing_message:
            try:
                self._importing_message.hide()
                Logger.log("d", " 隐藏导入加载提示")
            except:
                pass
            finally:
                self._importing_message = None
    
    def _processBatchImport(self):
        """批处理导入：每次处理30个设置，然后返回事件循环"""
        if not self._import_state:
            return
        
        BATCH_SIZE = 30  # 每批处理30个设置
        state = self._import_state
        profile = state['profile']
        all_keys = state['all_keys']
        global_quality_changes = state['global_quality_changes']
        current_index = state['current_index']
        
        # 处理本批次
        end_index = min(current_index + BATCH_SIZE, len(all_keys))
        for i in range(current_index, end_index):
            key = all_keys[i]
            try:
                value = profile.getProperty(key, "value")
                if value is not None:
                    global_quality_changes.setProperty(key, "value", value)
                    state['applied_count'] += 1
                    
                    # 记录关键参数
                    if self._debug_mode and key in self.KEY_MONITORING_PARAMS:
                        Logger.log("d", f" 应用关键设置: {key} = {value}")
            except Exception as e:
                Logger.log("w", f"设置 {key} 失败: {str(e)}")
        
        # 更新进度
        state['current_index'] = end_index
        progress = int((end_index / len(all_keys)) * 100)
        Logger.log("d", f"批处理进度: {end_index}/{len(all_keys)} ({progress}%)")
        
        # 检查是否完成
        if end_index >= len(all_keys):
            Logger.log("i", f"全局设置应用完成，共 {state['applied_count']} 个")
            # 继续处理 extruder 设置
            self._processExtruderBatchImport()
        else:
            # 继续下一批，使用QTimer返回事件循环
            QTimer.singleShot(0, self._processBatchImport)
    
    def _processExtruderBatchImport(self):
        """批处理extruder导入"""
        if not self._import_state:
            return
        
        state = self._import_state
        profile = state['profile']
        all_keys = state['all_keys']
        global_stack = state['global_stack']
        
        Logger.log("d", "开始同步设置到 extruder...")
        
        # 同步到所有extruder
        for extruder in global_stack.extruderList:
            # 清空 extruder userChanges
            extruder_user_changes = extruder.userChanges
            if extruder_user_changes:
                for key in list(extruder_user_changes.getAllKeys()):
                    extruder_user_changes.removeInstance(key, postpone_emit=True)
            
            # 写入 extruder qualityChanges
            extruder_quality_changes = extruder.qualityChanges
            if extruder_quality_changes and extruder_quality_changes.getId() != "empty_quality_changes":
                Logger.log("d", f"同步设置到 extruder qualityChanges: {extruder_quality_changes.getId()}")
                for key in all_keys:
                    try:
                        value = profile.getProperty(key, "value")
                        if value is not None:
                            extruder_quality_changes.setProperty(key, "value", value)
                    except Exception as e:
                        Logger.log("w", f"无法同步 {key} 到 extruder: {e}")
        
        Logger.log("d", "Extruder设置同步完成")
        
        # 完成导入
        QTimer.singleShot(0, self._finishBatchImport)
    
    def _finishBatchImport(self):
        """完成批处理导入，触发信号刷新"""
        if not self._import_state:
            return
        
        state = self._import_state
        global_stack = state['global_stack']
        global_quality_changes = state['global_quality_changes']
        user_changes = state['user_changes']
        machine_manager = state['machine_manager']
        config_name = state['config_name']
        applied_count = state['applied_count']
        settings = state['settings']
        temp_path = state['temp_path']
        
        Logger.log("d", "开始触发信号刷新...")
        
        # 触发信号
        global_quality_changes.sendPostponedEmits()
        user_changes.sendPostponedEmits()
        machine_manager.activeStackValueChanged.emit()
        machine_manager.activeQualityGroupChanged.emit()
        
        Logger.log("i", f"配置 '{config_name}' 导入完成！共应用 {applied_count} 个设置")
        
        # 验证
        if self._debug_mode:
            Logger.log("d", "=== 导入后立即验证 ===")
            self._log_key_params(global_stack, global_quality_changes, "  ")
        
        # 清理临时文件
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                Logger.log("d", "临时配置文件已删除")
            except:
                pass
        
        # 延迟刷新
        QTimer.singleShot(100, lambda: self._finalRefresh(global_stack, config_name, applied_count, len(settings)))
        
        # 隐藏加载提示
        self._hideImportingMessage()
        
        # 清理状态
        self._import_state = None

