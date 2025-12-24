import json
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QWidget, QCheckBox
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QByteArray, QSettings
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from UM.Logger import Logger
from UM.i18n import i18nCatalog
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5 as Cipher_pkcs1_v1_5
from Crypto import Cipher
import base64
from cura.config import VERIFY_URL, LOGIN_URL, PUBLIC_KEY_URL

i18n_catalog = i18nCatalog("uranium")
class VerificationDialog(QDialog):
    update_token_signal = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n_catalog.i18n("验证码"))
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        self.setFixedSize(300, 150)
        self.network_manager = QNetworkAccessManager()
        self.network_manager.finished.connect(self.verify_response)
        self.verify_success = False
        self.uuid = ""
        self.token= ""
        self.init_ui()

    def verify_response(self, reply: QNetworkReply) :
        self.confirm_btn.setEnabled(True)
        error = reply.error()
        if error == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()      
            response_data = json.loads(data.data().decode('utf-8'))
            Logger.debug("verify_response:%s ", response_data)
            
            if response_data["msg"] == "success":
                self.token = response_data["data"]["token"]
                self.verify_success = True
                self.update_token_signal.emit(self.token)
                self.accept()
            else:
                Logger.debug("verify_response has verified error... ")
                self.setTipText(response_data["msg"])
        else:
            self.verify_success = False
            Logger.debug("verify_response code error... ")

    def auth_token(self) -> str:
        return self.token

    def init_ui(self):
        layout = QVBoxLayout()
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(i18n_catalog.i18n("请输入验证码"))
        layout.addWidget(self.input_field)
        self.tip_label = QLabel()
        self.tip_label.setFixedHeight(20)
        self.tip_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.tip_label)
        self.tip_label.setStyleSheet("font-size:9px; color:red;")
        
        button_layout = QHBoxLayout()
        self.confirm_btn = QPushButton(i18n_catalog.i18n("确认"))
        self.confirm_btn.setFixedHeight(30)
        self.cancel_btn = QPushButton(i18n_catalog.i18n("取消"))
        self.confirm_btn.setFixedHeight(30)
        self.confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                color: #333;
                border: 1px solid #ddd;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
        """)
        
        self.confirm_btn.clicked.connect(self.confirm)
        self.cancel_btn.clicked.connect(self.cancel)
        
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.confirm_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)

    def setTipText(self, text):
        self.tip_label.setText(text)

    def get_code(self):
        return self.input_field.text()
        
    def confirm(self):
        code = self.get_code()
        if not code:
            QMessageBox.warning(self, i18n_catalog.i18n("Warning"), i18n_catalog.i18n("Please input verification code"))
            return
        verify_data = {
            "uuid": self.uuid,
            "tfaCode": code
        }
        json_data = json.dumps(verify_data, ensure_ascii=False)
        request = QNetworkRequest(QUrl(VERIFY_URL))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        self.confirm_btn.setEnabled(False)

        self.network_manager.post(request, QByteArray(json_data.encode('utf-8')))
        # self.accept()
        
    def cancel(self):
        self.reject()
    
    def verify_login(self, uuid) -> bool: 
        self.uuid = uuid
        if self.exec() == QDialog.DialogCode.Accepted:
            if self.verify_success :
                print("verify successfully")
                return True
            else:
                print("verify failly")
                return False
        else:
            return False


class LoginWindow(QDialog):
    login_success = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # self.setWindowTitle(i18n_catalog.i18n("GFD_Cura - Login"))
        self.setWindowTitle(i18n_catalog.i18n("功夫豆Cura - 登录"))
        self.setFixedSize(350, 250)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        self.settings = QSettings("GFD", "Cura")
        self.network_manager = QNetworkAccessManager()
        self.reply_login = None
        self.reply_auth = None
        self._token = ""
        self.setup_ui()
        self._load_cached_credentials()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # title_label = QLabel(i18n_catalog.i18n("Sign in to GFD account"))
        # title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        # layout.addWidget(title_label)
        self._logined = False
        
        username_layout = QHBoxLayout()
        # username_label = QLabel(i18n_catalog.i18nc("@label","Account"))
        username_label = QLabel(i18n_catalog.i18nc("@label","账户"))
        username_label.setStyleSheet("font-size: 12px; color: #666;")
        username_label.setFixedWidth(80)
        self.username_input = QLineEdit()
        # self.username_input.setPlaceholderText(i18n_catalog.i18n("Please enter the account id"))
        self.username_input.setPlaceholderText(i18n_catalog.i18n("请输入账户"))
        self.username_input.setStyleSheet("padding: 8px; border: 1px solid #ddd; border-radius: 4px;")
        # 测试用：预填写账号
        self.username_input.setText("ligw@gongfudou.com")
        username_layout.setStretch(1, 1)
        username_layout.addWidget(username_label)
        username_layout.addWidget(self.username_input)
        layout.addLayout(username_layout)
        
        
        password_layout = QHBoxLayout()
        # password_label = QLabel(i18n_catalog.i18n("Password"))
        password_label = QLabel(i18n_catalog.i18n("密码"))
        password_label.setStyleSheet("font-size: 12px; color: #666;")
        password_label.setFixedWidth(80)
        self.password_input = QLineEdit()
        # self.password_input.setPlaceholderText(i18n_catalog.i18n("Please enter the password"))
        self.password_input.setPlaceholderText(i18n_catalog.i18n("请输入密码"))
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setStyleSheet("padding: 8px; border: 1px solid #ddd; border-radius: 4px;")

        password_layout.setStretch(1, 1)
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        layout.addLayout(password_layout)

        re_layout = QHBoxLayout()
        self.check_remember = QCheckBox("记住账号密码")
        self.check_remember.setChecked(True)

        self.tip_label = QLabel()
        self.tip_label.setFixedHeight(20)
        self.tip_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.tip_label.setStyleSheet("font-size:9px; color:red")
        re_layout.addWidget(self.check_remember)
        re_layout.addStretch()
        re_layout.addWidget(self.tip_label)
        layout.addLayout(re_layout)

        button_layout = QHBoxLayout()
        
        # cancel_button = QPushButton(i18n_catalog.i18n("Cancel"))
        cancel_button = QPushButton(i18n_catalog.i18n("取消"))
        cancel_button.setFixedHeight(32)
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                color: #333;
                border: 1px solid #ddd;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
        """)
        cancel_button.clicked.connect(self.cancel_login)
        
        # self.login_button = QPushButton(i18n_catalog.i18n("Login"))
        self.login_button = QPushButton(i18n_catalog.i18n("登录"))
        self.login_button.setFixedHeight(32)
        self.login_button.setFocus()
        self.login_button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        self.login_button.clicked.connect(self.attempt_login)
        button_layout.addStretch()
        
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(self.login_button)
        layout.addLayout(button_layout)
        
        # remember_layout = QHBoxLayout()
        # self.remember_checkbox = QCheckBox("记住密码")
        # self.remember_checkbox.setStyleSheet("font-size: 12px; color: #666;")
        # remember_layout.addWidget(self.remember_checkbox)
        # remember_layout.addStretch()
        # layout.addLayout(remember_layout)
        
        self.setLayout(layout)

    def _load_cached_credentials(self):
        """读取本地缓存的账号密码，自动填充到输入框"""
        username = self.settings.value("login/username", "")
        password = self.settings.value("login/password", "")
        remember = self.settings.value("login/remember", True, type=bool)
        
        self.username_input.setText(username)
        self.password_input.setText(password)
        self.check_remember.setChecked(remember)

    def _save_credentials(self):
        """保存账号密码到本地（根据复选框状态）"""
        if self.check_remember.isChecked():
            # 保存账号密码
            self.settings.setValue("login/username", self.username_input.text().strip())
            self.settings.setValue("login/password", self.password_input.text().strip())
            self.settings.setValue("login/remember", True)
        else:
            # 清空缓存
            self.settings.remove("login/username")
            self.settings.remove("login/password")
            self.settings.setValue("login/remember", False)
        
        # 立即同步到文件（可选，QSettings默认自动同步）
        self.settings.sync()
    
    def setTipText(self, text):
        self.tip_label.setText(text)
    
    def on_auth_finished(self):
        if self.reply_auth.error() == QNetworkReply.NetworkError.NoError:
            data = self.reply_auth.readAll()      
            response_data = json.loads(data.data().decode('utf-8'))
            Logger.debug("auth_response:%s ", response_data)
            if response_data["msg"] == "success":
               username = self.username_input.text().strip()
               password = self.password_input.text().strip()


               public_key = response_data["data"]
               if not username or not password:
                #    QMessageBox.warning(self, i18n_catalog.i18n("Input error"), i18n_catalog.i18n("Please enter your username and password."))
                   QMessageBox.warning(self, i18n_catalog.i18n("输入错误"), i18n_catalog.i18n("请输入账户或密码."))
                   return
               login_data = {
                   "email": username,
                   "password": self.rsa_encrypt(password, public_key)
               }
               json_data = json.dumps(login_data, ensure_ascii=False)
               request = QNetworkRequest(QUrl(LOGIN_URL))
               request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
               # self.login_button.setEnabled(False)
               Logger.debug("login_request:%s ", json_data)
               self.reply_login = self.network_manager.post(request, QByteArray(json_data.encode('utf-8')))
               self.reply_login.finished.connect(self.on_login_response)

    def attempt_login(self):
        request = QNetworkRequest(QUrl(PUBLIC_KEY_URL))
        self.login_button.setEnabled(False)
        self.reply_auth = self.network_manager.get(request)
        self.reply_auth.finished.connect(self.on_auth_finished)


    def rsa_encrypt(self, password, public_key) -> str:
        # public_key = base64.b64decode(public_key).decode('utf-8')
        # rsakey = RSA.importKey(public_key)
        # encrypted = rsakey.encrypt(password.encode('utf-8'), 32)[0]
        # return base64.b64encode(encrypted).decode('utf-8')
        try:
            public_key = public_key.replace(" ", "").replace("\n", "")
            
            key_bytes = base64.b64decode(public_key)
            from Crypto.PublicKey import RSA
            rsakey = RSA.importKey(key_bytes)
            
            cipher = Cipher_pkcs1_v1_5.new(rsakey)
            encrypted = cipher.encrypt(password.encode('utf-8'))
            return base64.b64encode(encrypted).decode('utf-8')
    
        except UnicodeDecodeError:
            Logger.error("Base decode error")
        except ValueError as ve:
            Logger.error(f"rsa error: {ve}")
        except Exception as e:
            Logger.error(f"encode error: {e}")
    
    def on_login_response(self):
        self.login_button.setEnabled(True)
        
        error = self.reply_login.error()
        if error == QNetworkReply.NetworkError.NoError:
            data = self.reply_login.readAll()      
            response_data = json.loads(data.data().decode('utf-8'))
            Logger.debug("login_response:%s ", response_data)
            if response_data["msg"] == "success":
                if self.verify_credentials(response_data["data"]["uuid"]):
                    self._save_credentials()
                    self._logined = True
                    self.accept()
                else:
                    Logger.debug("login_response error... ")
                    self._logined = False
            else:
                self.setTipText(response_data["msg"])
        else:
            self._logined = False
        
        
            
    def cancel_login(self):
        confirm_dialog = QMessageBox(self)
        confirm_dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        confirm_dialog.setWindowTitle(i18n_catalog.i18n("确认"))
        confirm_dialog.setIcon(QMessageBox.Icon.Question)
        # confirm_dialog.setText(i18n_catalog.i18n("Are you sure you want to close the app without logging in?"))
        confirm_dialog.setText(i18n_catalog.i18n("确认不登录并且关闭应用嘛"))
        confirm_dialog.setStandardButtons(QMessageBox.StandardButton.No | QMessageBox.StandardButton.Yes)
        confirm_dialog.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        continue_btn = confirm_dialog.button(QMessageBox.StandardButton.No)
        sure_btn = confirm_dialog.button(QMessageBox.StandardButton.Yes)
        sure_btn.setText(i18n_catalog.i18n("取消"))
        continue_btn.setText(i18n_catalog.i18n("确认"))
        
        continue_btn.setStyleSheet("""
        QPushButton {
                width:60px;
                height:30px;
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        sure_btn.setStyleSheet("""
        QPushButton {
                width:60px;
                height:28px;
                border: 1px solid gray;
                border-radius: 4px;
            }
        """)
        result = confirm_dialog.exec()
        
        if result == QMessageBox.StandardButton.Yes:
            # self.login_canceled.emit()
            self._logined = False
        else:
            self.reject()
        
    def verify_credentials(self, uuid) -> bool:
        dialog = VerificationDialog()
        dialog.update_token_signal.connect(self.on_update_token)
        return dialog.verify_login(uuid)
    
    def on_update_token(self, token):
        Logger.debug("toker: %s", token)
        self._token = token
          
    def auth_token(self) -> str:
        return self._token

    def exec_login(self) -> bool:
        result = self.exec()
        if result == QDialog.DialogCode.Accepted:
            if self._logined:
                print("login success")
                return True
            else:
                return False
        else:
            print("login failed")
            return False

