
import asyncio

from PySide.QtCore import Qt, Signal

from PySide.QtWidgets import (QWidget, QLabel, QVBoxLayout, QLineEdit, QPushButton,
                               QDockWidget, QMessageBox)


from enum import Enum
import tools.log as log
from tools.models import AuthInput, AsyncResponse
from tools.authentication.authentication import AuthenticatedSession


class UIStrings:
    """Constant strings used in the UI."""
    LOGIN_FAILED_TITLE = "Ошибка входа"
    REGISTRATION_FAILED_TITLE = "Ошибка регистрации"
    WRONG_CREDENTIALS = "Указанные логин или пароль не найдены. Повторите попытку, чтобы получить доступ к AI инструментам"
    WRONG_CREDENTIALS_TITLE = "Неверные данные"
    NO_CREDENTIALS = "Укажите логин и пароль, чтобы получить доступ к AI инструментам"
    NO_CREDENTIALS_TITLE = "Нет данных"
    CONNECTION_ABORTED = "Похоже, вы не подключены к интернету. Некоторые функции могут быть не доступны"
    CONNECTION_ABORTED_TITLE = "Нет подключения"
    WEBSOCKET_CONNECTION_ERROR = "Ошибка подключения к серверу аутентификации"
    WEBSOCKET_CONNECTION_ERROR_TITLE = "Ошибка подключения"
    
class LoginWithServicesWidget(QWidget):
    """Widget for OAuth login options."""

    def __init__(self, parent=None):
        super(LoginWithServicesWidget, self).__init__(parent)
        self.setWindowTitle("Sign In With Services")
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

    def add_service(self, icon, text, color):
        button = QPushButton(text, self)
        button.setIcon(icon)
        button.setIconSize(Qt.QSize(24, 24))
        button.setStyleSheet(f"background-color: {color}; text-align: left; padding-left: 10px;")
        self.layout.addWidget(button)
        return button

class AuthenticationFormWidget(QWidget):
    """
    A reusable form widget for username/password input with a main button and a switch button.
    """
    def __init__(self, parent=None, title="", mainButton=None, switchButton=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.mainButtonConfig = mainButton or {}
        self.switchButtonConfig = switchButton or {}
        self.init_ui(title)

    def init_ui(self, title):
        layout = QVBoxLayout(self)
        label = QLabel(title, self)
        label.setAlignment(Qt.AlignCenter)
        font = label.font()
        font.setPointSize(16)
        label.setFont(font)

        username_label = QLabel("Username", self)
        self.username = QLineEdit(self)
        password_label = QLabel("Password", self)
        self.password = QLineEdit(self)
        self.password.setEchoMode(QLineEdit.Password)

        main_button = QPushButton(self.mainButtonConfig.get("text", ""), self)
        main_button.clicked.connect(lambda: self.mainButtonConfig.get("action", lambda x, y: None)(
            self.username.text(), self.password.text()
        ))

        switch_button = QPushButton(self.switchButtonConfig.get("text", ""), self)
        switch_button.setStyleSheet("border: none; background: transparent;")
        switch_button.clicked.connect(self.switchButtonConfig.get("action", lambda: None))

        # Add WebSocket authentication button
        websocket_button = QPushButton("Sign in via Browser", self)
        websocket_button.setStyleSheet("background-color: #007bff; color: white; padding: 8px;")
        websocket_button.clicked.connect(self.mainButtonConfig.get("websocket_action", lambda: None))

        layout.addSpacing(10)
        layout.addWidget(label)
        layout.addSpacing(10)
        layout.addWidget(username_label)
        layout.addWidget(self.username)
        layout.addWidget(password_label)
        layout.addWidget(self.password)
        layout.addSpacing(20)
        layout.addWidget(main_button)
        layout.addSpacing(10)
        layout.addWidget(websocket_button)
        layout.addWidget(switch_button)
        self.setFixedWidth(400)
        self.setLayout(layout)

class RegisterWidget(AuthenticationFormWidget):
    def __init__(self, sign_up_action, switch_action, websocket_action=None, parent=None):
        super().__init__(
            parent,
            title="Sign Up",
            mainButton={"text": "Sign Up", "action": sign_up_action, "websocket_action": websocket_action},
            switchButton={"text": "Sign In", "action": switch_action},
        )

class LoginWidget(AuthenticationFormWidget):
    def __init__(self, sign_in_action, switch_action, websocket_action=None, parent=None):
        super().__init__(
            parent,
            title="Sign In",
            mainButton={"text": "Sign In", "action": sign_in_action, "websocket_action": websocket_action},
            switchButton={"text": "Sign Up", "action": switch_action},
        )

class ArchiAuthenticationWindow(QDockWidget):
    # Define signals for authentication events
    login_success = Signal()
    register_success = Signal()

    class WidgetType(Enum):
        LOGIN = 1
        REGISTER = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ArchiAuthenticationDock")  # Set object name for state saving
        self.setWindowTitle("Authentication")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.setFloating(True)
        self.setFixedWidth(400)
        self.hide()

    def on_send_request(self, response: AsyncResponse):
        if response.has_result():
            QMessageBox.information(self, "Success", "Authentication successful")

    def setup_widgets(self, session: AuthenticatedSession):
        """Set up the login and register widgets with the session."""
        
        async def websocket_auth():
            await session.authenticate_via_websocket(self.on_send_request)
        
        self.loginWidget = LoginWidget(
            lambda username, password: session.login(AuthInput(username=username, password=password), self.on_send_request),
            lambda: self.toggleWidgets(ArchiAuthenticationWindow.WidgetType.REGISTER),
            lambda: asyncio.create_task(websocket_auth())
        )
        self.registerWidget = RegisterWidget(
            lambda username, password: session.sign_up(AuthInput(username=username, password=password), self.on_send_request),
            lambda: self.toggleWidgets(ArchiAuthenticationWindow.WidgetType.LOGIN),
            lambda: asyncio.create_task(websocket_auth())
        )
        self.setWidget(self.loginWidget)

    def toggleWidgets(self, widgetType: 'ArchiAuthenticationWindow.WidgetType'):
        """Switch between login and register forms."""
        if widgetType == ArchiAuthenticationWindow.WidgetType.LOGIN:
            self.registerWidget.hide()
            self.loginWidget.show()
            self.setWidget(self.loginWidget)
        elif widgetType == ArchiAuthenticationWindow.WidgetType.REGISTER:
            self.loginWidget.hide()
            self.registerWidget.show()
            self.setWidget(self.registerWidget)
        self.show()
