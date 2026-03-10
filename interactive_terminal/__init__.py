"""InteractiveTerminal - MCP Server for interactive terminal sessions."""

__version__ = "1.2.6"
VERSION = __version__

from .server import main, TerminalSession, TerminalManager

__all__ = ["main", "TerminalSession", "TerminalManager", "VERSION", "__version__"]
