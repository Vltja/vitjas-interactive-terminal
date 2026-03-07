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

Uses tmux as backend for reliable session management.
"""

import os
import subprocess
import time
import shlex
import re
from typing import Dict, Optional, List, Any
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("InteractiveTerminal")


class TerminalManager:
    """Manages interactive terminal sessions using tmux.
    
    IMPORTANT: This class does NOT use internal state (dict) to track sessions.
    Instead, it queries tmux directly for all operations. This ensures
    sessions persist across MCP server process restarts.
    """
    
    # Prefix for all terminal session names
    SESSION_PREFIX = "term_"
    
    def _session_exists(self, terminal_id: str) -> bool:
        """Check if a tmux session exists."""
        result = subprocess.run(
            ["tmux", "has-session", "-t", terminal_id],
            capture_output=True
        )
        return result.returncode == 0
    
    def _get_next_terminal_id(self) -> str:
        """Get the next available terminal ID by checking existing tmux sessions."""
        existing_ids = set()
        
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    line = line.strip()
                    if line.startswith(self.SESSION_PREFIX):
                        try:
                            num = int(line[len(self.SESSION_PREFIX):])
                            existing_ids.add(num)
                        except ValueError:
                            pass
        except Exception:
            pass
        
        # Find next available ID
        counter = 1
        while counter in existing_ids:
            counter += 1
        
        return f"{self.SESSION_PREFIX}{counter}"
    
    def _get_session_cwd(self, terminal_id: str) -> str:
        """Get current working directory of a tmux session."""
        try:
            result = subprocess.run([
                "tmux", "display-message", "-t", terminal_id, "-p",
                "#{pane_current_path}"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "/unknown"
    
    def create(self, directory: str, cols: int = 120, rows: int = 40) -> str:
        """Create a new interactive terminal session."""
        terminal_id = self._get_next_terminal_id()
        
        # Create detached tmux session
        result = subprocess.run([
            "tmux", "new-session", "-d",
            "-s", terminal_id,
            "-x", str(cols),
            "-y", str(rows),
            "bash", "-c",
            f"cd {shlex.quote(directory)} && exec bash"
        ], cwd=directory, capture_output=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create tmux session: {result.stderr.decode()}")
        
        # Configure tmux session
        subprocess.run(["tmux", "set-option", "-t", terminal_id, "history-limit", "50000"])
        subprocess.run(["tmux", "set-option", "-t", terminal_id, "status", "off"])
        
        return terminal_id
    
    def send_text(self, terminal_id: str, text: str) -> bool:
        """Send text to terminal. Handles newlines automatically."""
        if not self._session_exists(terminal_id):
            return False
        
        if text.endswith("\n"):
            # Send text without newline, then send Enter
            subprocess.run(["tmux", "send-keys", "-t", terminal_id, text[:-1]])
            time.sleep(0.05)
            subprocess.run(["tmux", "send-keys", "-t", terminal_id, "C-m"])
        else:
            subprocess.run(["tmux", "send-keys", "-t", terminal_id, text])
        
        return True
    
    def send_key(self, terminal_id: str, key: str) -> bool:
        """Send special keys to terminal."""
        if not self._session_exists(terminal_id):
            return False
        
        # Comprehensive key mapping
        key_map = {
            # Navigation keys
            "enter": "C-m", "return": "C-m",
            "escape": "Escape", "esc": "Escape",
            "tab": "Tab", "backspace": "BS",
            "delete": "Delete", "del": "Delete",
            
            # Arrow keys - CRITICAL for TUI navigation
            "up": "Up", "down": "Down",
            "left": "Left", "right": "Right",
            
            # Page navigation
            "pageup": "PageUp", "pagedown": "PageDown",
            "home": "Home", "end": "End",
            
            # Function keys
            "f1": "F1", "f2": "F2", "f3": "F3", "f4": "F4",
            "f5": "F5", "f6": "F6", "f7": "F7", "f8": "F8",
            "f9": "F9", "f10": "F10", "f11": "F11", "f12": "F12",
            
            # Keypad
            "kp_enter": "KPEnter",
        }
        
        # Add Ctrl combinations (Ctrl+A through Ctrl+Z)
        for c in "abcdefghijklmnopqrstuvwxyz":
            key_map[f"ctrl+{c}"] = f"C-{c.upper()}"
            key_map[f"ctrl-{c}"] = f"C-{c.upper()}"
            key_map[f"ctrl_{c}"] = f"C-{c.upper()}"
        
        # Add Alt/Meta combinations
        for c in "abcdefghijklmnopqrstuvwxyz":
            key_map[f"alt+{c}"] = f"M-{c}"
            key_map[f"alt-{c}"] = f"M-{c}"
            key_map[f"alt_{c}"] = f"M-{c}"
            key_map[f"meta+{c}"] = f"M-{c}"
        
        # Add Shift+arrow for selection
        key_map["shift+up"] = "S-Up"
        key_map["shift+down"] = "S-Down"
        key_map["shift+left"] = "S-Left"
        key_map["shift+right"] = "S-Right"
        
        # Look up the key, default to literal if not found
        tmux_key = key_map.get(key.lower(), key)
        subprocess.run(["tmux", "send-keys", "-t", terminal_id, tmux_key])
        
        return True
    
    def get_info(self, terminal_id: str) -> Optional[Dict[str, int]]:
        """Get terminal session info."""
        if not self._session_exists(terminal_id):
            return None
        
        result = subprocess.run([
            "tmux", "display-message", "-t", terminal_id, "-p",
            "#{history_size} #{pane_height} #{pane_width}"
        ], capture_output=True, text=True)
        
        try:
            parts = result.stdout.strip().split()
            history_size = int(parts[0])
            pane_height = int(parts[1])
            pane_width = int(parts[2])
            return {
                "total_lines": history_size + pane_height,
                "history_lines": history_size,
                "visible_height": pane_height,
                "visible_width": pane_width
            }
        except (ValueError, IndexError):
            return None
    
    def capture(self, terminal_id: str, start: Optional[int] = None, end: Optional[int] = None) -> str:
        """Capture terminal screen content."""
        if not self._session_exists(terminal_id):
            return "Error: Terminal session not found."
        
        info = self.get_info(terminal_id)
        if not info:
            return "Error: Could not get terminal info."
        
        # Default to visible area
        if start is None:
            start = info["history_lines"]
        if end is None:
            end = info["total_lines"] - 1
        
        # Convert to tmux coordinates
        tmux_start = start - info["history_lines"]
        tmux_end = end - info["history_lines"]
        
        result = subprocess.run([
            "tmux", "capture-pane", "-p",
            "-t", terminal_id,
            "-J",  # Join wrapped lines
            "-S", str(tmux_start),
            "-E", str(tmux_end)
        ], capture_output=True, text=True)
        
        return result.stdout
    
    def list_terminals(self) -> List[Dict[str, Any]]:
        """List all active terminal sessions by querying tmux."""
        terminals = []
        
        try:
            # Use pane_width/pane_height instead of session_width/session_height
            result = subprocess.run([
                "tmux", "list-sessions", "-F",
                "#{session_name}|#{pane_width}|#{pane_height}|#{session_created}"
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                return []
            
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                    
                parts = line.split('|')
                if len(parts) >= 4:
                    session_name = parts[0]
                    # Only include sessions with our prefix
                    if session_name.startswith(self.SESSION_PREFIX):
                        try:
                            terminals.append({
                                "id": session_name,
                                "cols": int(parts[1]) if parts[1] else 120,
                                "rows": int(parts[2]) if parts[2] else 40,
                                "created": int(parts[3]) if parts[3] else 0,
                                "cwd": self._get_session_cwd(session_name)
                            })
                        except (ValueError, IndexError):
                            continue
        except Exception:
            pass
        
        return terminals
    
    def delete(self, terminal_id: str) -> bool:
        """Delete a terminal session."""
        if not self._session_exists(terminal_id):
            return False
        
        subprocess.run(["tmux", "kill-session", "-t", terminal_id])
        return True


# Global terminal manager instance
# Note: This instance doesn't store state internally, it queries tmux directly
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
    terminal_id = terminal_manager.create(directory, cols, rows)
    return {
        "terminal_id": terminal_id,
        "status": "created",
        "cwd": directory,
        "cols": cols,
        "rows": rows
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
        "error": None if success else "Terminal not found"
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
    
    return {
        "content": content,
        "total_lines": len(lines),
        "visible_rows": info.get("visible_height", 0) if info else 0,
        "cols": info.get("visible_width", 0) if info else 0,
        "terminal_id": terminal_id,
        "error": None if content and not content.startswith("Error") else content
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

if __name__ == "__main__":
    # Run the MCP server

def main():
    """Entry point for pip installation."""
    mcp.run()

if __name__ == "__main__":
    main()
