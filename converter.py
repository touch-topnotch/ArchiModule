from PySide.QtWidgets import QApplication
from pivy.quarter import QuarterWidget
import sys
app = QApplication(sys.argv)
viewer = QuarterWidget()  # Minimal QuarterWidget initialization
viewer.setWindowTitle("Test QuarterWidget")
viewer.resize(800, 600)
viewer.show()
sys.exit(app.exec_())