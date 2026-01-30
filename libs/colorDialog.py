from PyQt6.QtWidgets import QColorDialog, QDialogButtonBox


class ColorDialog(QColorDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel)
        self.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)

        self.default = None

        # Safely find the QDialogButtonBox in the layout
        self.bb = None
        layout = self.layout()
        if layout:
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item:
                    widget = item.widget()
                    if isinstance(widget, QDialogButtonBox):
                        self.bb = widget
                        break

        if self.bb:
            self.bb.addButton(QDialogButtonBox.StandardButton.RestoreDefaults)
            self.bb.clicked.connect(self.check_restore)

    def getColor(self, value=None, title=None, default=None): # type: ignore
        self.default = default
        if title:
            self.setWindowTitle(title)
        if value:
            self.setCurrentColor(value)
        return self.currentColor() if self.exec() else None

    def check_restore(self, button):
        if (
            self.bb
            and self.bb.buttonRole(button) == QDialogButtonBox.ButtonRole.ResetRole
            and self.default
        ):
            self.setCurrentColor(self.default)
