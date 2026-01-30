from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QHBoxLayout,
    QMessageBox,
    QFrame,
    QHeaderView,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QApplication,
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, QTimer
from PyQt6.QtGui import QColor, QBrush
from libs.database import Class, Image, Annotation
from sqlalchemy import func
from datetime import datetime


class StatCard(QFrame):
    def __init__(self, title, value, color="#3498db", parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 110)
        self.setObjectName("StatCard")

        # Glassmorphism style
        self.setStyleSheet(
            f"""
            #StatCard {{
                background-color: rgba(40, 40, 40, 180);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 16px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """
        )

        # Shadow for depth
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(6)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            "color: #ecf0f1; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px;"
        )

        self.value_label = QLabel(str(value))
        self.value_label.setStyleSheet(
            f"color: {color}; font-size: 36px; font-weight: 900;"
        )

        layout.addWidget(self.title_label, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.value_label, alignment=Qt.AlignmentFlag.AlignLeft)

        # Entrance animation (Scale up effect)
        self.anim = QPropertyAnimation(self, b"maximumSize")
        self.anim.setDuration(600)
        self.anim.setStartValue(QSize(0, 110))
        self.anim.setEndValue(QSize(200, 110))
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)

    def pulse(self):
        # Let's just use a simple stylesheet flash
        original_style = self.styleSheet()
        self.setStyleSheet(
            original_style + " #StatCard { background-color: rgba(52, 152, 219, 80); }"
        )
        QTimer.singleShot(500, lambda: self.setStyleSheet(original_style))

    def showEvent(self, a0):
        super().showEvent(a0)
        self.anim.start()

    def update_value(self, value):
        self.value_label.setText(str(value))


