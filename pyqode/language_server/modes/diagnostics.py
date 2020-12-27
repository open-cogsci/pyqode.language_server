# -*- coding: utf-8 -*-
"""
This module contains the pyFlakes checker mode
"""
from pyqode.core.modes import CheckerMode
from pyqode.qt.QtCore import Signal
from pyqode.language_server.backend.workers import run_diagnostics


class DiagnosticsMode(CheckerMode):
    
    server_status_changed = Signal(int, int)

    def __init__(self):
        self._last_server_status = None
        super().__init__(run_diagnostics, delay=1000)

    def _on_work_finished(self, results):
        
        # Check if the result is valid
        if not isinstance(results, dict) or 'server_status' not in results:
            return
        if results['server_status'] != self._last_server_status:
            self.server_status_changed.emit(
                results['server_status'],
                results['server_pid']
            )
            self._last_server_status = results['server_status']
        super()._on_work_finished(results['messages'])
