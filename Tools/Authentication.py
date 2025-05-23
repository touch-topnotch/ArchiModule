import FreeCADGui
import hashlib
import requests
import keyring

from PySide.QtCore import Qt, Signal, QTimer
from PySide.QtWidgets import QGraphicsBlurEffect
from PySide.QtWidgets import (QWidget, QLabel, QVBoxLayout, QLineEdit, QPushButton,
                               QDockWidget, QMessageBox)

from tools.master_api import MasterAPI
from enum import Enum
import tools.log as log
from tools.models import AuthInput, Token, AsyncResponse
from typing import Callable

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

class AuthenticatedSession:
    APP_NAME = "Archi"
    
    def __init__(self, masterAPI: MasterAPI):
        self.masterAPI = masterAPI
        self.token = None
        self.last_token_update = 0
        self.authWindow = None
        self.on_login_callback = None
        self.on_error_callback = None
        self.has_internet_connection = True

    def _hash_password(self, password: str) -> str:
        """Returns SHA-256 hash of the password."""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    def _handle_network_error(self, err_msg: str, callback: Callable[[AsyncResponse], None]):
        self.has_internet_connection = False
        callback(AsyncResponse(error=Exception(err_msg)))

    def _login_via_credentials(self, auth_input: AuthInput) -> AsyncResponse:
        hashed_pw = self._hash_password(auth_input.password)
        try:
            resp = requests.post(
                f"{self.masterAPI.API_BASE_URL}/auth/token",
                data={"username": auth_input.username, "password": hashed_pw},
            )
            if resp.status_code == 200:
                keyring.set_password(self.APP_NAME, "username", auth_input.username)
                keyring.set_password(self.APP_NAME, "password", auth_input.password)
                log.info(f"Login successful")
                self.token = Token(**resp.json())
                return AsyncResponse(result=self.token)
            return AsyncResponse(error=Exception(resp.text))
        except (ConnectionAbortedError, ConnectionResetError) as e:
            self._handle_network_error(str(e), lambda r: None)
            return AsyncResponse(error=Exception(UIStrings.CONNECTION_ABORTED))
        except Exception as e:
            log.error(f"Login error: {str(e)}")
            return AsyncResponse(error=Exception(str(e)))

    def _sign_up_via_credentials(self, auth_input: AuthInput) -> AsyncResponse:
        hashed_pw = self._hash_password(auth_input.password)
        try:
            resp = requests.post(
                f"{self.masterAPI.API_BASE_URL}/auth/",
                json={"username": auth_input.username, "password": hashed_pw},
            )
            if resp.status_code == 200:
                return self._login_via_credentials(auth_input)
            log.error(f"Registration error: {resp.text}")
            return AsyncResponse(error=Exception(resp.text))
        except (ConnectionAbortedError, ConnectionResetError) as e:
            log.error(f"Registration error: {str(e)}")
            self._handle_network_error(str(e), lambda r: None)
            return AsyncResponse(error=Exception(UIStrings.CONNECTION_ABORTED))
        except Exception as e:
            log.error(f"Registration error: {str(e)}")
            return AsyncResponse(error=Exception(str(e)))

    def set_auth_window(self, window):
        """Set the authentication window and configure callbacks."""
        if not window:
            log.error("Cannot set null authentication window")
            return
            
        self.authWindow = window
        self.authWindow.login_success.connect(self._on_login_success)
        self.authWindow.register_success.connect(self._on_register_success)

    def _on_login_success(self, response: AsyncResponse):
        """Handle successful login."""
        if not response:
            log.error("Received null result in login success handler")
            return
            
        if response.has_error():
            log.error(f"Login failed: {response.error}")
            if self.authWindow:
                QMessageBox.warning(self.authWindow, UIStrings.LOGIN_FAILED_TITLE, str(response.error))
            if self.on_error_callback:
                self.on_error_callback(response.error)
            return

        self.token = response.result
        log.info("User successfully logged in")
        if self.on_login_callback:
            self.on_login_callback(response.result)

    def _on_register_success(self, response: AsyncResponse):
        """Handle successful registration."""
        if not response:
            log.error("Received null result in registration success handler")
            return
            
        if response.has_error():
            log.error(f"Registration failed: {response.error}")
            if self.authWindow:
                QMessageBox.warning(self.authWindow, UIStrings.REGISTRATION_FAILED_TITLE, str(response.error))
            if self.on_error_callback:
                self.on_error_callback(response.error)
            return

        self.token = response.result
        log.info("User successfully registered")
        if self.on_login_callback:
            self.on_login_callback(response.result)

    def auto_login(self, callback: Callable[[AsyncResponse], None]):
        """Attempt to login automatically using saved credentials."""
        if not self.masterAPI:
            log.error("Cannot auto-login: master API not initialized")
            callback(AsyncResponse(error=Exception("Master API not initialized")))
            return
        if self.token and not self.token.is_expired:
            log.info(f"Token is {self.token}, {self.token.is_expired}, {self.token.expires_at}")
            callback(AsyncResponse(result=self.token))
            return
        if self.token and self.token.is_expired:
            log.info("Token is expired, deleting it")
            self.token = None
            
        username = keyring.get_password(self.APP_NAME, "username")
        password = keyring.get_password(self.APP_NAME, "password")
        
        if username and password:
            auth_input = AuthInput(username=username, password=password)
            self.masterAPI._run_async(self._login_via_credentials, callback, auth_input)
        else:
            callback(AsyncResponse(error=Exception(UIStrings.NO_CREDENTIALS)))

    def login(self, auth_input: AuthInput, callback: Callable[[AsyncResponse], None]):
        """Login with username and password."""
        if not self.masterAPI:
            log.error("Cannot login: master API not initialized")
            callback(AsyncResponse(error=Exception("Master API not initialized")))
            return
            
        def on_login(response: AsyncResponse):
            if not response:
                log.error("Received null result in login handler")
                callback(AsyncResponse(error=Exception("Received null result in login handler")))
                return
            if response.has_error():
                log.error(f"Login failed: {response.error}")
                if self.authWindow:
                    QMessageBox.warning(self.authWindow, UIStrings.LOGIN_FAILED_TITLE, str(response.error))
                if self.on_error_callback:
                    self.on_error_callback(response.error)
                callback(response)
                return
            
            self._on_login_success(response)
            log.info(f"Token is {self.token}, {self.token.is_expired}, {self.token.expires_at}, {callback}, {AsyncResponse(token=self.token)}")
            callback(AsyncResponse(token=self.token))

        self.masterAPI.run_async_task(self._login_via_credentials, on_login, auth_input=auth_input)

    def sign_up(self, auth_input: AuthInput, callback: Callable[[AsyncResponse], None]):
        """Register a new user."""
        if not self.masterAPI:
            log.error("Cannot sign up: master API not initialized")
            callback(AsyncResponse(error=Exception("Master API not initialized")))
            return
            
        def on_signup(response: AsyncResponse):
            if response.has_error():
                log.error(f"Registration failed: {response.error}")
                if self.on_error_callback:
                    self.on_error_callback(response.error)
                callback(response)
                return

            if not response:
                log.error("Received null result in signup handler")
                callback(AsyncResponse(error=Exception("Received null result in signup handler")))
                return

            self._on_register_success(response)
            callback(AsyncResponse(token=self.token))

        self.masterAPI.run_async_task(self._sign_up_via_credentials, on_signup, auth_input=auth_input)

    def show_login(self):
        """Show the login form."""
        if not self.authWindow:
            log.error("Cannot show login: authentication window not initialized")
            return
            
        self.authWindow.toggleWidgets(ArchiAuthenticationWindow.WidgetType.LOGIN)
        self.authWindow.show()

    def show_register(self):
        """Show the registration form."""
        if not self.authWindow:
            log.error("Cannot show register: authentication window not initialized")
            return
            
        self.authWindow.toggleWidgets(ArchiAuthenticationWindow.WidgetType.REGISTER)
        self.authWindow.show()
        
    def get_token(self, callback: Callable[[AsyncResponse], None]):
        """Get the current authentication token."""
        if self.token is None or self.token.is_expired:
            self.auto_login(callback)
        return self.token

    def is_authenticated(self):
        """Check if the user is currently authenticated."""
        return self.token is not None and not self.token.is_expired


