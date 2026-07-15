"""Interactive CLI interface."""

import os
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table


class CLIInterface:
    """Interactive command-line interface"""

    def __init__(self, history_file: str = ".agent_history"):
        self.console = Console()
        self.history_file = Path(history_file).expanduser()
        self.commands = {}
        self.running = False
        self._history = self._load_history()

    def _load_history(self) -> list[str]:
        try:
            if self.history_file.exists():
                return self.history_file.read_text(encoding="utf-8").splitlines()[-500:]
        except OSError:
            pass
        return []

    def _save_history(self) -> None:
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            self.history_file.write_text(
                "\n".join(self._history[-500:]) + "\n", encoding="utf-8"
            )
        except OSError:
            pass

    def register_command(self, name: str, handler: Callable, help_text: str = "") -> None:
        """Register a command handler"""
        self.commands[name] = {"handler": handler, "help": help_text}

    def print_welcome(self) -> None:
        """Print welcome message"""
        self.console.print(
            Panel.fit(
                "[bold]麒麟 OS-Agent[/bold]\n输入 [cyan]help[/cyan] 查看命令，输入 [cyan]exit[/cyan] 退出。",
                border_style="cyan",
            )
        )

    def print_help(self) -> None:
        """Print help information"""
        table = Table(title="可用命令", show_header=True, header_style="bold cyan")
        table.add_column("命令", style="cyan", no_wrap=True)
        table.add_column("说明")

        for cmd_name, cmd_info in self.commands.items():
            table.add_row(cmd_name, cmd_info["help"])

        self.console.print(table)

    def print_error(self, message: str) -> None:
        """Print error message"""
        self.console.print(f"[red]✗ Error:[/red] {message}")

    def print_success(self, message: str) -> None:
        """Print success message"""
        self.console.print(f"[green]✓ Success:[/green] {message}")

    def print_info(self, message: str) -> None:
        """Print info message"""
        self.console.print(f"[blue]ℹ Info:[/blue] {message}")

    def print_panel(self, content: str, title: str = "", style: str = "blue") -> None:
        """Print content in a panel"""
        panel = Panel(content, title=title, style=style)
        self.console.print(panel)

    def print_code(self, code: str, language: str = "python", theme: str = "monokai") -> None:
        """Print syntax-highlighted code"""
        syntax = Syntax(code, language, theme=theme, line_numbers=True)
        self.console.print(syntax)

    def get_input(self, prompt: str = "> ") -> str:
        """Get user input"""
        try:
            return input(prompt)
        except KeyboardInterrupt:
            return "exit"
        except EOFError:
            return "exit"

    def run_interactive_loop(self) -> None:
        """Run interactive command loop"""
        self.print_welcome()
        self.running = True

        while self.running:
            try:
                user_input = self.get_input("agent> ")

                if not user_input.strip():
                    continue

                self._history.append(user_input.strip())
                self._save_history()

                parts = user_input.strip().split(maxsplit=1)
                command = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""

                if command == "exit" or command == "quit":
                    self.console.print("[yellow]再见！[/yellow]")
                    self.running = False
                    break

                if command == "help":
                    self.print_help()
                    continue

                if command in self.commands:
                    try:
                        self.commands[command]["handler"](args)
                    except Exception as e:
                        self.print_error(f"Command failed: {str(e)}")
                else:
                    self.print_error(f"未知命令: {command}。输入 help 查看可用命令。")

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Interrupted[/yellow]")
                continue

    def clear_screen(self) -> None:
        """Clear terminal screen"""
        os.system("clear" if os.name == "posix" else "cls")
