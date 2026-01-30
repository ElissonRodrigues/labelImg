from PyQt6.QtGui import QColor, QCursor, QPixmap, QPainter, QBrush
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QPoint, QRectF, QLineF
from PyQt6.QtWidgets import QWidget, QMenu, QApplication


from libs.shape import Shape
from libs.utils import distance
from libs.undo_manager import CreateShapeCommand, DeleteShapeCommand, MoveShapeCommand

CURSOR_DEFAULT = Qt.CursorShape.ArrowCursor
CURSOR_POINT = Qt.CursorShape.PointingHandCursor
CURSOR_DRAW = Qt.CursorShape.CrossCursor
CURSOR_MOVE = Qt.CursorShape.ClosedHandCursor
CURSOR_GRAB = Qt.CursorShape.OpenHandCursor


class Canvas(QWidget):
    zoomRequest = pyqtSignal(int)
    lightRequest = pyqtSignal(int)
    scrollRequest = pyqtSignal(int, object, bool)
    newShape = pyqtSignal()
    selectionChanged = pyqtSignal(bool)
    shapeMoved = pyqtSignal()
    drawingPolygon = pyqtSignal(bool)

    CREATE, EDIT = list(range(2))

    epsilon = 24.0

    def __init__(self, *args, **kwargs):
        self.undo_manager = kwargs.pop("undo_manager", None)
        super().__init__(*args, **kwargs)
        # Initialise local state.
        self.mode = self.EDIT
        self.shapes = []
        self.current = None
        self.selected_shape = None  # save the selected shape here
        self.selected_shape_copy = None
        self.drawing_line_color = QColor(0, 0, 255)
        self.drawing_rect_color = QColor(0, 0, 255)
        self.line = Shape(line_color=self.drawing_line_color)
        self.prev_point = QPointF()
        self.offsets = QPointF(), QPointF()
        self.scale = 1.0
        self.overlay_color = None
        self.label_font_size = 8
        self.pixmap = QPixmap()
        self.visible = {}
        self._hide_background = False
        self.hide_background = False
        self.h_shape = None
        self.h_vertex = None
        self._painter = QPainter()
        self._cursor = CURSOR_DEFAULT
        # Menus:
        self.menus = (QMenu(), QMenu())
        self.prev_shape_points = []

        # Set widget options.
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self.verified = False
        self.draw_square = False

        # initialisation for panning
        self.pan_initial_pos = QPoint()

    def update_status_message(self, pos, current_width=None, current_height=None):
        window = getattr(self.parent(), "window", lambda: None)()
        if not window:
            return

        label_coordinates = getattr(window, "label_coordinates", None)
        if not label_coordinates:
            return

        if current_width is not None and current_height is not None:
            label_coordinates.setText(
                f"Width: {current_width:.0f}, Height: {current_height:.0f} / X: {pos.x():.0f}; Y: {pos.y():.0f}"
            )
        elif getattr(window, "file_path", None) is not None:
            label_coordinates.setText(f"X: {pos.x():.0f}; Y: {pos.y():.0f}")

    def set_drawing_color(self, qcolor):
        self.drawing_line_color = qcolor
        self.drawing_rect_color = qcolor

    def enterEvent(self, ev):
        self.override_cursor(self._cursor)

    def leaveEvent(self, ev):
        self.restore_cursor()

    def focusOutEvent(self, ev):
        self.restore_cursor()

    def isVisible(self, shape):
        return self.visible.get(shape, True)

    def drawing(self):
        return self.mode == self.CREATE

    def editing(self):
        return self.mode == self.EDIT

    def set_editing(self, value=True):
        self.mode = self.EDIT if value else self.CREATE
        if not value:  # Create
            self.un_highlight()
            self.de_select_shape()
            self.override_cursor(CURSOR_DRAW)
            # Set prev_point to current mouse position for immediate crosshair
            widget_pos = self.mapFromGlobal(QCursor.pos())
            self.prev_point = self.transform_pos(widget_pos)
        else:
            self.restore_cursor()
            self.prev_point = QPointF()
        self.repaint()

    def un_highlight(self, shape=None):
        if shape is None or shape == self.h_shape:
            if self.h_shape:
                self.h_shape.highlight_clear()
            self.h_vertex = self.h_shape = None

    def selected_vertex(self):
        return self.h_vertex is not None

    def mouseMoveEvent(self, ev):
        """Update line with last point and current coordinates."""
        pos = self.transform_pos(ev.position())

        # Update coordinates in status bar if image is opened
        self.update_status_message(pos)

        # Polygon drawing.
        if self.drawing():
            self.override_cursor(CURSOR_DRAW)
            if self.current:
                # Display annotation width and height while drawing
                current_width = abs(self.current[0].x() - pos.x())
                current_height = abs(self.current[0].y() - pos.y())

                parent = self.parent()
                label_coordinates = None
                if parent and hasattr(parent, "window") and parent.window():
                    label_coordinates = getattr(
                        parent.window(), "label_coordinates", None
                    )

                if label_coordinates:
                    label_coordinates.setText(
                        f"Width: {current_width:.0f}, Height: {current_height:.0f} / X: {pos.x():.0f}; Y: {pos.y():.0f}"
                    )

                color = self.drawing_line_color
                if self.out_of_pixmap(pos):
                    # Don't allow the user to draw outside the pixmap.
                    # Clip the coordinates to 0 or max,
                    # if they are outside the range [0, max]
                    size = self.pixmap.size()
                    clipped_x = min(max(0, pos.x()), size.width())
                    clipped_y = min(max(0, pos.y()), size.height())
                    pos = QPointF(clipped_x, clipped_y)
                elif len(self.current) > 1 and self.close_enough(pos, self.current[0]):
                    # Attract line to starting point and colorise to alert the
                    # user:
                    pos = self.current[0]
                    color = self.current.line_color
                    self.override_cursor(CURSOR_POINT)
                    self.current.highlight_vertex(0, Shape.NEAR_VERTEX)

                # Check if square mode is enabled (via toggle or holding Shift)
                modifiers = QApplication.keyboardModifiers()
                is_shift_pressed = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
                if self.draw_square or is_shift_pressed:
                    init_pos = self.current[0]
                    min_x = init_pos.x()
                    min_y = init_pos.y()
                    min_size = min(abs(pos.x() - min_x), abs(pos.y() - min_y))
                    direction_x = -1 if pos.x() - min_x < 0 else 1
                    direction_y = -1 if pos.y() - min_y < 0 else 1
                    self.line[1] = QPointF(
                        min_x + direction_x * min_size, min_y + direction_y * min_size
                    )
                else:
                    self.line[1] = pos

                self.line.line_color = color
                self.prev_point = QPointF()
                self.current.highlight_clear()
            else:
                self.prev_point = pos
            self.repaint()
            return

        # Polygon copy moving.
        if Qt.MouseButton.RightButton & ev.buttons():
            if self.selected_shape_copy and self.prev_point:
                self.override_cursor(CURSOR_MOVE)
                self.bounded_move_shape(self.selected_shape_copy, pos)
                self.repaint()
            elif self.selected_shape:
                self.selected_shape_copy = self.selected_shape.copy()
                self.repaint()
            return

        # Polygon/Vertex moving.
        if Qt.MouseButton.LeftButton & ev.buttons():
            if self.selected_vertex():
                self.bounded_move_vertex(pos)
                self.shapeMoved.emit()
                self.repaint()

                # Display annotation width and height while moving vertex
                point1 = self.h_shape[1]
                point3 = self.h_shape[3]
                current_width = abs(point1.x() - point3.x())
                current_height = abs(point1.y() - point3.y())

                label_coordinates = getattr(
                    self.parent().window(), "label_coordinates", None
                )
                if label_coordinates:
                    label_coordinates.setText(
                        f"Width: {current_width:.0f}, Height: {current_height:.0f} / X: {pos.x():.0f}; Y: {pos.y():.0f}"
                    )
            elif self.selected_shape and self.prev_point:
                self.override_cursor(CURSOR_MOVE)
                self.bounded_move_shape(self.selected_shape, pos)
                self.shapeMoved.emit()
                self.repaint()

                # Display annotation width and height while moving shape
                point1 = self.selected_shape[1]
                point3 = self.selected_shape[3]
                current_width = abs(point1.x() - point3.x())
                current_height = abs(point1.y() - point3.y())

                label_coordinates = getattr(
                    self.parent().window(), "label_coordinates", None
                )
                if label_coordinates:
                    label_coordinates.setText(
                        f"Width: {current_width:.0f}, Height: {current_height:.0f} / X: {pos.x():.0f}; Y: {pos.y():.0f}"
                    )
            else:
                # pan
                curr_pos = ev.globalPosition()
                delta = curr_pos - self.pan_initial_pos
                self.pan_initial_pos = curr_pos
                self.scrollRequest.emit(
                    int(delta.x()), Qt.Orientation.Horizontal, False
                )
                self.scrollRequest.emit(int(delta.y()), Qt.Orientation.Vertical, False)
                self.update()
            return

        # Just hovering over the canvas, 2 possibilities:
        # - Highlight shapes
        # - Highlight vertex
        # Update shape/vertex fill and tooltip value accordingly.
        self.setToolTip("Image")
        priority_list = self.shapes + (
            [self.selected_shape] if self.selected_shape else []
        )
        for shape in reversed([s for s in priority_list if self.isVisible(s)]):
            # Look for a nearby vertex to highlight. If that fails,
            # check if we happen to be inside a shape.
            index = shape.nearest_vertex(pos, self.epsilon)
            if index is not None:
                if self.selected_vertex():
                    self.h_shape.highlight_clear()
                self.h_vertex, self.h_shape = index, shape
                shape.highlight_vertex(index, shape.MOVE_VERTEX)
                self.override_cursor(CURSOR_POINT)
                self.setToolTip("Click & drag to move point")
                self.setStatusTip(self.toolTip())
                self.update()
                break
            elif shape.contains_point(pos):
                if self.selected_vertex():
                    self.h_shape.highlight_clear()
                self.h_vertex, self.h_shape = None, shape
                self.setToolTip(f"Click & drag to move shape '{shape.label}'")
                self.setStatusTip(self.toolTip())
                self.override_cursor(CURSOR_GRAB)
                self.update()

                # Display annotation width and height while hovering inside
                point1 = self.h_shape[1]
                point3 = self.h_shape[3]
                current_width = abs(point1.x() - point3.x())
                current_height = abs(point1.y() - point3.y())

                label_coordinates = getattr(
                    self.parent().window(), "label_coordinates", None
                )
                if label_coordinates:
                    label_coordinates.setText(
                        f"Width: {current_width:.0f}, Height: {current_height:.0f} / X: {pos.x():.0f}; Y: {pos.y():.0f}"
                    )
                break
        else:  # Nothing found, clear highlights, reset state.
            if self.h_shape:
                self.h_shape.highlight_clear()
                self.update()
            self.h_vertex, self.h_shape = None, None
            self.override_cursor(CURSOR_DEFAULT)

    def mousePressEvent(self, ev):
        pos = self.transform_pos(ev.position())

        if ev.button() == Qt.MouseButton.LeftButton:
            if self.drawing():
                self.handle_drawing(pos)
            else:
                selection = self.select_shape_point(pos)
                self.prev_point = pos

                if selection is None:
                    # pan
                    QApplication.setOverrideCursor(
                        QCursor(Qt.CursorShape.OpenHandCursor)
                    )
                    self.pan_initial_pos = ev.globalPosition()

        elif ev.button() == Qt.MouseButton.RightButton and self.editing():
            self.select_shape_point(pos)
            self.prev_point = pos

        if self.selected_shape:
            self.prev_shape_points = [p for p in self.selected_shape.points]

        self.update()

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.RightButton:
            menu = self.menus[bool(self.selected_shape_copy)]
            self.restore_cursor()
            if (
                not menu.exec(self.mapToGlobal(ev.position().toPoint()))
                and self.selected_shape_copy
            ):
                # Cancel the move by deleting the shadow copy.
                self.selected_shape_copy = None
                self.repaint()
        elif ev.button() == Qt.MouseButton.LeftButton and self.selected_shape:
            if self.selected_vertex():
                self.override_cursor(CURSOR_POINT)
            else:
                self.override_cursor(CURSOR_GRAB)

            if self.undo_manager and self.prev_shape_points and self.selected_shape:
                if self.prev_shape_points != self.selected_shape.points:
                    self.undo_manager.push(
                        MoveShapeCommand(
                            self,
                            self.selected_shape,
                            self.prev_shape_points,
                            self.selected_shape.points,
                        )
                    )

        elif ev.button() == Qt.MouseButton.LeftButton:
            pos = self.transform_pos(ev.position())
            if self.drawing():
                self.handle_drawing(pos)
            else:
                # pan
                QApplication.restoreOverrideCursor()

    def end_move(self, copy=False):
        if not self.selected_shape or not self.selected_shape_copy:
            return
        shape = self.selected_shape_copy
        # del shape.fill_color
        # del shape.line_color
        if copy:
            self.shapes.append(shape)
            self.selected_shape.selected = False
            self.selected_shape = shape
            self.repaint()
        else:
            self.selected_shape.points = [p for p in shape.points]
        self.selected_shape_copy = None

    def hide_background_shapes(self, value):
        self.hide_background = value
        if self.selected_shape:
            # Only hide other shapes if there is a current selection.
            # Otherwise the user will not be able to select a shape.
            self.set_hiding(True)
            self.repaint()

    def handle_drawing(self, pos):
        if self.current and self.current.reach_max_points() is False:
            init_pos = self.current[0]
            min_x = init_pos.x()
            min_y = init_pos.y()
            target_pos = self.line[1]
            max_x = target_pos.x()
            max_y = target_pos.y()
            self.current.add_point(QPointF(max_x, min_y))
            self.current.add_point(target_pos)
            self.current.add_point(QPointF(min_x, max_y))
            self.finalise()
        elif not self.out_of_pixmap(pos):
            self.current = Shape()
            self.current.add_point(pos)
            self.line.points = [pos, pos]
            self.set_hiding()
            self.drawingPolygon.emit(True)
            self.update()

    def set_hiding(self, enable=True):
        self._hide_background = self.hide_background if enable else False

    def can_close_shape(self):
        return self.drawing() and self.current and len(self.current) > 2

    def mouseDoubleClickEvent(self, ev):
        # We need at least 4 points here, since the mousePress handler
        # adds an extra one before this handler is called.
        if self.can_close_shape() and len(self.current) > 3:
            self.current.pop_point()
            self.finalise()

    def select_shape(self, shape):
        self.de_select_shape()
        shape.selected = True
        self.selected_shape = shape
        self.set_hiding()
        self.selectionChanged.emit(True)
        self.update()

    def select_shape_point(self, point):
        """Select the first shape created which contains this point."""
        self.de_select_shape()
        if self.selected_vertex():  # A vertex is marked for selection.
            index, shape = self.h_vertex, self.h_shape
            shape.highlight_vertex(index, shape.MOVE_VERTEX)
            self.select_shape(shape)
            return self.h_vertex
        for shape in reversed(self.shapes):
            if self.isVisible(shape) and shape.contains_point(point):
                self.select_shape(shape)
                self.calculate_offsets(shape, point)
                return self.selected_shape
        return None

    def calculate_offsets(self, shape, point):
        rect = shape.bounding_rect()
        x1 = rect.x() - point.x()
        y1 = rect.y() - point.y()
        x2 = (rect.x() + rect.width()) - point.x()
        y2 = (rect.y() + rect.height()) - point.y()
        self.offsets = QPointF(x1, y1), QPointF(x2, y2)

    def snap_point_to_canvas(self, x, y):
        """
        Moves a point x,y to within the boundaries of the canvas.
        :return: (x,y,snapped) where snapped is True if x or y were changed, False if not.
        """
        if x < 0 or x > self.pixmap.width() or y < 0 or y > self.pixmap.height():
            x = max(x, 0)
            y = max(y, 0)
            x = min(x, self.pixmap.width())
            y = min(y, self.pixmap.height())
            return x, y, True

        return x, y, False

    def bounded_move_vertex(self, pos):
        index, shape = self.h_vertex, self.h_shape
        point = shape[index]
        if self.out_of_pixmap(pos):
            size = self.pixmap.size()
            clipped_x = min(max(0, pos.x()), size.width())
            clipped_y = min(max(0, pos.y()), size.height())
            pos = QPointF(clipped_x, clipped_y)

        # Check if square mode is enabled (via toggle or holding Shift)
        modifiers = QApplication.keyboardModifiers()
        is_shift_pressed = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        if self.draw_square or is_shift_pressed:
            opposite_point_index = (index + 2) % 4
            opposite_point = shape[opposite_point_index]
            min_size = min(
                abs(pos.x() - opposite_point.x()), abs(pos.y() - opposite_point.y())
            )
            direction_x = -1 if pos.x() - opposite_point.x() < 0 else 1
            direction_y = -1 if pos.y() - opposite_point.y() < 0 else 1
            shift_pos = QPointF(
                opposite_point.x() + direction_x * min_size - point.x(),
                opposite_point.y() + direction_y * min_size - point.y(),
            )
        else:
            shift_pos = pos - point

        shape.move_vertex_by(index, shift_pos)

        left_index = (index + 1) % 4
        right_index = (index + 3) % 4
        left_shift = None
        right_shift = None
        if index % 2 == 0:
            right_shift = QPointF(shift_pos.x(), 0)
            left_shift = QPointF(0, shift_pos.y())
        else:
            left_shift = QPointF(shift_pos.x(), 0)
            right_shift = QPointF(0, shift_pos.y())
        shape.move_vertex_by(right_index, right_shift)
        shape.move_vertex_by(left_index, left_shift)

    def bounded_move_shape(self, shape, pos):
        if self.out_of_pixmap(pos):
            return False  # No need to move
        o1 = pos + self.offsets[0]
        if self.out_of_pixmap(o1):
            pos -= QPointF(min(0, o1.x()), min(0, o1.y()))

        o2 = pos + self.offsets[1]
        if self.out_of_pixmap(o2):
            pos += QPointF(
                min(0, self.pixmap.width() - o2.x()),
                min(0, self.pixmap.height() - o2.y()),
            )
        # The next line tracks the new position of the cursor
        # relative to the shape, but also results in making it
        # a bit "shaky" when nearing the border and allows it to
        # go outside of the shape's area for some reason. XXX
        # self.calculateOffsets(self.selectedShape, pos)
        dp = pos - self.prev_point
        if dp:
            shape.move_by(dp)
            self.prev_point = pos
            return True
        return False

    def de_select_shape(self):
        if self.selected_shape:
            self.selected_shape.selected = False
            self.selected_shape = None
            self.set_hiding(False)
            self.selectionChanged.emit(False)
            self.update()

    def delete_selected(self):
        if self.selected_shape:
            shape = self.selected_shape
            self.un_highlight(shape)
            if self.undo_manager:
                self.undo_manager.push(DeleteShapeCommand(self, shape))
            elif self.selected_shape in self.shapes:
                self.shapes.remove(self.selected_shape)
            self.selected_shape = None
            self.update()
            return shape

    def copy_selected_shape(self):
        if self.selected_shape:
            shape = self.selected_shape.copy()
            self.de_select_shape()
            self.shapes.append(shape)
            shape.selected = True
            self.selected_shape = shape
            self.bounded_shift_shape(shape)
            return shape

    def bounded_shift_shape(self, shape):
        # Try to move in one direction, and if it fails in another.
        # Give up if both fail.
        point = shape[0]
        offset = QPointF(2.0, 2.0)
        self.calculate_offsets(shape, point)
        self.prev_point = point
        if not self.bounded_move_shape(shape, point - offset):
            self.bounded_move_shape(shape, point + offset)

    def paintEvent(self, event):
        if not self.pixmap:
            return super().paintEvent(event)

        p = self._painter
        p.begin(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        p.scale(self.scale, self.scale)
        p.translate(self.offset_to_center())

        temp = self.pixmap
        if self.overlay_color:
            temp = QPixmap(self.pixmap)
            painter = QPainter(temp)
            painter.setCompositionMode(painter.CompositionMode_Overlay)
            painter.fillRect(temp.rect(), self.overlay_color)
            painter.end()

        p.drawPixmap(0, 0, temp)
        Shape.scale = self.scale
        Shape.label_font_size = self.label_font_size
        for shape in self.shapes:
            if (shape.selected or not self._hide_background) and self.isVisible(shape):
                shape.fill = shape.selected or shape == self.h_shape
                shape.paint(p)
        if self.current:
            self.current.paint(p)
            self.line.paint(p)
        if self.selected_shape_copy:
            self.selected_shape_copy.paint(p)

        # Paint rect
        if self.current is not None and len(self.line) == 2:
            left_top = self.line[0]
            right_bottom = self.line[1]
            p.setPen(self.drawing_rect_color)
            brush = QBrush(Qt.BrushStyle.BDiagPattern)
            p.setBrush(brush)
            p.drawRect(QRectF(left_top, right_bottom))

        if (
            self.drawing()
            and not self.prev_point.isNull()
            and not self.out_of_pixmap(self.prev_point)
        ):
            p.setPen(QColor(0, 0, 0))
            p.drawLine(
                QLineF(
                    self.prev_point.x(), 0, self.prev_point.x(), self.pixmap.height()
                )
            )
            p.drawLine(
                QLineF(0, self.prev_point.y(), self.pixmap.width(), self.prev_point.y())
            )

        self.setAutoFillBackground(True)
        if self.verified:
            pal = self.palette()
            pal.setColor(self.backgroundRole(), QColor(184, 239, 38, 128))
            self.setPalette(pal)
        else:
            pal = self.palette()
            pal.setColor(self.backgroundRole(), QColor(232, 232, 232, 255))
            self.setPalette(pal)

        p.end()

    def transform_pos(self, point):
        """Convert from widget-logical coordinates to painter-logical coordinates."""
        return QPointF(point) / self.scale - self.offset_to_center()

    def offset_to_center(self):
        s = self.scale
        area = super().size()
        w, h = self.pixmap.width() * s, self.pixmap.height() * s
        aw, ah = area.width(), area.height()
        x = (aw - w) / (2 * s) if aw > w else 0
        y = (ah - h) / (2 * s) if ah > h else 0
        return QPointF(x, y)

    def out_of_pixmap(self, p):
        w, h = self.pixmap.width(), self.pixmap.height()
        return not (0 <= p.x() <= w and 0 <= p.y() <= h)

    def finalise(self):
        if not self.current:
            return
        if self.current.points[0] == self.current.points[-1]:
            self.current = None
            self.drawingPolygon.emit(False)
            self.update()
            return

        self.current.close()
        if self.undo_manager:
            self.undo_manager.push(CreateShapeCommand(self, self.current))
        else:
            self.shapes.append(self.current)
        self.current = None
        self.set_hiding(False)
        self.newShape.emit()
        self.update()

    def close_enough(self, p1, p2):
        return distance(p1 - p2) < self.epsilon

    # These two, along with a call to adjustSize are required for the
    # scroll area.
    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        if self.pixmap:
            return self.scale * self.pixmap.size()
        return super().minimumSizeHint()

    def wheelEvent(self, ev):
        delta = ev.angleDelta()
        h_delta = delta.x()
        v_delta = delta.y()

        mods = ev.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)

        if ctrl and shift and v_delta:
            self.lightRequest.emit(v_delta)
        elif ctrl and v_delta:
            self.zoomRequest.emit(v_delta)
        else:
            if v_delta:
                self.scrollRequest.emit(v_delta, Qt.Orientation.Vertical, True)
            if h_delta:
                self.scrollRequest.emit(h_delta, Qt.Orientation.Horizontal, True)
        ev.accept()

    def keyPressEvent(self, ev):
        key = ev.key()
        if self.current:
            if key == Qt.Key.Key_Escape:
                self.current = None
                self.drawingPolygon.emit(False)
                self.update()
            elif key == Qt.Key.Key_Return and self.can_close_shape():
                self.finalise()
            return

        match key:
            case Qt.Key.Key_Escape if not self.editing():
                self.drawingPolygon.emit(False)
                self.update()
            case Qt.Key.Key_Left if self.selected_shape:
                self.move_one_pixel("Left")
            case Qt.Key.Key_Right if self.selected_shape:
                self.move_one_pixel("Right")
            case Qt.Key.Key_Up if self.selected_shape:
                self.move_one_pixel("Up")
            case Qt.Key.Key_Down if self.selected_shape:
                self.move_one_pixel("Down")
            case _:
                super().keyPressEvent(ev)

    def move_one_pixel(self, direction):
        if not self.selected_shape:
            return

        step = None
        match direction:
            case "Left" if not self.move_out_of_bound(s := QPointF(-1.0, 0)):
                step = s
            case "Right" if not self.move_out_of_bound(s := QPointF(1.0, 0)):
                step = s
            case "Up" if not self.move_out_of_bound(s := QPointF(0, -1.0)):
                step = s
            case "Down" if not self.move_out_of_bound(s := QPointF(0, 1.0)):
                step = s

        if step:
            for i, _ in enumerate(self.selected_shape.points):
                self.selected_shape.points[i] += step
            self.shapeMoved.emit()
            self.repaint()

    def move_out_of_bound(self, step):
        if not self.selected_shape:
            return True
        return any(self.out_of_pixmap(p + step) for p in self.selected_shape.points)

    def set_last_label(self, text, line_color=None, fill_color=None):
        if not text:
            return None
        self.shapes[-1].label = text
        if line_color:
            self.shapes[-1].line_color = line_color

        if fill_color:
            self.shapes[-1].fill_color = fill_color

        return self.shapes[-1]

    def undo_last_line(self):
        if not self.shapes:
            return
        self.current = self.shapes.pop()
        self.current.set_open()
        self.line.points = [self.current[-1], self.current[0]]
        self.drawingPolygon.emit(True)

    def reset_all_lines(self):
        if not self.shapes:
            return
        self.current = self.shapes.pop()
        self.current.set_open()
        self.line.points = [self.current[-1], self.current[0]]
        self.drawingPolygon.emit(True)
        self.current = None
        self.drawingPolygon.emit(False)
        self.update()

    def load_pixmap(self, pixmap):
        self.pixmap = pixmap
        self.shapes = []
        self.repaint()

    def load_shapes(self, shapes):
        self.shapes = list(shapes)
        self.selected_shape = None
        self.current = None
        self.repaint()

    def set_shape_visible(self, shape, value):
        self.visible[shape] = value
        self.repaint()

    def current_cursor(self):
        cursor = QApplication.overrideCursor()
        if cursor is not None:
            cursor = cursor.shape()
        return cursor

    def override_cursor(self, cursor):
        self._cursor = cursor
        if self.current_cursor() is None:
            QApplication.setOverrideCursor(cursor)
        else:
            QApplication.changeOverrideCursor(cursor)

    def restore_cursor(self):
        QApplication.restoreOverrideCursor()

    def reset_state(self):
        self.de_select_shape()
        self.un_highlight()
        self.selected_shape_copy = None

        self.restore_cursor()
        self.pixmap = None
        self.update()

    def set_drawing_shape_to_square(self, status):
        self.draw_square = status
