import json
import os
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QHttpMultiPart, QHttpPart
from PyQt6.QtCore import QUrl, QByteArray, QObject, pyqtSignal
class GCodeUploadByToken(QObject):
    uploadFinished = pyqtSignal(bool, dict) 
    uploadError = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent) 
        self._download_url = ""
        self.network_manager = QNetworkAccessManager(self)
        self.reply_upload = None
        self.header_data = None
        self._current_file_path = None
        self._tried_cdn = False  # 是否已尝试过 CDN

        self.network_manager.finished.connect(self.on_upload_finished)

    def upload_gcode(self, file_path, header_data):
        self.header_data = header_data
        if not os.path.exists(file_path):
            err = f"File not exist: {file_path}"
            self.uploadError.emit(err)
            print(err)
            return

        if not header_data.get('obs_url') or not header_data.get('key'):
            err = "url is null"
            self.uploadError.emit(err)
            print(err)
            return

        file_name = os.path.basename(file_path)
        print(f"file name={file_name}")

        multi_part = QHttpMultiPart(QHttpMultiPart.ContentType.FormDataType)
        multi_part.setParent(self)

        def add_form_field(field_name, field_value):
            if not isinstance(field_value, str):
                field_value = str(field_value)
            part = QHttpPart()
            disposition = f'form-data; name="{field_name}"'.encode('utf-8')
            part.setRawHeader(b'Content-Disposition', disposition)
            part.setBody(field_value.encode('utf-8'))
            multi_part.append(part)


        add_form_field('key', header_data.get('key', ''))
        add_form_field('policy', header_data.get('policy', ''))
        add_form_field('signature', header_data.get('signature', ''))
        add_form_field('AccessKeyId', header_data.get('AccessKeyId', ''))
        add_form_field('success_action_status', '200')


        file_part = QHttpPart()
        disposition = f'form-data; name="file"; filename="{file_name}"'.encode('utf-8')
        file_part.setRawHeader(b'Content-Disposition', disposition)
        file_part.setRawHeader(b'Content-Type', b'application/octet-stream')
        try:
            with open(file_path, 'rb') as f:
                file_data = QByteArray(f.read())
        except Exception as e:
            err = f"Read file error: {str(e)}"
            self.uploadError.emit(err)
            print(err)
            multi_part.deleteLater()
            return

        # 直接使用 setBody，避免 QBuffer 生命周期问题
        file_part.setBody(file_data)
        multi_part.append(file_part)

        upload_url = f"{header_data.get('obs_url')}"
        print(f"url={upload_url}")
        request = QNetworkRequest(QUrl(upload_url))
        request.setTransferTimeout(60000)  # 60秒超时 

        self.reply_upload = self.network_manager.post(request, multi_part)
        multi_part.setParent(self.reply_upload)
        self.reply_upload.errorOccurred.connect(self.on_upload_error)

    def on_upload_error(self, error: QNetworkReply.NetworkError):
        if not self.reply_upload:
            return
        err_str = self.reply_upload.errorString()
        err = f"upload error [{error}]: {err_str}"
        self.uploadError.emit(err)
        print(err)
        # Note: reply会在on_upload_finished中deleteLater，这里不需要再调用
    
    def cancel_upload(self):
        """取消当前上传"""
        if self.reply_upload:
            print("Cancelling upload...")
            self.reply_upload.abort()
            # abort会触发finished信号，在那里清理

    def on_upload_finished(self, reply: QNetworkReply):
        # 确保是我们的上传请求
        if reply != self.reply_upload:
            reply.deleteLater()
            return
        
        print(f"reply operation: {reply.operation()}")
        status_code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        print(f"status_code: {status_code}")

        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                data = reply.readAll()
                response_str = data.data().decode('utf-8', errors='ignore')
                print(f"upload_response (raw): {response_str}")
                
                # OBS上传成功通常返回204或200，response可能为空
                if status_code in [200, 204]:
                    response_data = {"status": "success", "status_code": status_code}
                    if response_str:
                        try:
                            response_data.update(json.loads(response_str))
                        except json.JSONDecodeError:
                            response_data["raw_response"] = response_str
                    
                    # 构建完整的文件访问URL（CDN URL）
                    if self.header_data:
                        cdn_base = self.header_data.get('cdn', '')
                        file_key = self.header_data.get('key', '')
                        if cdn_base and file_key:
                            full_url = f"{cdn_base}/{file_key}"
                            response_data["file_url"] = full_url
                            print(f"上传成功！文件地址: {full_url}")
                    
                    print(f"upload_response (parsed): {response_data}")
                    self.uploadFinished.emit(True, response_data)
                else:
                    # 非预期的状态码
                    response_data = {
                        "error": f"Unexpected status code: {status_code}",
                        "status_code": status_code,
                        "raw_response": response_str
                    }
                    print(f"upload_response (error): {response_data}")
                    self.uploadFinished.emit(False, response_data)
            else:
                # 读取错误响应体（OBS 通常返回 XML 错误详情）
                data = reply.readAll()
                error_response = data.data().decode('utf-8', errors='ignore')
                err_str = reply.errorString()
                
                response_data = {
                    "error": err_str, 
                    "status_code": status_code,
                    "error_body": error_response
                }
                print(f"upload_error: {response_data}")
                print(f"OBS 错误响应体: {error_response}")
                self.uploadFinished.emit(False, response_data)
                self.uploadError.emit(f"upload error: {err_str}")
        except Exception as e:
            print(f"Exception in on_upload_finished: {str(e)}")
            self.uploadError.emit(f"处理上传响应时出错: {str(e)}")
            self.uploadFinished.emit(False, {"error": str(e)})
        finally:
            reply.deleteLater()
            self.reply_upload = None
