#!/usr/bin/env python3
"""
InteractiveTerminal MCP Server

An MCP (Model Context Protocol) server providing fully interactive terminal sessions.

This server enables AI agents to:
- Create and manage multiple terminal sessions
- Send text and special keys (arrows, Ctrl, Alt, function keys)
- Control TUI applications (nano, htop, vim, less, etc.)
- Start long-running processes and check results later
- Navigate menus and interactive command-line interfaces

Cross-platform: Uses pywinpty on Windows, ptyprocess on Linux/Mac.
"""

import os
import sys
import time
import json
import logging
import urllib.request
import urllib.error
import threading
import re
import select
# fcntl is Unix-only - imported conditionally below
from typing import Dict, Optional, List, Any
from mcp.server.fastmcp import FastMCP

# Platform detection
import platform

# Conditional import for fcntl (Unix only)
if sys.platform != 'win32':
    import fcntl
else:
    fcntl = None
IS_WINDOWS = platform.system() == "Windows"

# Platform-specific PTY imports
if IS_WINDOWS:
    try:
        from winpty import PtyProcess
        PTY_BACKEND = "pywinpty"
    except ImportError:
        raise ImportError("pywinpty is required on Windows. Install with: pip install pywinpty")
else:
    try:
        from ptyprocess import PtyProcess
        PTY_BACKEND = "ptyprocess"
    except ImportError:
        raise ImportError("ptyprocess is required on Unix. Install with: pip install ptyprocess")

# Import version from package
try:
    from interactive_terminal import VERSION as CURRENT_VERSION
except ImportError:
    CURRENT_VERSION = "1.2.0"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("InteractiveTerminal")

# PyPI API URL for version checking
PYPI_API_URL = "https://pypi.org/pypi/vitjas-interactive-terminal/json"

# Environment variable to disable auto-update
AUTO_UPDATE_ENABLED = os.environ.get("VITJAS_AUTO_UPDATE", "true").lower() not in ("false", "0", "no")


# ============================================================================
# AUTO-UPDATE FUNCTIONALITY
# ============================================================================

