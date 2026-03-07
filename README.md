# Vitjas Interactive Terminal MCP Server

A Model Context Protocol (MCP) server providing **fully interactive terminal sessions** for AI agents.

## 🎯 Purpose

This server enables AI agents to interact with **any** command-line application, including:
- **TUI applications**: htop, top, btop, ncdu, nmtui, etc.
- **Text editors**: nano, vim, emacs
- **Pagers**: less, more
- **File managers**: midnight commander (mc), ranger
- **Interactive CLIs**: python REPL, node REPL, mysql, psql
- **Long-running processes**: downloads, builds, tests

## ✨ Key Features

- 🖥️ **True Interactive Terminals** - Not just command execution!
- ⌨️ **Full Keyboard Support** - Arrow keys, Ctrl, Alt, Function keys
- 📜 **Scrollback History** - 50,000 lines of history
- 🔄 **Session Persistence** - Terminals persist between commands
- 📊 **Screen Capture** - Read terminal output anytime
- 🎮 **TUI Navigation** - Navigate menus, lists, editors
- 🔍 **Buffer Search** - Search through terminal history

## 📦 Installation

### From PyPI (Recommended)

```bash
pip install vitjas-interactive-terminal
```

### Prerequisites

```bash
# Ensure tmux is installed
apt-get install tmux    # Debian/Ubuntu
brew install tmux        # macOS
```

## ⚙️ Configuration

### For Claude Desktop / Agent Zero

Add to your MCP configuration:

```json
{
  "mcpServers": {
    "InteractiveTerminal": {
      "command": "vitjas-interactive-terminal",
      "args": []
    }
  }
}
```

**No paths needed!** After `pip install`, the command is available system-wide.

## 🔧 Available Tools

| Tool | Description |
|------|-------------|
| `create_terminal` | Create a new interactive terminal session |
| `send_text` | Send text/commands to terminal |
| `send_keys` | Send special keys (arrows, Ctrl, Alt, F-keys) |
| `get_screen` | Read terminal output with metadata |
| `list_terminals` | List all active terminal sessions |
| `delete_terminal` | Close/delete a terminal session |
| `search_buffer` | Search through terminal history |

## ⌨️ Supported Keys for `send_keys`

| Category | Keys |
|----------|------|
| **Navigation** | `up`, `down`, `left`, `right`, `home`, `end`, `pageup`, `pagedown` |
| **Control** | `ctrl+a` through `ctrl+z`, `ctrl+c` (interrupt), `ctrl+d` (EOF) |
| **Alt** | `alt+a` through `alt+z` |
| **Special** | `enter`, `escape`, `tab`, `backspace`, `delete`, `f1`-`f12` |

## 💡 Usage Examples

### Run a Simple Command
```
1. create_terminal(directory="/home/user")
2. send_text("ls -la\n")
3. get_screen()  # See the directory listing
```

### Navigate htop
```
1. create_terminal()
2. send_text("htop\n")
3. send_keys("down")    # Move selection down
4. send_keys("enter")   # View process details
5. send_keys("q")       # Quit htop
```

### Edit File in nano
```
1. create_terminal(directory="/tmp")
2. send_text("nano myfile.txt\n")
3. send_text("Hello World!")
4. send_keys("ctrl+o")  # Save
5. send_keys("enter")   # Confirm filename
6. send_keys("ctrl+x")  # Exit
```

## 🔧 Technical Details

- **Backend**: tmux sessions
- **History**: 50,000 lines scrollback
- **Default size**: 120 cols × 40 rows
- **Session persistence**: Until deleted or server restart

## 📄 License

MIT License
