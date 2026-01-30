from PyQt6.QtGui import QUndoCommand, QUndoStack
from PyQt6.QtCore import QObject
import json
from libs.database import UndoHistory


class UndoManager:
    def __init__(self, db_session=None):
        self.stack = QUndoStack()
        self.db_session = db_session

    def set_db_session(self, db_session):
        self.db_session = db_session

    def _log_to_db(self, action_type, details):
        if self.db_session:
            try:
                history = UndoHistory(
                    action_type=action_type, details=json.dumps(details)
                )
                self.db_session.add(history)
                self.db_session.commit()
            except Exception as e:
                print(f"Failed to log undo history: {e}")

    def push(self, command):
        print(f"UndoManager: Pushed command {command.text()}")
        self.stack.push(command)
        if hasattr(command, "to_data"):
            self._log_to_db(command.text(), command.to_data())

    def undo(self):
        print("UndoManager: Undo called")
        self.stack.undo()

    def redo(self):
        print("UndoManager: Redo called")
        self.stack.redo()

    def can_undo(self):
        return self.stack.canUndo()

    def can_redo(self):
        return self.stack.canRedo()

    def clear(self):
        self.stack.clear()


# Abstract Command Classes or Concrete Commands
# We can define them here or in a separate file.
# For simplicity, let's look at what actions we need.


class CreateShapeCommand(QUndoCommand):
    def __init__(self, canvas, shape):
        super().__init__()
        self.canvas = canvas
        self.shape = shape
        self.shape = shape
        self.setText(f"Create Shape {shape.label}")

    def to_data(self):
        return self.shape.to_data()

    def redo(self):
        # Initial create logic or restore shape
        if self.shape not in self.canvas.shapes:
            self.canvas.shapes.append(self.shape)
            self.canvas.repaint()

    def undo(self):
        if self.shape in self.canvas.shapes:
            self.canvas.shapes.remove(self.shape)
            self.canvas.repaint()
        # Also need to handle selection if it was selected


class DeleteShapeCommand(QUndoCommand):
    def __init__(self, canvas, shape):
        super().__init__()
        self.canvas = canvas
        self.shape = shape
        self.shape = shape
        self.setText(f"Delete Shape {shape.label}")

    def to_data(self):
        return self.shape.to_data()

    def redo(self):
        if self.shape in self.canvas.shapes:
            self.canvas.shapes.remove(self.shape)
            self.canvas.selected_shape = None
            self.canvas.repaint()

    def undo(self):
        if self.shape not in self.canvas.shapes:
            self.canvas.shapes.append(self.shape)
            self.canvas.repaint()


class EditLabelCommand(QUndoCommand):
    def __init__(self, shape, old_label, new_label):
        super().__init__()
        self.shape = shape
        self.old_label = old_label
        self.new_label = new_label
        self.setText(f"Change Label from {old_label} to {new_label}")

    def redo(self):
        self.shape.label = self.new_label
        # potentially update color?

    def undo(self):
        self.shape.label = self.old_label


class MoveShapeCommand(QUndoCommand):
    def __init__(self, canvas, shape, old_points, new_points):
        super().__init__()
        self.canvas = canvas
        self.shape = shape
        self.old_points = old_points
        self.new_points = new_points
        self.new_points = new_points
        self.setText("Move/Edit Shape")

    def to_data(self):
        return {
            "shape_uuid": self.shape.uuid,
            "old_points": [(p.x(), p.y()) for p in self.old_points],
            "new_points": [(p.x(), p.y()) for p in self.new_points],
        }

    def redo(self):
        self.shape.points = self.new_points
        self.canvas.repaint()

    def undo(self):
        self.shape.points = self.old_points
        self.canvas.repaint()
