import FreeCADGui
import FreeCAD
from PySide2.QtCore import Qt
from PySide2.QtWidgets import QGraphicsBlurEffect
from PySide2.QtWidgets import (QWidget, QLabel, QVBoxLayout, QLineEdit, QPushButton,
                               QDockWidget)

from MasterAPI import MasterAPI
from enum import Enum


class AuthenticatedSession:
    def __init__(self, masterAPI: MasterAPI):
        self.masterAPI = masterAPI
        self.authWindow = ArchiAuthenticationWindow(self.login, self.sign_up)
        self.token = None

    def auto_login(self):
        self.token = self.masterAPI.auto_login()
        return self.token is not None

    def login(self, username, password):
        self.token = self.masterAPI.login_via_password(username, password)
        return self.token is not None

    def sign_up(self, username, password):
        status = self.masterAPI.sign_up(username, password)
        if (status == 201):
            return self.login(username, password)
        return False
    def show_login(self):
        self.authWindow.toggleWidgets(ArchiAuthenticationWindow.WidgetType.LOGIN)
        self.authWindow.show()
    def show_register(self):
        self.authWindow.toggleWidgets(ArchiAuthenticationWindow.WidgetType.REGISTER)
        self.authWindow.show()
    def try_auto_auth(self):
        if not self.auto_login():
            self.show_login()
    def get_token(self):
        if(self.token is None):
            complete = self.auto_login()
            if not complete:
                return None
        return self.token
    
    

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
    class WidgetType(Enum):
        LOGIN = 1
        REGISTER = 2

    def __init__(self,
                login_action,
                register_action,
                
                  parent=None):
        super().__init__(parent)
        self.setWindowTitle("Authentication")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.setFloating(True)

        self.loginWidget = LoginWidget(
            login_action,
            lambda: self.toggleWidgets(ArchiAuthenticationWindow.WidgetType.REGISTER)
        )
        self.setWidget(self.loginWidget)
        self.registerWidget = RegisterWidget(
            register_action,
            lambda: self.toggleWidgets(ArchiAuthenticationWindow.WidgetType.LOGIN)
        )
        self.setWidget(self.registerWidget)
        self.setFixedWidth(400)
        self.hide()

    def toggleWidgets(self, widgetType: 'ArchiAuthenticationWindow.WidgetType'):
        if widgetType == ArchiAuthenticationWindow.WidgetType.LOGIN:
            self.registerWidget.hide()
            self.loginWidget.show()
        elif widgetType == ArchiAuthenticationWindow.WidgetType.REGISTER:
            self.loginWidget.hide()
            self.registerWidget.show()
        self.show()


class Archi_Authentication_Command:
    def __init__(self, masterAPI: MasterAPI):
        self.masterAPI: MasterAPI = masterAPI
        self.authWindow: ArchiAuthenticationWindow | None = None
        self.session: AuthenticatedSession | None = None

    def GetResources(self):
        return {
            "MenuText": "Project Context",
            "ToolTip": "Initialize or manage project context",
            "Pixmap": "Archi_ProjectContext"
        }

    def Activated(self):
        if self.authWindow is None:
            mw = FreeCADGui.getMainWindow()
            # find dock widgets with name Authentication
            dock_widgets = mw.findChildren(QDockWidget)
            for widget in dock_widgets:
                # if widget is already open, bring it to front
                if widget.windowTitle() == "Authentication":
                    widget.close()
            self.session = AuthenticatedSession(self.masterAPI)
            self.authWindow = ArchiAuthenticationWindow(self.session)
            mw.addDockWidget(Qt.RightDockWidgetArea, self.authWindow)
            self.authWindow.setFloating(True)
            self.authWindow.try_auto_auth()
        else:
            self.authWindow.toggleWidgets(ArchiAuthenticationWindow.WidgetType.LOGIN)
            self.authWindow.show()

    def IsActive(self):
        return True


# m = MasterAPI("http://localhost:8000")
# FreeCADGui.addCommand("Archi_Authentication", Archi_Authentication_Command(m))
# FreeCADGui.runCommand("Archi_Authentication")