def check_for_update() -> Optional[str]:
    """
    Check PyPI for the latest version of vitjas-interactive-terminal.
    
    Returns:
        Latest version string if available and newer than current, None otherwise.
    """
    try:
        logger.info(f"Checking for updates (current version: {CURRENT_VERSION})...")
        
        request = urllib.request.Request(
            PYPI_API_URL,
            headers={"Accept": "application/json", "User-Agent": f"vitjas-interactive-terminal/{CURRENT_VERSION}"}
        )
        
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            latest_version = data["info"]["version"]
            
            logger.info(f"Latest version on PyPI: {latest_version}")
            
            # Compare versions (simple string comparison works for semver)
            if latest_version != CURRENT_VERSION:
                # More robust version comparison
                try:
                    from packaging import version
                    if version.parse(latest_version) > version.parse(CURRENT_VERSION):
                        return latest_version
                except ImportError:
                    # Fallback to string comparison if packaging not available
                    if latest_version > CURRENT_VERSION:
                        return latest_version
        
        return None
        
    except urllib.error.URLError as e:
        logger.warning(f"Could not reach PyPI: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"Could not parse PyPI response: {e}")
        return None
    except Exception as e:
        logger.warning(f"Update check failed: {e}")
        return None


def perform_upgrade() -> bool:
    """
    Perform pip upgrade of vitjas-interactive-terminal.
    
    Returns:
        True if upgrade successful, False otherwise.
    """
    import subprocess
    try:
        logger.info("Starting auto-update via pip...")
        
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "vitjas-interactive-terminal"],
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )
        
        if result.returncode == 0:
            logger.info("Update installed successfully!")
            logger.info(f"pip output: {result.stdout}")
            return True
        else:
            logger.warning(f"Update failed with return code {result.returncode}")
            logger.warning(f"pip stderr: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.warning("Update timed out after 120 seconds")
        return False
    except Exception as e:
        logger.warning(f"Update failed with exception: {e}")
        return False


def run_auto_update_check():
    """
    Run the complete auto-update check and upgrade process.
    This is designed to be run synchronously at startup (quick check) or can be extended for async.
    """
    if not AUTO_UPDATE_ENABLED:
        logger.info("Auto-update disabled via VITJAS_AUTO_UPDATE environment variable")
        return False
    
    logger.info("Running auto-update check...")
    latest_version = check_for_update()
    
    if latest_version:
        logger.info(f"New version {latest_version} available (current: {CURRENT_VERSION})")
        
        if perform_upgrade():
            logger.info("Restart with new version to complete update.")
            return True
    else:
        logger.info("No update available or update check failed")
    
    return False


# Initialize FastMCP server
mcp = FastMCP("InteractiveTerminal")


# ============================================================================
# KEY MAPPINGS - Convert key names to escape sequences
# ============================================================================

class KeyMapper:
    """Maps human-readable key names to terminal escape sequences."""
    
    # Special keys - VT100/ANSI escape sequences
    SPECIAL_KEYS = {
        # Navigation
        "up": "\x1b[A",
        "down": "\x1b[B",
        "right": "\x1b[C",
        "left": "\x1b[D",
        "home": "\x1b[H",
        "end": "\x1b[F",
        "pageup": "\x1b[5~",
        "pagedown": "\x1b[6~",
        
        # Standard keys
        "enter": "\r",
        "return": "\r",
        "tab": "\t",
        "escape": "\x1b",
        "esc": "\x1b",
        "backspace": "\x7f",
        "delete": "\x1b[3~",
        "del": "\x1b[3~",
        
        # Function keys
        "f1": "\x1bOP",
        "f2": "\x1bOQ",
        "f3": "\x1bOR",
        "f4": "\x1bOS",
        "f5": "\x1b[15~",
        "f6": "\x1b[17~",
        "f7": "\x1b[18~",
        "f8": "\x1b[19~",
        "f9": "\x1b[20~",
        "f10": "\x1b[21~",
        "f11": "\x1b[23~",
        "f12": "\x1b[24~",
        
        # Keypad
        "kp_enter": "\r",
        "insert": "\x1b[2~",
    }
    
    @classmethod
    def get_key_sequence(cls, key: str) -> Optional[str]:
        """Convert a key name to its escape sequence."""
        key_lower = key.lower().strip()
        
        # Direct special key lookup
        if key_lower in cls.SPECIAL_KEYS:
            return cls.SPECIAL_KEYS[key_lower]
        
        # Ctrl combinations: ctrl+a, ctrl-a, ctrl_a -> \x01
        ctrl_match = re.match(r'^ctrl[+_-]([a-z])$', key_lower)
        if ctrl_match:
            char = ctrl_match.group(1)
            return chr(ord(char) - ord('a') + 1)
        
        # Alt combinations: alt+a, alt-a, alt_a -> \x1ba
        alt_match = re.match(r'^(?:alt|meta)[+_-]([a-z0-9])$', key_lower)
        if alt_match:
            char = alt_match.group(1)
            return f"\x1b{char}"
        
        # Shift+arrow for selection
        shift_arrow_match = re.match(r'^shift[+_-](up|down|left|right)$', key_lower)
        if shift_arrow_match:
            arrow = shift_arrow_match.group(1)
            shift_arrows = {
                "up": "\x1b[1;2A",
                "down": "\x1b[1;2B",
                "right": "\x1b[1;2C",
                "left": "\x1b[1;2D",
            }
            return shift_arrows.get(arrow)
        
        # Single character - return as-is
        if len(key) == 1:
            return key
        
        return None


# ============================================================================
# TERMINAL SESSION
# ============================================================================

class TerminalSession:
    """Represents a single interactive terminal session."""
    
    def __init__(self, terminal_id: str, directory: str, cols: int = 120, rows: int = 40):
        self.terminal_id = terminal_id
        self.directory = directory
        self.cols = cols
        self.rows = rows
        self.created = time.time()
        self._lock = threading.Lock()
        
        # Output buffer for scrollback
        self._buffer = ""
        self._buffer_max_size = 500 * 1024  # 500KB max buffer
        
        # Create the PTY process
        try:
            # Determine shell based on platform
            if IS_WINDOWS:
                # On Windows, use cmd.exe or powershell
                shell = os.environ.get('COMSPEC', 'cmd.exe')
            else:
                # On Unix-like systems, use bash or sh
                shell = os.environ.get('SHELL', '/bin/bash')
            
            # Create PtyProcess
            if IS_WINDOWS:
                # pywinpty on Windows
                self.process = PtyProcess.spawn(
                    [shell],
                    cwd=directory,
                    dimensions=(rows, cols),
                    env=os.environ.copy()
                )
                self._fd = None  # pywinpty handles fd internally
            else:
                # ptyprocess on Unix
                self.process = PtyProcess.spawn(
                    [shell],
                    cwd=directory,
                    dimensions=(rows, cols),
                    env=os.environ.copy()
                )
                # Get file descriptor for non-blocking I/O
                self._fd = self.process.fd
                # Set non-blocking mode
                flags = fcntl.fcntl(self._fd, fcntl.F_GETFL)
                fcntl.fcntl(self._fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            logger.info(f"Created terminal {terminal_id} with shell: {shell} (backend: {PTY_BACKEND})")
            
        except Exception as e:
            logger.error(f"Failed to create PTY for {terminal_id}: {e}")
            raise RuntimeError(f"Failed to create terminal: {e}")
    
    def is_alive(self) -> bool:
        """Check if the terminal process is still running."""
        try:
            return self.process.isalive()
        except Exception:
            return False
    
    def send(self, data: str) -> bool:
        """Send data to the terminal."""
        if not self.is_alive():
            return False
        
        try:
            with self._lock:
                # ptyprocess (Unix) requires bytes, pywinpty (Windows) accepts strings
                if IS_WINDOWS:
                    self.process.write(data)
                else:
                    self.process.write(data.encode('utf-8'))
            return True
        except Exception as e:
            logger.error(f"Error sending to terminal {self.terminal_id}: {e}")
            return False
    
    def read_output(self, timeout: float = 0.1) -> str:
        """Read available output from the terminal using non-blocking I/O."""
        output = ""
        
        if IS_WINDOWS:
            # pywinpty - use its read method with timeout
            try:
                data = self.process.read(timeout=timeout)
                if data:
                    output = data if isinstance(data, str) else data.decode('utf-8', errors='replace')
            except Exception:
                pass
        else:
            # ptyprocess on Unix - use select + os.read for non-blocking I/O
            try:
                # Use select to check if data is available
                ready, _, _ = select.select([self._fd], [], [], timeout)
                if ready:
                    # Read available data
                    try:
                        data = os.read(self._fd, 65536)
                        if data:
                            output = data.decode('utf-8', errors='replace')
                    except BlockingIOError:
                        pass
                    except OSError:
                        pass
            except Exception:
                pass
        
        # Append to buffer if we got output
        if output:
            with self._lock:
                self._buffer += output
                # Trim buffer if too large
                if len(self._buffer) > self._buffer_max_size:
                    self._buffer = self._buffer[-(self._buffer_max_size // 2):]
        
        return output
    
    def get_screen_content(self) -> str:
        """Get the current buffer content."""
        # First, read any pending output
        self.read_output(timeout=0.05)
        
        with self._lock:
            return self._buffer
    
    def resize(self, cols: int, rows: int):
        """Resize the terminal."""
        try:
            self.process.setwinsize(rows, cols)
            self.cols = cols
            self.rows = rows
            logger.info(f"Resized terminal {self.terminal_id} to {cols}x{rows}")
        except Exception as e:
            logger.warning(f"Failed to resize terminal {self.terminal_id}: {e}")
    
    def close(self):
        """Close the terminal session."""
        try:
            if self.is_alive():
                self.process.terminate()
        except Exception as e:
            logger.warning(f"Error closing terminal {self.terminal_id}: {e}")


# ============================================================================
# TERMINAL MANAGER
# ============================================================================

class TerminalManager:
    """Manages interactive terminal sessions using pywinpty (Windows) or ptyprocess (Unix)."""
    
    def __init__(self):
        self._sessions: Dict[str, TerminalSession] = {}
        self._lock = threading.Lock()
        self._counter = 0
    
    def _get_next_terminal_id(self) -> str:
        """Get the next available terminal ID."""
        with self._lock:
            self._counter += 1
            return f"term_{self._counter}"
    
    def create(self, directory: str, cols: int = 120, rows: int = 40) -> str:
        """Create a new interactive terminal session."""
        terminal_id = self._get_next_terminal_id()
        
        # Validate directory
        if not os.path.isdir(directory):
            directory = "/tmp" if not IS_WINDOWS else os.environ.get('TEMP', 'C:\\')
        
        session = TerminalSession(terminal_id, directory, cols, rows)
        
        with self._lock:
            self._sessions[terminal_id] = session
        
        return terminal_id
    
    def _session_exists(self, terminal_id: str) -> bool:
        """Check if a terminal session exists and is alive."""
        with self._lock:
            session = self._sessions.get(terminal_id)
            return session is not None and session.is_alive()
    
    def send_text(self, terminal_id: str, text: str) -> bool:
        """Send text to terminal."""
        with self._lock:
            session = self._sessions.get(terminal_id)
        
        if not session:
            return False
        
        # If text ends with newline, send the text then Enter
        if text.endswith("\n"):
            text_to_send = text[:-1]
            if text_to_send:
                session.send(text_to_send)
            time.sleep(0.02)
            session.send("\r")
        else:
            session.send(text)
        
        return True
    
    def send_key(self, terminal_id: str, key: str) -> bool:
        """Send special keys to terminal."""
        with self._lock:
            session = self._sessions.get(terminal_id)
        
        if not session:
            return False
        
        # Get the escape sequence for the key
        sequence = KeyMapper.get_key_sequence(key)
        if sequence:
            session.send(sequence)
            return True
        
        logger.warning(f"Unknown key: {key}")
        return False
    
    def get_info(self, terminal_id: str) -> Optional[Dict[str, Any]]:
        """Get terminal session info."""
        with self._lock:
            session = self._sessions.get(terminal_id)
        
        if not session:
            return None
        
        content = session.get_screen_content()
        lines = content.split('\n') if content else []
        
        return {
            "total_lines": len(lines),
            "history_lines": max(0, len(lines) - session.rows),
            "visible_height": session.rows,
            "visible_width": session.cols,
            "alive": session.is_alive()
        }
    
    def capture(self, terminal_id: str, start: Optional[int] = None, end: Optional[int] = None) -> str:
        """Capture terminal screen content."""
        with self._lock:
            session = self._sessions.get(terminal_id)
        
        if not session:
            return "Error: Terminal session not found."
        
        content = session.get_screen_content()
        if not content:
            return ""
        
        lines = content.split('\n')
        info = self.get_info(terminal_id)
        
        # Default to last visible area
        if start is None:
            start = max(0, len(lines) - session.rows)
        if end is None:
            end = len(lines)
        
        # Clamp values
        start = max(0, start)
        end = min(len(lines), end)
        
        selected_lines = lines[start:end]
        return '\n'.join(selected_lines)
    
    def list_terminals(self) -> List[Dict[str, Any]]:
        """List all active terminal sessions."""
        terminals = []
        dead_terminals = []
        
        with self._lock:
            for terminal_id, session in self._sessions.items():
                if session.is_alive():
                    terminals.append({
                        "id": terminal_id,
                        "cols": session.cols,
                        "rows": session.rows,
                        "created": int(session.created),
                        "cwd": session.directory
                    })
                else:
                    dead_terminals.append(terminal_id)
            
            # Clean up dead sessions
            for tid in dead_terminals:
                del self._sessions[tid]
        
        return terminals
    
    def delete(self, terminal_id: str) -> bool:
        """Delete a terminal session."""
        with self._lock:
            session = self._sessions.get(terminal_id)
            if session:
                session.close()
                del self._sessions[terminal_id]
                return True
        return False


# Global terminal manager instance
terminal_manager = TerminalManager()


# ============================================================================
# MCP TOOLS
# ============================================================================

@mcp.tool()
def create_terminal(directory: str = "/tmp", cols: int = 120, rows: int = 40) -> dict:
    """
    Create a new INTERACTIVE terminal session for controlling command-line programs.
    
    🖥️ THIS IS AN INTERACTIVE TERMINAL - You can:
    • Run any command-line program
    • Control TUI applications (nano, vim, htop, less, top, mc, etc.)
    • Navigate menus with ARROW KEYS (Up/Down/Left/Right)
    • Use Ctrl+C to interrupt, Ctrl+D to exit, Ctrl+Z to suspend
    • Start downloads/long processes and check results later
    • Edit files interactively in nano or vim
    
    The terminal persists between commands - you can run a command now,
    check the result later, send more input, etc.
    
    Args:
        directory: Working directory for the terminal (default: /tmp)
        cols: Terminal width in characters (default: 120)
        rows: Terminal height in lines (default: 40)
    
    Returns:
        {"terminal_id": "term_X", "status": "created", "cwd": "/path/to/dir"}
    """
    try:
        terminal_id = terminal_manager.create(directory, cols, rows)
        return {
            "terminal_id": terminal_id,
            "status": "created",
            "cwd": directory,
            "cols": cols,
            "rows": rows
        }
    except Exception as e:
        return {
            "terminal_id": None,
            "status": "error",
            "error": str(e),
            "cwd": directory
        }


@mcp.tool()
def send_text(terminal_id: str, text: str) -> dict:
    """
    Send text/commands to an interactive terminal.
    
    📝 Use this to:
    • Type commands (end with newline "\\n" to execute)
    • Enter text in interactive prompts
    • Fill in forms and input fields
    • Type in editors (nano, vim)
    
    ⚠️ To EXECUTE a command, end text with a newline: send_text("term_1", "ls -la\n")
    ⚠️ To just TYPE without executing, omit the newline: send_text("term_1", "hello")
    
    Args:
        terminal_id: The terminal ID from create_terminal()
        text: Text to send (use "\n" for Enter/newline)
    
    Returns:
        {"success": true/false, "terminal_id": "..."}
    """
    success = terminal_manager.send_text(terminal_id, text)
    return {
        "success": success,
        "terminal_id": terminal_id,
        "error": None if success else "Terminal not found"
    }


@mcp.tool()
def send_keys(terminal_id: str, keys: str) -> dict:
    """
    Send special keys to an interactive terminal - USE THIS FOR TUI NAVIGATION!
    
    ⌨️ AVAILABLE KEYS:
    
    Navigation:
    • "up", "down", "left", "right" - Arrow keys (for menus, file lists, etc.)
    • "home", "end" - Jump to start/end of line
    • "pageup", "pagedown" - Scroll pages
    
    Control Keys:
    • "ctrl+c" - Interrupt/Cancel current command (VERY USEFUL!)
    • "ctrl+d" - End of input / Exit shell
    • "ctrl+z" - Suspend process
    • "ctrl+a" - Go to line start
    • "ctrl+e" - Go to line end
    • "ctrl+u" - Clear line before cursor
    • "ctrl+k" - Clear line after cursor
    • "ctrl+w" - Delete word before cursor
    • "ctrl+l" - Clear screen
    
    Alt Keys:
    • "alt+f" - Move forward one word
    • "alt+b" - Move backward one word
    • "alt+d" - Delete word after cursor
    
    Other:
    • "enter" - Execute/confirm
    • "escape" - Cancel/exit mode
    • "tab" - Autocomplete
    • "backspace", "delete"
    • "f1" through "f12" - Function keys
    
    🎯 EXAMPLES:
    • Navigate htop: send_keys("term_1", "down") then send_keys("term_1", "enter")
    • Exit nano: send_keys("term_1", "ctrl+x")
    • Cancel running command: send_keys("term_1", "ctrl+c")
    • Select menu option: send_keys("term_1", "down") x3 then "enter"
    
    Args:
        terminal_id: The terminal ID from create_terminal()
        keys: Key name (e.g., "ctrl+c", "up", "down", "enter", "escape")
    
    Returns:
        {"success": true/false, "terminal_id": "...", "key_sent": "..."}
    """
    success = terminal_manager.send_key(terminal_id, keys)
    return {
        "success": success,
        "terminal_id": terminal_id,
        "key_sent": keys if success else None,
        "error": None if success else "Terminal not found or unknown key"
    }


@mcp.tool()
def get_screen(terminal_id: str, start_line: int = None, end_line: int = None) -> dict:
    """
    Read the current terminal screen content.
    
    📺 Use this to:
    • See command output and results
    • Check status of long-running processes
    • Read what's displayed in TUI apps (htop, nano, etc.)
    • Capture error messages
    • Verify command execution
    
    Returns the terminal content with metadata about dimensions.
    
    Args:
        terminal_id: The terminal ID from create_terminal()
        start_line: Optional start line (for scrolling back in history)
        end_line: Optional end line
    
    Returns:
        {
            "content": "...terminal output...",
            "total_lines": 45,
            "visible_rows": 40,
            "cols": 120,
            "terminal_id": "term_1"
        }
    """
    content = terminal_manager.capture(terminal_id, start_line, end_line)
    info = terminal_manager.get_info(terminal_id)
    
    lines = content.split('\n') if content else []
    
    error = None
    if content and content.startswith("Error:"):
        error = content
    
    return {
        "content": content,
        "total_lines": len(lines),
        "visible_rows": info.get("visible_height", 0) if info else 0,
        "cols": info.get("visible_width", 0) if info else 0,
        "terminal_id": terminal_id,
        "error": error
    }


@mcp.tool()
def list_terminals() -> dict:
    """
    List all active interactive terminal sessions.
    
    📋 Use this to:
    • See what terminals you have created
    • Find terminal IDs for other commands
    • Check which directories terminals are in
    
    Returns:
        {
            "terminals": [
                {"id": "term_1", "cwd": "/tmp", "cols": 120, "rows": 40},
                ...
            ],
            "count": 2
        }
    """
    terminals = terminal_manager.list_terminals()
    return {
        "terminals": terminals,
        "count": len(terminals)
    }


@mcp.tool()
def delete_terminal(terminal_id: str) -> dict:
    """
    Delete/close an interactive terminal session.
    
    🗑️ Use this to:
    • Clean up terminals you no longer need
    • Free up resources
    • Close terminals with stuck processes
    
    ⚠️ WARNING: This will terminate any running processes in that terminal!
    
    Args:
        terminal_id: The terminal ID to delete
    
    Returns:
        {"success": true/false, "message": "..."}
    """
    success = terminal_manager.delete(terminal_id)
    return {
        "success": success,
        "terminal_id": terminal_id,
        "message": "Terminal deleted" if success else "Terminal not found"
    }


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Entry point for pip installation."""
    logger.info(f"Starting InteractiveTerminal MCP Server v{CURRENT_VERSION}")
    logger.info(f"Platform: {platform.system()}, PTY Backend: {PTY_BACKEND}")
    
    # Run auto-update check before starting the server
    try:
        run_auto_update_check()
    except Exception as e:
        logger.warning(f"Auto-update check failed (non-fatal): {e}")
    
    # Start the MCP server
    mcp.run()


if __name__ == "__main__":
    main()
