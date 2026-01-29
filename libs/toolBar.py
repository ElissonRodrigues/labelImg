from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QToolBar, QWidgetAction, QToolButton


class ToolBar(QToolBar):

    def __init__(self, title):
        super(ToolBar, self).__init__(title)
        m = (0, 0, 0, 0)
        self.setContentsMargins(*m)
        self.setStyleSheet("QToolBar { spacing: 0px; }")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)

    def addAction(self, action):  # type: ignore
        if isinstance(action, QWidgetAction):
            return super(ToolBar, self).addAction(action)
        btn = ToolButton()
        btn.setDefaultAction(action)
        btn.setToolButtonStyle(self.toolButtonStyle())
        self.addWidget(btn)


class ToolButton(QToolButton):
    """ToolBar companion class which ensures all buttons have the same size."""

    minSize = (60, 60)

    def minimumSizeHint(self):
        ms = super(ToolButton, self).minimumSizeHint()
        w1, h1 = ms.width(), ms.height()
        w2, h2 = self.minSize
        ToolButton.minSize = max(w1, w2), max(h1, h2)
        return QSize(*ToolButton.minSize)
