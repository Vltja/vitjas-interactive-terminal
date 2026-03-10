# 🖥️ Interactive Terminal MCP Server

[![PyPI version](https://badge.fury.io/py/vitjas-interactive-terminal.svg)](https://badge.fury.io/py/vitjas-interactive-terminal)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A fully interactive terminal MCP server for AI agents with **TUI support**, **keyboard control**, and **screen capture** - Cross-platform (Windows, Linux, Mac).

## ✨ Features

- 🖥️ **Full Terminal Control** - Create, manage, and delete terminal sessions
- ⌨️ **Keyboard Support** - Arrow keys, Ctrl, Alt, F-keys, PageUp/Down, etc.
- 📺 **TUI Applications** - Works with htop, vim, nano, mc, and more
- 🔄 **Auto-Update** - Automatically checks and installs updates from PyPI
- 🌍 **Cross-Platform** - Windows (pywinpty), Linux/Mac (ptyprocess)

## 📦 Installation

```bash
pip install vitjas-interactive-terminal
```

## 🚀 Usage

### Start the MCP Server

You can start the server in **3 ways**:

```bash
# Option 1: Entry Point (recommended)
vitjas-interactive-terminal

# Option 2: Python Module
python -m interactive_terminal

# Option 3: Python3 Module (Linux/Mac)
python3 -m interactive_terminal
```

### MCP Configuration

#### For Claude Desktop / Agent Zero:

**Linux/Mac (Option A - Entry Point):**
```json
{
  "mcpServers": {
    "InteractiveTerminal": {
      "command": "vitjas-interactive-terminal",
      "args": [],
      "init_timeout": 30
    }
  }
}
```

**Linux/Mac (Option B - Python3 Module):**
```json
{
  "mcpServers": {
    "InteractiveTerminal": {
      "command": "python3",
      "args": ["-m", "interactive_terminal"],
      "init_timeout": 30
    }
  }
}
```

**Windows:**
```json
{
  "mcpServers": {
    "InteractiveTerminal": {
      "command": "python",
      "args": ["-m", "interactive_terminal"],
      "init_timeout": 30
    }
  }
}
```

## 🛠️ Available Tools

| Tool | Description |
|------|-------------|
| `create_terminal` | Create a new interactive terminal session |
| `send_text` | Send text/commands to a terminal |
| `send_keys` | Send special keys (arrows, Ctrl+C, etc.) |
| `get_screen` | Read terminal screen content |
| `list_terminals` | List all active terminals |
| `delete_terminal` | Delete/close a terminal |
| `search_buffer` | Search through terminal history |

## ⌨️ Supported Keys

- **Navigation:** up, down, left, right, home, end, pageup, pagedown
- **Control:** ctrl+c, ctrl+d, ctrl+z, ctrl+a, ctrl+e, ctrl+u, ctrl+k, ctrl+w, ctrl+l
- **Alt:** alt+f, alt+b, alt+d
- **Other:** enter, escape, tab, backspace, delete, f1-f12

## 💡 Examples

### Navigate htop:
```bash
# Create terminal and start htop
create_terminal → send_text("htop\n") → get_screen()
# Navigate with arrow keys
send_keys("down") → send_keys("enter")
# Exit
send_keys("f10") or send_keys("q")
```

### Edit with nano:
```bash
# Create and open file
create_terminal → send_text("nano test.txt\n")
# Type content
send_text("Hello World!")
# Save and exit
send_keys("ctrl+x") → send_text("Y") → send_keys("enter")
```

## 🔧 Configuration

### Disable Auto-Update:
```bash
VITJAS_AUTO_UPDATE=false vitjas-interactive-terminal
```

## 📋 Requirements

- Python >= 3.10
- **Windows:** pywinpty >= 2.0.0 (auto-installed)
- **Linux/Mac:** ptyprocess >= 0.7.0 (auto-installed)

## 🔗 Links

- **PyPI:** https://pypi.org/project/vitjas-interactive-terminal/
- **GitHub:** https://github.com/Vltja/vitjas-interactive-terminal
- **Issues:** https://github.com/Vltja/vitjas-interactive-terminal/issues

## 📜 License

MIT License - see [LICENSE](LICENSE)

## 👤 Author

**Vltja** - [GitHub](https://github.com/Vltja)
