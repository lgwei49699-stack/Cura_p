import sys
import json
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QCheckBox, QHeaderView, QWidget
)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtCore import Qt, pyqtSlot, QUrl, QByteArray, QUrlQuery
from PyQt6.QtCore import QVariant
from PyQt6.QtGui import QFont, QColor, QBrush
from UM.Logger import Logger
from UM.i18n import i18nCatalog
from typing import Any, Dict, List, Callable
from collections.abc import Mapping
from cura.config import DEVICE_QUERY_URL

i18n_catalog = i18nCatalog("uranium")

class MachineSelectionDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("打印机选择")
        self.setModal(True)
        self.resize(900, 600)
        self.network_manager = QNetworkAccessManager()
        self.reply_query = None
        self.reply_obs = None
        self._auth_token = ""
        # self._obs_token = ""
        # self._download_url = ""
        self._device_list = []
        self._device_typr_set = []
        
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setSpacing(20)
        # filter_widget.setStyleSheet("""
        #     QWidget {
        #         background-color: #f0f0f0;
        #         border: 1px solid #ddd;
        #         border-radius: 4px;
        #     }
        # """)
        
        mac_label = QLabel(i18n_catalog.i18n("设备MAC:"))
        self.mac_input = QLineEdit()
        self.mac_input.setPlaceholderText("请输入设备MAC")
        self.mac_input.setFixedHeight(30)
        self.mac_input.setFixedWidth(150)
        
        user_label = QLabel(i18n_catalog.i18n("使用人:"))
        user_label.setMinimumWidth(50)
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("请输入使用人")
        self.user_input.setFixedHeight(30)
        self.user_input.setFixedWidth(120)
        
        model_label = QLabel(i18n_catalog.i18n("设备机型:"))
        self.model_combo = QComboBox()
        self.model_combo.setPlaceholderText("请选择设备机型")
        self.model_combo.setFixedHeight(30)
        self.model_combo.addItem(i18n_catalog.i18n("All"))
        self.model_combo.setFixedWidth(150)
        self.setStyleSheet("""
                           QComboBox,QLineEdit{
                               padding: 8px; 
                               border: 1px solid #ddd; 
                               border-radius: 4px;
                           }
                           """)
        
        self.search_btn = QPushButton(i18n_catalog.i18n("查找"))
        self.search_btn.setStyleSheet("""
            QPushButton {
                background-color: #3580FF;
                color: white;
                border: 1px solid #ddd;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """)
        self.search_btn.clicked.connect(self.apply_filter)
        self.mac_input.textChanged.connect(self.apply_filter)
        self.user_input.textChanged.connect(self.apply_filter)
        self.model_combo.currentIndexChanged.connect(self.apply_filter)
        
        self.reset_btn = QPushButton(i18n_catalog.i18n("重置"))
        self.reset_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #ddd;
                padding: 6px 12px;
                border-radius: 4px;
                color: black;
            }
            QPushButton:hover {
                background-color: #005a9e;
                color: white;
            }
        """)
        self.reset_btn.clicked.connect(self.reset_filter)
        
        filter_layout.addWidget(mac_label)
        filter_layout.addWidget(self.mac_input)
        filter_layout.addWidget(user_label)
        filter_layout.addWidget(self.user_input)
        filter_layout.addWidget(model_label)
        filter_layout.addWidget(self.model_combo)
        
        filter_layout.addWidget(self.search_btn)
        filter_layout.addWidget(self.reset_btn)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "", i18n_catalog.i18n("设备mac"), i18n_catalog.i18n("使用人"), i18n_catalog.i18n("打印机型号"), i18n_catalog.i18n("设备状态"), i18n_catalog.i18n("固件版本号")
        ])
        
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #ddd;
                alternate-background-color: #fafafa;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QHeaderView::section{
                background-color:#FAFAFA;
                height:35px;                 
            } 
        """)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed) 
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) 
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) 
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch) 
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 40)

        header.setStretchLastSection(False)
        self.table.verticalHeader().setVisible(False)
        
        main_layout.addWidget(filter_widget)
        main_layout.addWidget(self.table)
        

        self.confirm_btn = QPushButton(i18n_catalog.i18n("确认"))
        self.confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        self.confirm_btn.clicked.connect(self.accept_confirm)
        
  
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.confirm_btn)
        main_layout.addLayout(button_layout)
        #https://qa-appgw.gongfudou.com/app/print3d/manage/v1/md/query

    def accept_confirm(self):
        if not self.get_selected_rows():
            return
        self.accept()

    def set_auth_token(self, value):
        self._auth_token = value
        self.query_test_device()
        # self.query_obs_token()
    
    def parse_data(self, json_data) -> List[Dict[str, Any]]:
        devices = json_data['data']
        device_list = []
        self._device_typr_set = set()
        for device in devices:
            device_info = {
                'mac': device.get('mac', None),
                'operator': device.get('operator', None),
                'device_type': device.get('deviceType', None),
                'device_status': device.get('deviceStatus', None),
                'last_version': device.get('lastVersionFormat', None),
                'device_sn': device.get('sn', None),
                'device_id': device.get('deviceId', None),
                'status_title': device.get('deviceStatusTitle', None)
            }
            if device.get('deviceType', None) not in self._device_typr_set:
                self._device_typr_set.add(device.get('deviceType', None))
            device_list.append(device_info)
        return device_list

    def on_query_response(self):
        if self.reply_query.error() == QNetworkReply.NetworkError.NoError:
            data = self.reply_query.readAll()      
            response_data = json.loads(data.data().decode('utf-8'))
            Logger.debug("query_response:%s ", response_data)
            if response_data["msg"] == "success":
                self._device_list = self.parse_data(response_data)
                self.update_table(self._device_list)
                self.update_device_type()

    def update_device_type(self):
        for device_type in self._device_typr_set:
            self.model_combo.addItem(device_type)

    def _create_checkbox(self):
        checkbox = QCheckBox()
        checkbox.setStyleSheet("QCheckBox::indicator { width: 16px; height: 16px; }")
        return checkbox

    def _create_table_item(self, text, align_center=True, user_role_data=None, user_role_1_data=None):
        """
        创建统一样式的表格项
        :param text: 显示文本
        :param align_center: 是否居中对齐
        :param user_role_data: UserRole 绑定数据
        :param user_role_1_data: UserRole+1 绑定数据
        :return: QTableWidgetItem
        """
        item = QTableWidgetItem(text)
        if align_center:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if user_role_data is not None:
            item.setData(Qt.ItemDataRole.UserRole, user_role_data)
        if user_role_1_data is not None:
            item.setData(Qt.ItemDataRole.UserRole + 1, user_role_1_data)
        # 可扩展：统一设置文字颜色/背景色等
        return item

    def _fill_device_row(self, row, device):
        """
        填充单行设备数据
        :param row: 行索引
        :param device: 设备字典
        """
        self.table.setCellWidget(row, 0, self._create_checkbox())
        
        self.table.setItem(row, 1, self._create_table_item(
            text=device['mac'],
            user_role_data=device['device_sn'],
            user_role_1_data=device['device_id']
        ))
        self.table.setItem(row, 2, self._create_table_item(device['operator']))
        self.table.setItem(row, 3, self._create_table_item(device['device_type']))
        self.table.setItem(row, 4, self._create_table_item(
            text=device['status_title'],
            user_role_data=device['device_status']
        ))
        self.table.setItem(row, 5, self._create_table_item(device['last_version']))

    def update_table(self, device_list):
        """更新整表数据（清空后重新填充）"""
        self._device_list = device_list 
        self.table.setRowCount(0)
        self.table.setRowCount(len(device_list))
        
        for row, device in enumerate(device_list):
            self._fill_device_row(row, device)

    def get_selected_rows(self):
        selected_devices = []
        for row in range(self.table.rowCount()):
            checkbox = self.table.cellWidget(row, 0)
            if not (checkbox and checkbox.isChecked()):
                continue
            
            mac_item = self.table.item(row, 1)
            status_item = self.table.item(row, 4)
            
            device = {
                'mac': mac_item.text(),
                'device_sn': mac_item.data(Qt.ItemDataRole.UserRole),
                'device_id': mac_item.data(Qt.ItemDataRole.UserRole + 1),
                'operator': self.table.item(row, 2).text(),
                'device_type': self.table.item(row, 3).text(),
                'status_title': status_item.text(),
                'device_status': status_item.data(Qt.ItemDataRole.UserRole),
                'last_version': self.table.item(row, 5).text()
            }
            
            if device.get('device_status', 'offline') == 'offline':
                continue
            print(f"select = {device}")
            selected_devices.append(device)
        return selected_devices

    def query_test_device(self):
        """查询设备列表（网络请求）"""
        request = QNetworkRequest(QUrl(DEVICE_QUERY_URL))
        biz = "ZXBMan"
        request.setRawHeader(b"Authorization", self._auth_token.encode('utf-8'))
        request.setRawHeader(b"Biz", biz.encode("utf-8"))
        self.reply_query = self.network_manager.get(request)
        self.reply_query.finished.connect(self.on_query_response)

    def _filter_device(self, mac_filter, user_filter, model_filter):
        """
        过滤设备列表
        :return: 过滤后的设备列表
        """
        filtered_list = []
        for device in self._device_list:
            mac_match = mac_filter == "" or mac_filter in device["mac"].lower()
            user_match = user_filter == "" or user_filter in device["operator"].lower()
            model_match = model_filter == "All" or model_filter == device["device_type"]
            
            if mac_match and user_match and model_match:
                filtered_list.append(device)
        return filtered_list

    def apply_filter(self):
        """应用筛选条件"""
        mac_filter = self.mac_input.text().lower()
        user_filter = self.user_input.text().lower()
        model_filter = self.model_combo.currentText()
        
        self.table.setRowCount(0)
        
        if not self._device_list:
            self.query_test_device()
        else:
            filtered_devices = self._filter_device(mac_filter, user_filter, model_filter)
            for row, device in enumerate(filtered_devices):
                self.table.insertRow(row)
                self._fill_device_row(row, device)

    def reset_filter(self):
        """重置筛选条件并恢复全量数据"""
        self.mac_input.clear()
        self.user_input.clear()
        self.model_combo.setCurrentIndex(0)
        
        self.table.setRowCount(0)
        for row, device in enumerate(self._device_list):
            self.table.insertRow(row)
            self._fill_device_row(row, device)

    # def get_download_url(self) ->str:
    #     return self._download_url

    # def get_obs_token(self) -> str:
    #     return self._obs_token
                
    
    def exec_(self) -> bool:
        result = self.exec()
        if result == QDialog.DialogCode.Accepted:
            return True
        else:
            return False
