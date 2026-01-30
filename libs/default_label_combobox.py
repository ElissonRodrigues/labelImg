from PyQt6.QtWidgets import QWidget, QHBoxLayout, QComboBox


class DefaultLabelComboBox(QWidget):
    def __init__(self, parent=None, items=[]):
        super(DefaultLabelComboBox, self).__init__(parent)

        layout = QHBoxLayout()
        self.cb = QComboBox()
        self.items = items
        self.cb.addItems(self.items)

        if parent and hasattr(parent, "default_label_combo_selection_changed"):
            self.cb.currentIndexChanged.connect(
                parent.default_label_combo_selection_changed
            )

        layout.addWidget(self.cb)
        self.setLayout(layout)

    def update_items(self, items):
        if self.items == items:
            return

        current_text = self.cb.currentText()
        self.cb.blockSignals(True)
        self.cb.clear()
        self.items = items
        self.cb.addItems(self.items)

        # Restore previous selection if it's still available
        if current_text in self.items:
            index = self.cb.findText(current_text)
            self.cb.setCurrentIndex(index)

        self.cb.blockSignals(False)
