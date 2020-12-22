# coding=utf-8
"""
Contains the worker classes/functions executed on the server side.
"""

import shlex
import time
import logging
import subprocess
from contextlib import contextmanager
from pylspclient import JsonRpcEndpoint, LspEndpoint, LspClient, lsp_structs
from pylspclient.lsp_structs import (
    TextDocumentItem,
    Position,
    CompletionContext,
    CompletionTriggerKind,
    CompletionItemKind,
    DiagnosticSeverity
)

client = None  # Set by start_language_server
langid = None  # Set by server
diagnostics = {}  # Set by on_publish_diagnostics
document_version = 0

WARNING = 1
ERROR = 2
ICON_PATH = ('path', ':/pyqode_python_icons/rc/path.png')
ICON_CLASS = ('code-class', ':/pyqode_python_icons/rc/class.png')
ICON_FUNC = ('code-function', ':/pyqode_python_icons/rc/func.png')
ICON_VAR = ('code-variable', ':/pyqode_python_icons/rc/var.png')
ICON_KEYWORD = ('quickopen', ':/pyqode_python_icons/rc/keyword.png')
ICONS = {
    CompletionItemKind.File: ICON_PATH,
    CompletionItemKind.Class: ICON_CLASS,
    CompletionItemKind.Function: ICON_FUNC,
    CompletionItemKind.Variable: ICON_VAR,
    CompletionItemKind.Keyword: ICON_KEYWORD,
}

CLIENT_CAPABILITIES = {
    'textDocument': {
        'completion': {
            'completionItem': {
                'commitCharactersSupport': True,
                'documentationFormat': ['markdown', 'plaintext'],
                'snippetSupport': True
            },
            'completionItemKind': {
                'valueSet': []
            },
            'contextSupport': True,
        },
        'documentSymbol': {
            'symbolKind': {
                'valueSet': []
            }
        },
        'publishDiagnostics': {
            'relatedInformation': True
        }
    }
}


def start_language_server(cmd):
    
    global client
    
    print('starting language server: "{}"'.format(cmd))
    server_process = subprocess.Popen(
        shlex.split(cmd),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    json_rpc_endpoint = JsonRpcEndpoint(
        server_process.stdin,
        server_process.stdout
    )
    endpoint = LspEndpoint(
        json_rpc_endpoint,
        notify_callbacks = {
            'textDocument/publishDiagnostics': on_publish_diagnostics
        }
    )
    client = LspClient(endpoint)
    server_capabilities = client.initialize(
        server_process.pid,
        None,
        None,
        None,
        CLIENT_CAPABILITIES,
        'off',
        None
    )
    client.initialized()
    print('language server started')


def open_document(request_data):
    
    code = request_data['code']
    path = request_data['path']
    print('opening document "{}"'.format(path))
    td = _text_document(path, code)
    client.didOpen(td)
    

def calltips(request_data):
    """Worker that returns a list of calltips.

    A calltips is a tuple made of the following parts:
      - module_name: name of the module of the function invoked
      - call_name: name of the function that is being called
      - params: the list of parameter names.
      - index: index of the current parameter
      - bracket_start

    :returns tuple(label, parameters, active_parameter, column)
    """
    code = request_data['code']
    line = request_data['line']
    column = request_data['column']
    path = request_data['path']
    logging.debug(request_data)
    td = _text_document(path, code)
    with _timer('signatures'):
        signatures = client.signatureHelp(td, Position(line, column))
    if not signatures.signatures:
        return ()
    signature = signatures.signatures[signatures.activeSignature]
    return (
        signature.label,
        [p.label for p in signature.parameters],
        signatures.activeParameter,
        column
    )


class CompletionProvider:
    """Provides code completion."""

    @staticmethod
    def complete(code, line, column, path, encoding, prefix):
        """
        :returns: a list of completions.
        """
        
        td = _text_document(path, code)
        with _timer('completions'):
            completions = client.completion(
                td,
                Position(line, column),
                CompletionContext(CompletionTriggerKind.Invoked)
            )
        ret_val = []
        for completion in completions.items:
            ret_val.append({
                'name': completion.label,
                'icon': ICONS.get(completion.kind, ICON_VAR),
                'tooltip': completion.detail
            })
        return ret_val
    
    
def on_publish_diagnostics(d):
    
    global diagnostics
    diagnostics = d


def run_diagnostics(request_data):
    
    global diagnostics
    diagnostics = {}
    code = request_data['code']
    path = request_data['path']
    td = _text_document(path, code)
    with _timer('diagnostics'):
        client.didOpen(td)
        while not diagnostics:
            time.sleep(0.1)
    d = diagnostics.get('diagnostics',[])
    ret_val = []
    for msg in d:
        ret_val.append((
            msg['message'],
            ERROR if msg['severity'] <= DiagnosticSeverity.Error else WARNING,
            msg['range']['start']['line']
        ))
    return ret_val


def _text_document(path, code):
    
    global document_version
    document_version += 1
    return TextDocumentItem('file://' + path, langid, document_version, code)
    

@contextmanager
def _timer(msg):
    
    t0 = time.time()
    yield
    t1 = time.time()
    print('{} ({:.0f} ms)'.format(msg, 1000 * (t1 - t0)))
