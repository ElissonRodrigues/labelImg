#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import QListWidgetItem


# PyQt6: TypeError: unhashable type: 'QListWidgetItem'


class HashableQListWidgetItem(QListWidgetItem):

    def __init__(self, *args):
        super().__init__(*args)

    def __hash__(self):
        return hash(id(self))
