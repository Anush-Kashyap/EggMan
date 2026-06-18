import sys

from PySide6.QtWidgets import QApplication, QWidget


app = QApplication(sys.argv)

window = QWidget()

window.setWindowTitle("EggMan")

window.show()

app.exec()