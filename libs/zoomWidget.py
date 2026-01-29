from PyQt6.QtGui import QFontMetrics
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QSpinBox, QAbstractSpinBox


class ZoomWidget(QSpinBox):

    def __init__(self, value=100):
        super().__init__()
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setRange(1, 500)
        self.setSuffix(" %")
        self.setValue(value)
        self.setToolTip("Zoom Level")
        self.setStatusTip(self.toolTip())
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def minimumSizeHint(self):
        height = super().minimumSizeHint().height()
        fm = QFontMetrics(self.font())
        width = fm.horizontalAdvance(str(self.maximum()))
        return QSize(width, height)
