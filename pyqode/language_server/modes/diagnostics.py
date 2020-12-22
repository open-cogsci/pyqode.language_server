# -*- coding: utf-8 -*-
"""
This module contains the pyFlakes checker mode
"""
from pyqode.core.modes import CheckerMode
from pyqode.language_server.backend.workers import run_diagnostics


class DiagnosticsMode(CheckerMode):

    def __init__(self):
        super().__init__(run_diagnostics, delay=1000)
