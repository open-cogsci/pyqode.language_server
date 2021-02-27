# coding=utf-8
"""
Gets calltips from the language server
"""
from pyqode.qt.QtWidgets import QToolTip
from pyqode.qt.QtCore import QObject, Qt, Signal
from pyqode.core.modes import CalltipsMode as CoreCalltipsMode
from pyqode.language_server.backend import workers
from pyqode.language_server.modes import LanguageServerMode


class CalltipsMode(LanguageServerMode, CoreCalltipsMode):
    
    def __init__(self):
        LanguageServerMode.__init__(self)
        CoreCalltipsMode.__init__(self)
        self._working = False

    def _request_calltip(self, source, line, col, path, encoding):
        if self._working:
            return
        self._working = True
        self.editor.backend.send_request(
            workers.calltips,
            {
                'code': source,
                'line': line,
                'column': col,
                'path': path,
            },
            on_receive=self._on_results_available
        )
    
    def _on_results_available(self, results):
        self._working = False
        if not results:
            return
        call = {
            "call.module.name": None,
            "call.call_name": results[0],
            "call.params": results[1],
            "call.index": results[3],
            "call.bracket_start": (None, results[4]),
            "call.doc": results[2],
        }
        self.tooltipDisplayRequested.emit(call, results[4])
