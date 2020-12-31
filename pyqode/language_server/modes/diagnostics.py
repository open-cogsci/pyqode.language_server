# -*- coding: utf-8 -*-
"""
This module contains the LSP diagnostics checker mode
"""
from pyqode.core.modes import CheckerMode
from pyqode.qt.QtCore import Signal, QTimer
from pyqode.language_server.backend.workers import (
    run_diagnostics,
    poll_diagnostics
)


class DiagnosticsMode(CheckerMode):
    
    server_status_changed = Signal(int, int, dict)

    def __init__(self, show_diagnostics=True):
        """The show_diagnostics keyword determines whether the diagnostic
        messages are actually shown. If not, then the mode only does basic
        bookkeeping which is required for LSP support in general.
        """
        
        self._last_server_status = None
        self._show_diagnostics = show_diagnostics
        super().__init__(run_diagnostics, delay=1000)

    def _on_poll_result(self, results):
        
        if len(results) == 1 and results[0] is None:
            QTimer.singleShot(250, self._poll_messages)
            return
        super()._on_work_finished(results)
        
    def _poll_messages(self):

        self.editor.backend.send_request(
            poll_diagnostics,
            {'ignore_rules': self.ignore_rules},
            on_receive=self._on_poll_result
        )
        
    def _on_work_finished(self, results):
        
        # Check if the result is valid
        if not isinstance(results, dict) or 'server_status' not in results:
            return
        if results['server_status'] != self._last_server_status:
            self.server_status_changed.emit(
                results['server_status'],
                results['server_pid'],
                results['server_capabilities']
            )
            self._set_completion_triggers(results['server_capabilities'])
            self._last_server_status = results['server_status']
        if self._show_diagnostics:
            QTimer.singleShot(250, self._poll_messages)

    def _set_completion_triggers(self, capabilities):
        """If CodeCompletionMode is enabled, set the trigger symbols to the
        ones provided by the server, falling back to no trigger symbols.
        """
        
        if 'CodeCompletionMode' not in self.editor.modes.keys():
            return
        trigger_symbols = capabilities.get('capabilities', {}) \
            .get('completionProvider', {}) \
            .get('triggerCharacters', [])
        self.editor.modes.get(
            'CodeCompletionMode'
        ).trigger_symbols = trigger_symbols
