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
project_folders = None
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


def start_language_server(cmd, folders):
    
    global client, server_process, server_cmd, server_status, project_folders
    
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
    project_folders = _path_to_uri(folders)
    try:
        client.initialize(
            processId=server_process.pid,
            rootPath=None,
            rootUri=project_folders[0],
            initializationOptions=None,
            capabilities=CLIENT_CAPABILITIES,
            trace='off',
            workspaceFolders=project_folders
        )
    except lsp_structs.ResponseError as e:
        print('failed to initialize language server: {}'.format(e))
        server_status = SERVER_ERROR
        return
    client.initialized()
    server_cmd = cmd
    print('project_folders {}'.format(project_folders))
    print('language server started')


def restart_language_server():
    
    global client, server_status
    print('killing language server')
    client = None
    server_process.kill()
    if not server_process.wait(timeout=5):
        print('failed to kill language server')
    server_status = SERVER_NOT_STARTED
    start_language_server(server_cmd, project_folders)


def open_document(request_data):

    if server_status != SERVER_RUNNING:
        return
    code = request_data['code']
    path = request_data['path']
    print('opening document "{}"'.format(path))
    td = _text_document(path, code)
    client.didOpen(td)


def change_project_folders(request_data):
    
    if server_status != SERVER_RUNNING:
        return
    folders = request_data['folders']
    print('changing workspace folders: {}'.format(folders))
    

def calltips(request_data):

    if server_status != SERVER_RUNNING:
        return ()
    code = request_data['code']
    line = request_data['line']
    column = request_data['column']
    path = request_data['path']
    logging.debug(request_data)
    td = _text_document(path, code)
    # It appears that pyls returns an empty signature unless a didOpen is sent
    # to the server. Therefore we first try to get signatures once, and then if
    # this fails, try again but this time after sending a didOpen.
    for attempt in range(2):
        signatures = _run_command(
            'signatures(attempt={}, line={}, column={})'.format(
                attempt,
                line,
                column
            ),
            client.signatureHelp,
            (td, Position(line, column))
        )
        if signatures is not None and signatures.signatures:
            break
        client.didOpen(td)
    else:
        return ()
    signature = signatures.signatures[signatures.activeSignature]
    return (
        signature.label,
        [p.label for p in signature.parameters],
        signature.documentation,
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
        
        column += len(prefix)  # Go to the cursor position
        td = _text_document(path, code)
        completions = _run_command(
            'completions(line={}, col={})'.format(line, column),
            client.completion,
            (
                td,
                Position(line, column),
                CompletionContext(CompletionTriggerKind.Invoked)
            )
        )
        if completions is None:
            return []
        # It appears that the TypeScript server returns the items directly as
        # a list, whereas other servers return the items as a property.
        if hasattr(completions, 'items'):
            completions = completions.items
        ret_val = []
        for completion in completions:
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
    ret_val = {
        'server_status': server_status,
        'server_pid': server_process.pid,
        'messages': []
    }
    with _timer('diagnostics'):
        client.didOpen(td)
        for _ in range(20):
            if diagnostics:
                break
            time.sleep(0.1)
        else:
            print('run_diagnostics() timed out')
            return ret_val
    d = diagnostics.get('diagnostics', [])
    for msg in d:
        if any(msg['message'].startswith(ir) for ir in ignore_rules):
            continue
        ret_val['messages'].append((
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
        except lsp_structs.ResponseError:
            print('{}() gave ResponseError'.format(name))
            ret_val = None
        except TimeoutError:
            print('{}() gave TimeoutError'.format(name))
            restart_language_server()
            ret_val = None
    return ret_val


def _path_to_uri(paths, prefix='file://'):
    
    return [prefix + path for path in paths]
