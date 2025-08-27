from PySide.QtWidgets import QRadioButton
from PySide.QtWidgets import QGraphicsBlurEffect

class MyRadioButton(QRadioButton):
    def __init__(self, parent=None):
        super(MyRadioButton, self).__init__(parent)
        self.toggled.connect(self.on_toggled)
        
        self.activate_blur()
        # Hide the radio button indicator circle and prevent focus/selection outlines
        self.setStyleSheet("""
            QRadioButton::indicator {
                width: 0;
                height: 0;
                margin: 0;
            }
            QRadioButton {
                outline: none;
                border: none;
            }
            QRadioButton:focus {
                outline: none;
                border: none;
            }
        """)
        
    def activate_blur(self):
        self.blur_effect = QGraphicsBlurEffect()
        self.blur_effect.setBlurRadius(5)
        self.setGraphicsEffect(self.blur_effect)
        self.setWindowOpacity(0.5)
        
    def on_toggled(self, checked):
        if checked:
            self.setGraphicsEffect(None)
        else:
            self.activate_blur()
    def toggle_sim(self):
        self.setChecked(not self.isChecked())
        self.on_toggled(self.isChecked())

