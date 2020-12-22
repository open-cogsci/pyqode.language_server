# -*- coding: utf-8 -*-
"""
This package contains a series of python specific modes (calltips,
autoindent, code linting,...).

"""
from .calltips import CalltipsMode
from .diagnostics import DiagnosticsMode


__all__ = ['CalltipsMode', 'DiagnosticsMode']
