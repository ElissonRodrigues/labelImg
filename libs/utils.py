from math import sqrt
import hashlib
import re
import sys

from PyQt6.QtGui import QIcon, QAction, QRegularExpressionValidator, QColor
from PyQt6.QtCore import QRegularExpression
from PyQt6.QtWidgets import QPushButton, QMenu


def new_icon(icon):
    return QIcon(f":/{icon}")


def new_button(text, icon=None, slot=None):
    b = QPushButton(text)
    if icon is not None:
        b.setIcon(new_icon(icon))
    if slot is not None:
        b.clicked.connect(slot)
    return b


def new_action(
    parent,
    text,
    slot=None,
    shortcut=None,
    icon=None,
    tip=None,
    checkable=False,
    enabled=True,
):
    """Create a new action and assign callbacks, shortcuts, etc."""
    a = QAction(text, parent)
    if icon is not None:
        a.setIcon(new_icon(icon))
    if shortcut is not None:
        if isinstance(shortcut, (list, tuple)):
            a.setShortcuts(shortcut)
        else:
            a.setShortcut(shortcut)
    if tip is not None:
        a.setToolTip(tip)
        a.setStatusTip(tip)
    if slot is not None:
        a.triggered.connect(slot)
    if checkable:
        a.setCheckable(True)
    a.setEnabled(enabled)
    return a


def add_actions(widget, actions):
    for action in actions:
        if action is None:
            widget.addSeparator()
        elif isinstance(action, QMenu):
            widget.addMenu(action)
        else:
            widget.addAction(action)


def label_validator():
    return QRegularExpressionValidator(QRegularExpression(r"^[^ \t].+"), None)


class Struct(object):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def distance(p):
    return sqrt(p.x() * p.x() + p.y() * p.y())


def format_shortcut(text):
    mod, key = text.split("+", 1)
    return f"<b>{mod}</b>+<b>{key}</b>"


def generate_color_by_text(text):
    s = text
    hash_code = int(hashlib.sha256(s.encode("utf-8")).hexdigest(), 16)
    r = int((hash_code / 255) % 255)
    g = int((hash_code / 65025) % 255)
    b = int((hash_code / 16581375) % 255)
    return QColor(r, g, b, 100)


def natural_sort(list, key=lambda s: s):
    """
    Sort the list into natural alphanumeric order.
    """

    def get_alphanum_key_func(key):
        convert = lambda text: int(text) if text.isdigit() else text
        return lambda s: [convert(c) for c in re.split("([0-9]+)", key(s))]

    sort_key = get_alphanum_key_func(key)
    list.sort(key=sort_key)


def trimmed(text):
    return text.strip()
