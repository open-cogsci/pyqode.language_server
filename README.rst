.. image:: https://raw.githubusercontent.com/pyQode/pyQode/master/media/pyqode-banner.png


About
-----

This is a fork of PyQode, which is now developed as the editor component for Rapunzel_ and OpenSesame_. The original PyQode repository (<= v2) is no longer maintained.

*pyqode.language_server* adds **language server protocol (LSP_)** support to `pyQode`. The Language Server protocol is used between a tool (the client) and a language smartness provider (the server) to integrate features like auto complete, go to definition, find all references and alike into the tool

.. _LSP: https://langserver.org/
.. _OpenSesame: https://osdoc.cogsci.nl/
.. _Rapunzel: https://rapunzel.cogsci.nl/

Features:
---------

* calltips mode
* code completion
* diagnostics


License
-------

pyQode is licensed under the **MIT license**.

Requirements
------------

pyqode.language_server depends on the following libraries:

- _pylspclient

.. _pylspclient: https://github.com/yeger00/pylspclient
