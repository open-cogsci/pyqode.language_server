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
SERVER_NOT_STARTED = 0
SERVER_RUNNING = 1
SERVER_ERROR = 2

client = None  # Set by start_language_server
server_status = SERVER_NOT_STARTED
langid = None  # Set by server
server_process = None
server_cmd = None
diagnostics = {}  # Set by on_publish_diagnostics
document_version = 0


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
    
    global client, server_process, server_cmd, server_status
    
    print('starting language server: "{}"'.format(cmd))
    try:
        server_process = subprocess.Popen(
            shlex.split(cmd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except FileNotFoundError:
        server_status = SERVER_ERROR
        return
    server_status = SERVER_RUNNING
    json_rpc_endpoint = JsonRpcEndpoint(
        server_process.stdin,
        server_process.stdout
    )
    endpoint = LspEndpoint(
        json_rpc_endpoint,
        notify_callbacks={
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
    server_cmd = cmd
    print('language server started')


def restart_language_server():
    
    global client, server_status
    print('killing language server')
    client = None
    server_process.kill()
    if not server_process.wait(timeout=5):
        print('failed to kill language server')
    server_status = SERVER_NOT_STARTED
    start_language_server(server_cmd)


def open_document(request_data):

    if server_status != SERVER_RUNNING:
        return
    code = request_data['code']
    path = request_data['path']
    print('opening document "{}"'.format(path))
    td = _text_document(path, code)
    client.didOpen(td)


def calltips(request_data):

    if server_status != SERVER_RUNNING:
        return ()
    code = request_data['code']
    line = request_data['line']
    column = request_data['column']
    path = request_data['path']
    logging.debug(request_data)
    td = _text_document(path, code)
    signatures = _run_command(
        'signatures',
        client.signatureHelp,
        (td, Position(line, column))
    )
    if signatures is None or not signatures.signatures:
        return ()
    signature = signatures.signatures[signatures.activeSignature]
    return (
        signature.label,
        [p.label for p in signature.parameters],
        signatures.activeParameter,
        column
    )


def symbols(request_data):
    
    if server_status != SERVER_RUNNING:
        return []
    code = request_data['code']
    path = request_data['path']
    symbol_kind = request_data['kind']
    td = _text_document(path, code)
    symbols = _run_command(
        'symbols',
        client.documentSymbol,
        (td,)
    )
    if symbols is None:
        return []
    return [
        (s.name, s.kind.name, s.location.range.start.line, s.containerName)
        for s in symbols
        if s.kind.name in symbol_kind
    ]


class CompletionProvider:
    """Provides code completion."""

    @staticmethod
    def complete(code, line, column, path, encoding, prefix):
        """
        :returns: a list of completions.
        """
        
        td = _text_document(path, code)
        completions = _run_command(
            'completions',
            client.completion,
            (
                td,
                Position(line, column),
                CompletionContext(CompletionTriggerKind.Invoked)
            )
        )
        if completions is None:
            return []
        ret_val = []
        for completion in completions.items:
            # The label tends to include parentheses etc., and that's why it's
            # better to use insertText when available.
            text = completion.insertText
            if not text:
                text = completion.label
            ret_val.append({
                'name': text,
                'icon': ICONS.get(completion.kind, ICON_VAR),
                'tooltip': completion.detail
            })
        print('completion() gave {} suggestions'.format(len(ret_val)))
        return ret_val
    
    
def on_publish_diagnostics(d):
    
    global diagnostics
    diagnostics = d


def run_diagnostics(request_data):
    
    if server_status != SERVER_RUNNING:
        return [server_status]
    global diagnostics
    diagnostics = {}
    code = request_data['code']
    path = request_data['path']
    ignore_rules = request_data['ignore_rules']
    td = _text_document(path, code)
    with _timer('diagnostics'):
        client.didOpen(td)
        for _ in range(20):
            if diagnostics:
                break
            time.sleep(0.1)
        else:
            print('run_diagnostics() timed out')
            return []
    d = diagnostics.get('diagnostics', [])
    ret_val = [server_status]
    for msg in d:
        if any(msg['message'].startswith(ir) for ir in ignore_rules):
            continue
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


def _run_command(name, fnc, args):
    
    with _timer(name):
        try:
            ret_val = fnc(*args)
        except lsp_structs.ResponseError as e:
            print('{}() gave ResponseError'.format(name))
            print(e)
            ret_val = None
        except TimeoutError:
            print('{}() gave TimeoutError'.format(name))
            restart_language_server()
            ret_val = None
    return ret_val
