# coding=utf-8
"""
Contains the worker classes/functions executed on the server side.
"""

import shlex
import time
import logging
import subprocess
import difflib
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
MAX_COMPLETIONS = 10  # Limit the number of completion suggestions
RESPONSE_TIMEOUT = 5  # Restart server if no response is received after timeout
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
    """Starts the language server and waits for initialization to complete."""
    
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
        },
        timeout=RESPONSE_TIMEOUT
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
    """Kills a running language server and restarts it."""
    
    global client, server_status
    print('killing language server')
    client = None
    server_process.kill()
    if not server_process.wait(timeout=5):
        print('failed to kill language server')
    server_status = SERVER_NOT_STARTED
    start_language_server(server_cmd, project_folders)


def change_project_folders(request_data):
    """Changes the project folders. Currently not implemented in pylsp."""
    
    if server_status != SERVER_RUNNING:
        return
    folders = request_data['folders']
    print('changing workspace folders: {}'.format(folders))
    

def calltips(request_data):
    """Requests calltips (signatures) from the server."""

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
        try:
            signatures = _run_command(
                'signatures(attempt={}, line={}, column={})'.format(
                    attempt,
                    line,
                    column
                ),
                client.signatureHelp,
                (td, Position(line, column))
            )
        except TypeError:
            # The TypeScript server tends to give TypeErrors on the first try
            print('signatures gave TypeError')
        else:
            if signatures is not None and signatures.signatures:
                break
        client.didOpen(td)
    else:
        return ()
    signature = signatures.signatures[signatures.activeSignature]
    # Some servers give a documentation string directly, others a dict with a
    # value and a format.
    if isinstance(signature.documentation, dict):
        if 'value' in signature.documentation:
            signature.documentation = signature.documentation['value']
        else:
            signature.documentation = ''
    return (
        signature.label,
        [p.label for p in signature.parameters],
        signature.documentation,
        signatures.activeParameter,
        column
    )


def symbols(request_data):
    """Requests document symbols from the server."""
    
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
    
    
class CompletionMatch(str):
    """Allows a full completion item to be processed by difflib by behaving as
    a string.
    """
    
    tooltip = None
    icon = None
    
    def to_dict(self):
        
        return {'name': self, 'icon': self.icon, 'tooltip': self.tooltip}
        
    @classmethod
    def from_completion(cls, completion):

        # The label tends to include parentheses etc., and that's why it's
        # better to use insertText when available.
        text = completion.insertText
        if not text:
            text = completion.label
        completion_match = cls(text)
        completion_match.icon = ICONS.get(completion.kind, ICON_VAR)
        completion_match.tooltip = completion.detail
        return completion_match


class CompletionProvider:
    """Provides a completer function. The rest of the worker is implemented in
    pyqode.core.
    """

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
        # The CompletionMatch class behaves as a string, but also remembers
        # the tooltip and icon of a completion. We use difflib to get the best
        # matching completions, and then return these as a list of dicts.
        matches = difflib.get_close_matches(
            prefix,
            possibilities=set(
                CompletionMatch.from_completion(completion)
                for completion in completions
            ),
            n=MAX_COMPLETIONS,
            cutoff=0
        )
        print('completion() gave {} suggestions'.format(len(matches)))
        return [match.to_dict() for match in matches]
    
    
def on_publish_diagnostics(d):
    """Is called by the server when diagnostic info is available."""
    
    global diagnostics
    diagnostics = d


def run_diagnostics(request_data):
    """Sends a didOpen to the server to start a diagnostic check. Immediately
    returns information about the server status, but the actual diagnostics
    messages are returned by poll_diagnostics() to avoid diagnostics from
    blocking the server.
    """
    
    global diagnostics
    if server_status != SERVER_RUNNING:
        return [server_status]
    diagnostics = {}
    code = request_data['code']
    path = request_data['path']
    client.didOpen(_text_document(path, code))
    return {
        'server_status': server_status,
        'server_pid': server_process.pid,
    }


def poll_diagnostics(request_data):
    """Returns diagnostic messages if they are available."""
    
    if not diagnostics:
        return [None]
    ignore_rules = request_data['ignore_rules']
    d = diagnostics.get('diagnostics', [])
    ret_val = []
    for msg in d:
        if any(msg['message'].startswith(ir) for ir in ignore_rules):
            continue
        ret_val.append((
            msg['message'],
            ERROR if msg['severity'] <= DiagnosticSeverity.Error else WARNING,
            msg['range']['start']['line']
        ))
    print('{} diagnostic messages'.format(len(ret_val)))
    return ret_val


def _text_document(path, code):
    
    global document_version
    document_version += 1
    return TextDocumentItem('file://' + path, langid, document_version, code)
    

@contextmanager
def _timer(msg):
    
    print('starting {}'.format(msg))
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
    
    return [
        path if path.startswith(prefix) else prefix + path
        for path in paths
    ]
