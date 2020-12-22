# coding=utf-8
"""
Gets calltips from the language server
"""
from pyqode.core.api import Mode
from pyqode.qt.QtWidgets import QToolTip
from pyqode.qt.QtCore import QObject, Qt, Signal, QPoint
from pyqode.language_server.backend import workers

HIDE_KEYS = (
        Qt.Key_ParenRight,
        Qt.Key_Return,
        Qt.Key_Left,
        Qt.Key_Right,
        Qt.Key_Up,
        Qt.Key_Down,
        Qt.Key_End,
        Qt.Key_Home,
        Qt.Key_PageDown,
        Qt.Key_PageUp,
        Qt.Key_Backspace,
        Qt.Key_Delete
)

SHOW_KEYS = (
    Qt.Key_ParenLeft,
    Qt.Key_Comma
)


class CalltipsMode(Mode, QObject):
    
    tooltip_display_requested = Signal(object, int)
    tooltip_hide_requested = Signal()

    def __init__(self):
        
        Mode.__init__(self)
        QObject.__init__(self)
        self.tooltip_display_requested.connect(self._display_tooltip)
        self.tooltip_hide_requested.connect(QToolTip.hideText)
        self._working = False

    def on_state_changed(self, state):
        
        if state:
            self.editor.key_released.connect(self._on_key_released)
        else:
            self.editor.key_released.disconnect(self._on_key_released)

    def _on_key_released(self, event):
        
        if event.key() not in SHOW_KEYS:
            if event.key() in HIDE_KEYS:
                QToolTip.hideText()
            return
        tc = self.editor.textCursor()
        self._request_calltip(
            self.editor.toPlainText().replace(u'\u2029', u'\n'),
            tc.blockNumber(),
            tc.columnNumber(),
            self.editor.file.path,
        )

    def _request_calltip(self, source, line, col, path):
        
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
        print(results)
        if not results:
            return
        call = {
            "call.label": results[0],
            "call.params": results[1],
            "call.index": results[2],
        }
        self.tooltip_display_requested.emit(call, results[3])

    def _display_tooltip(self, call, col):
        
        if not call:
            return
        calltip = "<p style='white-space:pre'>{}".format(call['call.label'])
        for i, param in enumerate(call['call.params']):
            if i < len(call['call.params']) - 1 and not param.endswith(','):
                param += ", "
            if param.endswith(','):
                param += ' '  # pep8 calltip
            if i == call['call.index']:
                calltip += "<b>"
            calltip += param
            if i == call['call.index']:
                calltip += "</b>"
        calltip += ')</p>'
        position = self.editor.mapToGlobal(
            self.editor.cursorRect().bottomLeft()
        )
        QToolTip.showText(position, calltip, self.editor)
