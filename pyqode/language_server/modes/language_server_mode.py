# coding=utf-8
"""
A base class for language-server modes.
"""
import time
from pyqode.core.api import Mode
from pyqode.qt import QtCore


REQUEST_TIMEOUT = 5


class LanguageServerMode(Mode):

    def request(self, worker, request_data):
        
        self._results = None
        self.editor.backend.send_request(
            worker,
            request_data,
            on_receive=self._on_results_available
        )
        start_time = time.time()
        while time.time() - start_time < REQUEST_TIMEOUT:
            if self._results is not None:
                break
            QtCore.QCoreApplication.processEvents()
        else:
            return []
        return self._results
        
    def _on_results_available(self, results):
        
        self._results = results
