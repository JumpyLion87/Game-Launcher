from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, 
    QPushButton, QLabel, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QObject
from src.api.auth_api import AuthAPI, AuthResult
import asyncio

class LoginSignals(QObject):
    success = Signal(AuthResult)
    error = Signal(str)

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.auth_api = AuthAPI()
        self.auth_result = None
        self.signals = LoginSignals()
        self.setObjectName("login-dialog")
        self.setup_ui()
        
        # Подключаем сигналы
        self.signals.success.connect(self.on_login_success)
        self.signals.error.connect(self.on_login_error)
        
    def setup_ui(self):
        """Настройка интерфейса"""
        self.setWindowTitle("Авторизация")
        self.setFixedSize(350, 320)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Заголовок
        title = QLabel("Вход в аккаунт")
        title.setAlignment(Qt.AlignCenter)
        title.setProperty("class", "login-title")
        layout.addSpacing(5)
        layout.addWidget(title)
        layout.addSpacing(20)
        
        # Поля ввода
        self.username = QLineEdit()
        self.username.setPlaceholderText("Имя аккаунта")
        self.username.setProperty("class", "login-input")
        self.username.setFixedHeight(40)
        layout.addWidget(self.username)
        layout.addSpacing(15)
        
        self.password = QLineEdit()
        self.password.setPlaceholderText("Пароль")
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setProperty("class", "login-input")
        self.password.setFixedHeight(40)
        layout.addWidget(self.password)
        layout.addSpacing(20)
        
        # Кнопка входа
        self.login_button = QPushButton("Войти")
        self.login_button.setProperty("class", "login-button")
        self.login_button.setFixedHeight(40)
        self.login_button.clicked.connect(self.handle_login)
        layout.addWidget(self.login_button)
        layout.addSpacing(15)
        
        # Дополнительные кнопки
        self.register_button = QPushButton("Регистрация")
        self.register_button.setProperty("class", "link-button")
        layout.addWidget(self.register_button)
        
        self.forgot_button = QPushButton("Забыли пароль?")
        self.forgot_button.setProperty("class", "link-button")
        layout.addWidget(self.forgot_button)
        
    def handle_login(self):
        """Обработчик нажатия кнопки входа"""
        username = self.username.text().strip()
        password = self.password.text().strip()
        
        if not username or not password:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Введите имя аккаунта и пароль"
            )
            return
            
        # Отключаем кнопку на время авторизации
        self.login_button.setEnabled(False)
        self.login_button.setText("Вход...")
        
        # Запускаем асинхронную авторизацию
        loop = asyncio.get_event_loop()
        loop.create_task(self.try_login(username, password))
        
    async def try_login(self, username: str, password: str):
        """Асинхронная попытка авторизации"""
        try:
            result = await self.auth_api.login(username, password)
            if result.success:
                self.signals.success.emit(result)
            else:
                self.signals.error.emit(result.message)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            # Возвращаем кнопку в исходное состояние
            self.login_button.setEnabled(True)
            self.login_button.setText("Войти")
            
    def on_login_success(self, result: AuthResult):
        """Обработчик успешной авторизации"""
        self.auth_result = result
        self.accept()
        
    def on_login_error(self, message: str):
        """Обработчик ошибки авторизации"""
        QMessageBox.warning(
            self,
            "Ошибка авторизации",
            message
        ) 