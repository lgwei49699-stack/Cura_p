import json
import os
import sys
import urllib.parse
import datetime
try:
    from obs import ObsClient
    OBS_SDK_AVAILABLE = True
except ImportError:
    OBS_SDK_AVAILABLE = False
    print("Warning: Not install HUAWEI OBS SDK，Please run 'pip install esdk-obs-python' to install")
from typing import Optional, Dict, Any, Callable
from PyQt6.QtCore import QObject, pyqtSignal, QThread
import hashlib
import threading
import time


class UploadWorker(QThread):
    upload_finished = pyqtSignal(dict)
    upload_progress = pyqtSignal(int)
    metadata = {'Content-Type': 'application/octet-stream'}
    def __init__(self, file_path: str, access_key: str, secret_key: str,  server: str, bucket_name: str):
        super().__init__()
        self.file_path = file_path
        self.access_key = access_key
        self.secret_key = secret_key
        # self.obs_token = obs_token
        self.server = server
        self.bucket_name = bucket_name
        # self.download_url = down_load_url
        
    def run(self):  
        if not OBS_SDK_AVAILABLE:
            self.upload_finished.emit({
                "status": "error",
                "message": "OBS SDK not installed"
            })
            return  
        try:
            obsClient = ObsClient(
                access_key_id=self.access_key,
                secret_access_key=self.secret_key,
                # security_token = self.obs_token,
                server=self.server
            )
            print(f"file path {self.file_path}")
            date_folder = datetime.datetime.now().strftime("%Y%m%d")  
            file_basename = os.path.basename(self.file_path)
            file_name, file_ext = os.path.splitext(file_basename)
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            timestamp_filename = f"{file_name}_{timestamp}{file_ext}"


            # object_key = os.path.basename(self.file_path)
            object_key = f"{date_folder}/{timestamp_filename}"
            object_key = urllib.parse.quote(object_key, safe='/')
            resp = obsClient.putFile(self.bucket_name, object_key, self.file_path, self.metadata)
            
            if resp.status < 300:
                # timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                # download_url = f"https://{self.bucket_name}.{self.server.replace('https://', '')}/{object_key}"
                server_domain = self.server.replace('https://', '')
                encoded_object_key = urllib.parse.quote(object_key, safe='/')
                download_url = f"https://{self.bucket_name}.{server_domain}/{encoded_object_key}"
                # download_url = self.download_url
                self.upload_finished.emit({
                    "status": "success",
                    "download_url": download_url,
                    "object_key": object_key,
                    "file_size": os.path.getsize(self.file_path)
                })
            else:
                self.upload_finished.emit({
                    "status": "error",
                    "message": f"uploader error: {resp.errorMessage}"
                })
                
        except Exception as e:
            self.upload_finished.emit({
                "status": "error",
                "message": str(e)
            })

class GCodeUploader:
    
    def __init__(self, result_callback: Callable[[Dict[str, Any]], None] = None):
        self.result_callback = result_callback
        self._worker = None
        self._download_url = ""
        
    def upload_gcode(self, file_path: str, access_key: str, secret_key: str,
                     server: str, bucket_name: str) -> Dict[str, Any]:
        if not os.path.exists(file_path):
            return {"status": "error", "message": "gcode file not exist"}
            
        if not file_path.lower().endswith(('.gcode')):
            return {"status": "error", "message": "file format error"}
            
        self._worker = UploadWorker(file_path, access_key, secret_key,  server, bucket_name)
        result = {}
        
        def on_finished(res):
            print(f"res data={res}")
            if res["status"] == "success":
                # self._download_url = result["download_url"]
                # file_size = result["file_size"]
                # print(f"uploader success: file_size={file_size}, download_url={self._download_url}")
                if self.result_callback:
                    self.result_callback(res)
            else:
                print("uploader error not enter callback")
            
        self._worker.upload_finished.connect(on_finished)
        self._worker.start()
        
        return result
    