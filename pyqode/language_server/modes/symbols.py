# -*- coding: utf-8 -*-
"""
A mode that extracts document symbols (function defintions etc.)
"""
from libqtopensesame.misc.config import cfg
from pyqode.language_server.backend import workers
from pyqode.language_server.modes import LanguageServerMode


class SymbolsMode(LanguageServerMode):

    def request_symbols(self):
        
        return self.request(
            workers.symbols,
            {
                'code': self.editor.toPlainText().replace(u'\u2029', u'\n'),
                'path': self.editor.file.path,
                'kind': cfg.lsp_symbols_kind.split(';')
            }
        )
