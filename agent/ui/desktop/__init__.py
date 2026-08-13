"""JCodex desktop workbench package.

Layout:
- constants.py   pure constants and derived paths
- runtime.py     shared mutable process state (single owner)
- helpers.py     pure helper functions
- executor.py    per-conversation task executor + run context
- pipeline.py    graph runs, sub-agents, rollback, task lifecycle
- rpc_*.py       eel-exposed endpoint groups by domain
- main.py        orchestration, re-exports and server bootstrap
"""
