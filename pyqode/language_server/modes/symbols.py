# -*- coding: utf-8 -*-
"""
A mode that extracts document symbols (function defintions etc.)
"""
from pyqode.language_server.backend import workers
from pyqode.language_server.modes import LanguageServerMode


class SymbolsMode(LanguageServerMode):
    
    def __init__(self, symbols_kind):
        
        super().__init__()
        self._symbols_kind = symbols_kind

    def request_symbols(self):
        
        return self.request(
            workers.symbols,
            {
                'code': self.editor.toPlainText().replace(u'\u2029', u'\n'),
                'path': self.editor.file.path,
                'kind': self._symbols_kind
            }
        )