class LoginWithServicesWidget(QWidget):

    def __init__(self, parent=None):
        '''
        Login with google, facebook, apple, github.
        each button should contain: icon, text, color
        '''
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

        layout.addSpacing(10)
        layout.addWidget(label)
        layout.addSpacing(10)
        layout.addWidget(username_label)
        layout.addWidget(self.username)
        layout.addWidget(password_label)
        layout.addWidget(self.password)
        layout.addSpacing(30)
        layout.addWidget(main_button)
        layout.addWidget(switch_button)
        self.setFixedWidth(400)
        self.setLayout(layout)


class RegisterWidget(AuthenticationFormWidget):
    def __init__(self, sign_up_action, switch_action, parent=None):
        super().__init__(
            parent,
            title="Sign Up",
            mainButton={"text": "Sign Up", "action": sign_up_action},
            switchButton={"text": "Sign In", "action": switch_action},
        )


class LoginWidget(AuthenticationFormWidget):
    def __init__(self, sign_in_action, switch_action, parent=None):
        super().__init__(
            parent,
            title="Sign In",
            mainButton={"text": "Sign In", "action": sign_in_action},
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
        self.loginWidget = LoginWidget(
            lambda username, password: session.login(AuthInput(username=username, password=password), self.on_send_request),
            lambda: self.toggleWidgets(ArchiAuthenticationWindow.WidgetType.REGISTER)
        )
        self.registerWidget = RegisterWidget(
            lambda username, password: session.sign_up(AuthInput(username=username, password=password), self.on_send_request),
            lambda: self.toggleWidgets(ArchiAuthenticationWindow.WidgetType.LOGIN)
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


class Archi_Authentication_Command:
    def __init__(self, masterAPI: MasterAPI):
        self.masterAPI: MasterAPI = masterAPI
        self.authWindow: ArchiAuthenticationWindow | None = None
        self.session: AuthenticatedSession | None = None
        

    def GetResources(self):
        return {
            "MenuText": "Authentication",
            "ToolTip": "Sign in or create an account",
            "Pixmap": "Archi_Authentication"
        }


    def Activated(self):
        """Handle authentication command activation."""
        log.info("Authentication command activated")
        
        try:
            if self.authWindow is None:
                self._initialize_auth_window()

                
            if self.session and self.session.is_authenticated():
                log.info("Session is authenticated, calling _on_authentication_success")
                self._on_authentication_success(AsyncResponse(result=True))
                return
        
            # Добавляем небольшую задержку перед auto_login
            QTimer.singleShot(100, lambda: self.session.auto_login(
                lambda response: self._on_authentication_success(response) if response.has_result() 
                else self._show_existing_window()
            ))

            
        except Exception as e:
            log.error(f"Error in authentication command: {str(e)}")
            
    def _initialize_auth_window(self):
        """Initialize and show a new authentication window."""
        log.info("Initializing authentication window")
        mw = FreeCADGui.getMainWindow()
        self._close_existing_auth_windows(mw)
        
        # Create session and window
        self.session = AuthenticatedSession(self.masterAPI)
        self.authWindow = ArchiAuthenticationWindow(mw)
        self.authWindow.setup_widgets(self.session)
        
        # Set up callbacks
        self.session.set_auth_window(self.authWindow)
        self.session.on_login_callback = self._on_authentication_success
        
        # Add window to main window
        mw.addDockWidget(Qt.RightDockWidgetArea, self.authWindow)
        self.authWindow.setFloating(True)

    def _show_existing_window(self):
        """Show the existing authentication window."""
        if self.authWindow:
            self.authWindow.toggleWidgets(ArchiAuthenticationWindow.WidgetType.LOGIN)
            self.authWindow.show()
            self.authWindow.raise_()  
            self.authWindow.activateWindow()
        
    def _close_existing_auth_windows(self, main_window):
        """Close any existing authentication windows."""
        dock_widgets = main_window.findChildren(QDockWidget)
        for widget in dock_widgets:
            if widget.windowTitle() == "Authentication":
                widget.close()
        log.info("Closed existing authentication windows")

    def _on_authentication_success(self, response: AsyncResponse):
        """Handle successful authentication."""
        log.info("Authentication successful")
        if self.authWindow:
            self.authWindow.hide()

    def IsActive(self):
        return True


# m = MasterAPI("http://localhost:8000")
# FreeCADGui.addCommand("Archi_Authentication", Archi_Authentication_Command(m))
# FreeCADGui.runCommand("Archi_Authentication")