class StatisticsDialog(QDialog):
    def __init__(self, parent=None, db_session=None):
        super().__init__(parent)
        self.db_session = db_session
        self.setup_ui()

        if self.db_session:
            self.load_statistics()

    def setup_ui(self):
        self.setWindowTitle("Project Analytics Dashboard")
        self.resize(850, 650)
        self.setObjectName("StatsDialog")

        # Modern Dark Theme with Glassmorphism hints
        self.setStyleSheet(
            """
            #StatsDialog {
                background-color: #0f0f0f;
            }
            QLabel {
                color: #ffffff;
            }
            QTableWidget {
                background-color: #1a1a1a;
                color: #e0e0e0;
                gridline-color: #2a2a2a;
                border: 1px solid #333;
                border-radius: 16px;
                font-size: 14px;
                outline: none;
            }
            QTableWidget::item {
                padding: 15px;
                border-bottom: 1px solid #252525;
            }
            QTableWidget::item:selected {
                background-color: #2c3e50;
                color: #3498db;
            }
            QHeaderView::section {
                background-color: #1a1a1a;
                color: #3498db;
                padding: 15px;
                border: none;
                border-bottom: 2px solid #3498db;
                font-weight: 900;
                font-size: 12px;
                text-transform: uppercase;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 12px;
                padding: 14px 28px;
                font-weight: 900;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton#CloseBtn {
                background-color: transparent;
                border: 2px solid #e74c3c;
                color: #e74c3c;
            }
            QPushButton#CloseBtn:hover {
                background-color: #e74c3c;
                color: white;
            }
        """
        )

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 40, 40, 40)
        self.main_layout.setSpacing(35)

        # Header Title
        title_container = QHBoxLayout()
        header_title = QLabel("Project Insights")
        header_title.setStyleSheet(
            "font-size: 32px; font-weight: 900; color: #ffffff; letter-spacing: -1px;"
        )

        self.last_sync_label = QLabel("Last update: Just now")
        self.last_sync_label.setStyleSheet(
            "color: #7f8c8d; font-size: 12px; font-weight: 500; margin-top: 15px;"
        )

        title_container.addWidget(header_title)
        title_container.addStretch()
        title_container.addWidget(
            self.last_sync_label, alignment=Qt.AlignmentFlag.AlignBottom
        )
        self.main_layout.addLayout(title_container)

        # Summary Row (Cards)
        self.summary_layout = QHBoxLayout()
        self.card_images = StatCard("Total Images", 0, "#3498db")
        self.card_annots = StatCard("Annotations", 0, "#2ecc71")
        self.card_classes = StatCard("Classes", 0, "#f1c40f")

        self.summary_layout.addWidget(self.card_images)
        self.summary_layout.addWidget(self.card_annots)
        self.summary_layout.addWidget(self.card_classes)
        self.summary_layout.addStretch()

        self.main_layout.addLayout(self.summary_layout)

        # Table Section
        self.table_label = QLabel("Class Distribution Analysis")
        self.table_label.setStyleSheet(
            "color: #7f8c8d; font-size: 14px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px;"
        )
        self.main_layout.addWidget(self.table_label)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(
            ["Class Identity", "Count", "Dataset Coverage"]
        )

        header = self.table.horizontalHeader()
        if header:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            header.setStretchLastSection(True)

        v_header = self.table.verticalHeader()
        if v_header:
            v_header.setVisible(False)

        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QTableWidget { alternate-background-color: #222222; }"
        )

        self.main_layout.addWidget(self.table)

        # Bottom Actions
        self.button_box = QHBoxLayout()

        self.refresh_btn = QPushButton("↻ Refresh Intelligence")
        self.refresh_btn.setMinimumHeight(55)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.scan_and_refresh)

        self.close_btn = QPushButton("Dismiss")
        self.close_btn.setObjectName("CloseBtn")
        self.close_btn.setMinimumHeight(55)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close)

        self.button_box.addStretch()
        self.button_box.addWidget(self.refresh_btn)
        self.button_box.addWidget(self.close_btn)
        self.main_layout.addLayout(self.button_box)

    def load_statistics(self):
        if not self.db_session:
            return

        try:
            total_images = self.db_session.query(Image).count()
            total_annotations = self.db_session.query(Annotation).count()

            # Group by class
            results = (
                self.db_session.query(Class.name, func.count(Annotation.id))
                .join(Annotation, Class.id == Annotation.class_id)
                .group_by(Class.name)
                .order_by(func.count(Annotation.id).desc())
                .all()
            )

            self.card_images.update_value(total_images)
            self.card_annots.update_value(total_annotations)
            self.card_classes.update_value(len(results))

            self.table.setRowCount(len(results))
            for row, (class_name, count) in enumerate(results):
                name_item = QTableWidgetItem(class_name)
                name_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )

                count_item = QTableWidgetItem(str(count))
                count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                count_item.setForeground(QBrush(QColor("#2ecc71")))

                percent = (
                    (count / total_annotations * 100) if total_annotations > 0 else 0
                )
                percent_item = QTableWidgetItem(f"{percent:.1f}%")
                percent_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                self.table.setItem(row, 0, name_item)
                self.table.setItem(row, 1, count_item)
                self.table.setItem(row, 2, percent_item)

        except Exception as e:
            QMessageBox.critical(
                self, "Deep Insights Engine", f"Analytics platform error: {e}"
            )

    def scan_and_refresh(self):
        parent = self.parent()
        if parent:
            update_func = getattr(parent, "update_db_statistics", None)
            if callable(update_func):
                # Visual feedback
                self.refresh_btn.setEnabled(False)
                self.refresh_btn.setText("⏳ Processing...")
                self.refresh_btn.setStyleSheet(
                    "background-color: #2c3e50; color: #7f8c8d;"
                )
                QApplication.processEvents()

                self.statusBar_msg("Syncing project data...")
                update_func()
                self.load_statistics()

                # Feedback effects
                self.card_images.pulse()
                self.card_annots.pulse()
                self.card_classes.pulse()
                self.last_sync_label.setText(
                    f"Last update: {datetime.now().strftime('%H:%M:%S')}"
                )

                self.refresh_btn.setText("✅ Updated!")
                self.refresh_btn.setStyleSheet(
                    "background-color: #27ae60; color: white;"
                )
                self.statusBar_msg("Analytics updated successfully.")

                QTimer.singleShot(3000, self.reset_refresh_button)
            else:
                QMessageBox.warning(
                    self,
                    "Restricted Feature",
                    "Directory sync is not accessible from current context.",
                )

    def reset_refresh_button(self):
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("↻ Refresh Intelligence")
        self.refresh_btn.setStyleSheet("")

    def statusBar_msg(self, text):
        parent = self.parent()
        if parent and hasattr(parent, "statusBar"):
            sb = parent.statusBar()
            if sb:
                sb.showMessage(text, 5000)
        else:
            print(f"Stats Engine: {text}")
