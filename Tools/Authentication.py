import FreeCADGui
import FreeCAD

from PySide.QtCore import Qt, Signal
from PySide.QtWidgets import QGraphicsBlurEffect
from PySide.QtWidgets import (QWidget, QLabel, QVBoxLayout, QLineEdit, QPushButton,
                               QDockWidget)

from tools.master_api import MasterAPI
from enum import Enum
import tools.log as log

class AuthenticatedSession:
    def __init__(self, masterAPI: MasterAPI):
        self.masterAPI = masterAPI
        self.token = None
        self.authWindow = None
        self.on_login_callback = None

    def set_auth_window(self, window):
        """Set the authentication window and configure callbacks."""
        self.authWindow = window
        self.authWindow.login_success.connect(self._on_login_success)
        self.authWindow.register_success.connect(self._on_register_success)

    def _on_login_success(self):
        """Handle successful login."""
        log.info("User successfully logged in")
        if self.on_login_callback:
            self.on_login_callback()

    def _on_register_success(self):
        """Handle successful registration."""
        log.info("User successfully registered")
        if self.on_login_callback:
            self.on_login_callback()

    def auto_login(self):
        """Attempt to login automatically using saved credentials."""
        self.token = self.masterAPI.auto_login()
        if self.token is not None:
            log.info("Auto-login successful")
            self._on_login_success()
        return self.token is not None

    def login(self, username, password):
        """Login with username and password."""
        self.token = self.masterAPI.login_via_password(username, password)
        if self.token is not None:
            log.info(f"Login successful for user: {username}")
            self._on_login_success()
        return self.token is not None

    def sign_up(self, username, password):
        """Register a new user."""
        status = self.masterAPI.sign_up(username, password)
        if status == 201:
            success = self.login(username, password)
            if success:
                log.info(f"Registration and login successful for user: {username}")
                self._on_register_success()
            return success
        return False

    def show_login(self):
        """Show the login form."""
        if self.authWindow:
            self.authWindow.toggleWidgets(ArchiAuthenticationWindow.WidgetType.LOGIN)
            self.authWindow.show()

    def show_register(self):
        """Show the registration form."""
        if self.authWindow:
            self.authWindow.toggleWidgets(ArchiAuthenticationWindow.WidgetType.REGISTER)
            self.authWindow.show()

    def try_auto_auth(self):
        """Attempt auto-login, fall back to login form if unsuccessful."""
        if not self.auto_login():
            self.show_login()

    def get_token(self):
        """Get the current authentication token."""
        if self.token is None:
            complete = self.auto_login()
            if not complete:
                return None
        return self.token

    def is_authenticated(self):
        """Check if the user is currently authenticated."""
        return self.token is not None


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


class FormWidget(QWidget):
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


class RegisterWidget(FormWidget):
    def __init__(self, sign_up_action, switch_action, parent=None):
        super().__init__(
            parent,
            title="Sign Up",
            mainButton={"text": "Sign Up", "action": sign_up_action},
            switchButton={"text": "Sign In", "action": switch_action},
        )


class LoginWidget(FormWidget):
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
        self.setWindowTitle("Authentication")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.setFloating(True)
        self.setFixedWidth(400)
        self.hide()

    def setup_widgets(self, session):
        """Set up the login and register widgets with the session."""
        self.loginWidget = LoginWidget(
            session.login,
            lambda: self.toggleWidgets(ArchiAuthenticationWindow.WidgetType.REGISTER)
        )
        self.registerWidget = RegisterWidget(
            session.sign_up,
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
            else:
                self._show_existing_window()
                
            # Try auto-login first
            self.session.try_auto_auth()
            
        except Exception as e:
            log.error(f"Error in authentication command: {str(e)}")
            
    def _initialize_auth_window(self):
        """Initialize and show a new authentication window."""
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
            log.info("Showing existing authentication window")
        
    def _close_existing_auth_windows(self, main_window):
        """Close any existing authentication windows."""
        dock_widgets = main_window.findChildren(QDockWidget)
        for widget in dock_widgets:
            if widget.windowTitle() == "Authentication":
                widget.close()
        log.info("Closed existing authentication windows")

    def _on_authentication_success(self):
        """Handle successful authentication."""
        log.info("Authentication successful")
        if self.authWindow:
            self.authWindow.hide()

    def IsActive(self):
        return True


# m = MasterAPI("http://localhost:8000")
# FreeCADGui.addCommand("Archi_Authentication", Archi_Authentication_Command(m))
# FreeCADGui.runCommand("Archi_Authentication")