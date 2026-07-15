"""Extended tool executor with document reading capabilities"""

import json
import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests

from agent.tools.shell import ShellTool
from agent.tools.file import FileTool
from agent.tools.time_tool import TimeTool
from agent.tools.pdf_tool import PDFTool
from agent.tools.skill_tool import SkillTool
from agent.tools.glob import execute_glob, get_glob_tool_definition
from agent.tools.grep import execute_grep, get_grep_tool_definition
from agent.tools.edit import execute_edit, get_edit_tool_definition
from agent.tools.websearch import execute_websearch, get_websearch_tool_definition
from agent.tools.codesearch import execute_codesearch, get_codesearch_tool_definition
from agent.tools.preview import PreviewManager
from agent.tools.plan import PlanTool, get_plan_tool_definition


class ExtendedToolExecutor:
    """Execute tools with extended capabilities including document reading"""

    def __init__(
        self,
        skills_loader=None,
        preview_manager: Optional[PreviewManager] = None,
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        project_root: Optional[str] = None,
    ):
        self.shell_tool = ShellTool()
        self.file_tool = FileTool()
        self.pdf_tool = PDFTool()
        self.skill_tool = SkillTool(skills_loader) if skills_loader else None
        self.preview_manager = preview_manager or PreviewManager(
            project_root or Path(__file__).resolve().parents[2]
        )
        self.conversation_id = conversation_id
        self.message_id = message_id
        self._plan_tools: Dict[str, PlanTool] = {}
        self._plan_tools_lock = threading.RLock()
        self.tools: Dict[str, Callable] = {
            "bash": self.execute_shell,
            "read": self.execute_file_read,
            "glob": execute_glob,
            "grep": execute_grep,
            "edit": execute_edit,
            "write": self.execute_file_write,
            "file_list": self.execute_file_list,
            "file_delete": self.execute_file_delete,
            "dir_create": self.execute_dir_create,
            "dir_change": self.execute_dir_change,
            "read_pdf": self.execute_read_pdf,
            "read_markdown": self.execute_read_markdown,
            "read_json": self.execute_read_json,
            "search_files": self.execute_search_files,
            "get_file_info": self.execute_get_file_info,
            "copy_file": self.execute_copy_file,
            "move_file": self.execute_move_file,
            "create_file": self.execute_create_file,
            "websearch": execute_websearch,
            "codesearch": execute_codesearch,
            "read_url": self.execute_read_url,
            "set_timer": self.execute_set_timer,
            "send_file": self.execute_send_file,
            "generate_pdf": self.execute_generate_pdf,
            "load_skill": self.execute_load_skill,
            "question": self.execute_question,
            "update_plan": self.execute_update_plan,
            "project_preview": self.execute_project_preview,
            # Legacy aliases
            "shell": self.execute_shell,
            "file_read": self.execute_file_read,
            "file_write": self.execute_file_write,
            "web_search": execute_websearch,
        }

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools in OpenAI function calling format - aligned with OpenCode"""
        tools = [
            get_plan_tool_definition(),
            {
                "type": "function",
                "function": {
                    "name": "project_preview",
                    "description": "Start, inspect, or stop a persistent loopback-only Web project preview. Use this instead of bash for long-running development servers. For Python static sites, `python3 -m http.server` is enough: the preview manager injects the managed port and 127.0.0.1 binding automatically.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["start", "status", "stop"],
                                "description": "Preview lifecycle action",
                            },
                            "command": {
                                "type": "string",
                                "description": "Start command. Prefer injected $HOST/$PORT for dev servers, e.g. npm run dev -- --host $HOST --port $PORT. Python `-m http.server` commands are normalized automatically. Required for start.",
                            },
                            "workdir": {
                                "type": "string",
                                "description": "Project-relative or absolute working directory inside the project root",
                            },
                            "name": {
                                "type": "string",
                                "description": "Short project name displayed in the preview card",
                            },
                            "port": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 65535,
                                "description": "Loopback port; use 0 or omit to allocate one automatically",
                            },
                            "health_path": {
                                "type": "string",
                                "description": "Local HTTP path used for readiness checks (default: /)",
                            },
                            "startup_timeout": {
                                "type": "number",
                                "minimum": 1,
                                "maximum": 120,
                                "description": "Maximum seconds to wait for the server to become reachable",
                            },
                            "preview_id": {
                                "type": "string",
                                "description": "Preview identifier returned by start; required for stop and optional for status",
                            },
                        },
                        "required": ["action"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "bash",
                    "description": "Executes a given bash command in a persistent shell session with optional timeout, ensuring proper handling and security measures. AVOID using cd - use the workdir parameter instead.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The command to execute",
                            },
                            "timeout": {
                                "type": "number",
                                "description": "Optional timeout in milliseconds",
                            },
                            "workdir": {
                                "type": "string",
                                "description": "The working directory to run the command in",
                            },
                            "description": {
                                "type": "string",
                                "description": "Clear, concise description of what this command does",
                            },
                        },
                        "required": ["command"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read",
                    "description": "Read a file or directory from the local filesystem. By default returns up to 2000 lines from the start. Use offset parameter to read specific sections.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filePath": {
                                "type": "string",
                                "description": "The absolute path to the file or directory to read",
                            },
                            "offset": {
                                "type": "number",
                                "description": "The line number to start reading from (1-indexed)",
                            },
                            "limit": {
                                "type": "number",
                                "description": "The maximum number of lines to read (defaults to 2000)",
                            },
                        },
                        "required": ["filePath"],
                    },
                },
            },
            get_glob_tool_definition(),
            get_grep_tool_definition(),
            get_edit_tool_definition(),
            {
                "type": "function",
                "function": {
                    "name": "write",
                    "description": "Writes a file to the local filesystem. This tool will overwrite existing files.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "The content to write to the file",
                            },
                            "path": {
                                "type": "string",
                                "description": "The absolute path to the file to write",
                            },
                        },
                        "required": ["content", "path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "file_list",
                    "description": "List files in a directory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Directory path (default: current directory)",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "file_delete",
                    "description": "Delete a file or folder (supports both files and directories)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the file or folder to delete",
                            },
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "dir_create",
                    "description": "Create a directory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the directory to create",
                            },
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "copy_file",
                    "description": "Copy a file or directory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string",
                                "description": "Source file path",
                            },
                            "destination": {
                                "type": "string",
                                "description": "Destination path",
                            },
                        },
                        "required": ["source", "destination"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "move_file",
                    "description": "Move or rename a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string",
                                "description": "Source file path",
                            },
                            "destination": {
                                "type": "string",
                                "description": "Destination path",
                            },
                        },
                        "required": ["source", "destination"],
                    },
                },
            },
            get_websearch_tool_definition(),
            get_codesearch_tool_definition(),
            {
                "type": "function",
                "function": {
                    "name": "read_url",
                    "description": "Fetches content from a specified URL. Takes a URL and optional format as input.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The URL to fetch content from",
                            },
                            "format": {
                                "type": "string",
                                "description": "The format to return (text, markdown, html)",
                            },
                        },
                        "required": ["url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_pdf",
                    "description": "Read PDF/Word documents (supports .pdf, .docx, .doc formats)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the PDF or document file",
                            },
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "set_timer",
                    "description": "Set a timer that will trigger after specified minutes",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "minutes": {
                                "type": "number",
                                "description": "Minutes to wait",
                            },
                            "message": {
                                "type": "string",
                                "description": "Message to display when timer ends",
                            },
                        },
                        "required": ["minutes"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "send_file",
                    "description": "Send a file to the user via Feishu (Gateway Mode only)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the file to send",
                            },
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_pdf",
                    "description": "Generate PDF from Markdown, text, HTML, or Word documents",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "input_path": {
                                "type": "string",
                                "description": "Input file path",
                            },
                            "output_path": {
                                "type": "string",
                                "description": "Output PDF file path",
                            },
                            "format": {
                                "type": "string",
                                "description": "Input format (markdown/text/html/docx)",
                            },
                        },
                        "required": ["input_path", "output_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "load_skill",
                    "description": "Load a skill's complete content to get detailed guidance and instructions",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skill_name": {
                                "type": "string",
                                "description": "Name of the skill to load",
                            },
                        },
                        "required": ["skill_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "question",
                    "description": "Pause execution and ask the user one or more selectable questions. Do not continue until the user submits answers. Set multiple=true for every multi-select question. Set allow_free_text=true when the user may add text; never describe a capability in the question text without setting its matching field.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "questions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "header": {
                                            "type": "string",
                                            "description": "Very short label (max 30 chars)",
                                        },
                                        "multiple": {
                                            "type": "boolean",
                                            "description": "Required. True only when the user may select more than one option; false for exactly one choice.",
                                        },
                                        "selection_required": {
                                            "type": "boolean",
                                            "description": "Whether a listed option must be selected. Defaults to true; when allow_free_text is true, typed text can also satisfy the question.",
                                        },
                                        "allow_free_text": {
                                            "type": "boolean",
                                            "description": "Show a text supplement field below this question.",
                                        },
                                        "free_text_label": {
                                            "type": "string",
                                            "description": "Short label for the optional text supplement field.",
                                        },
                                        "free_text_placeholder": {
                                            "type": "string",
                                            "description": "Helpful example or placeholder for the text supplement field.",
                                        },
                                        "free_text_required": {
                                            "type": "boolean",
                                            "description": "Require text in the supplement field before submission.",
                                        },
                                        "options": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "description": {
                                                        "type": "string",
                                                        "description": "Explanation of choice",
                                                    },
                                                    "label": {
                                                        "type": "string",
                                                        "description": "Display text",
                                                    },
                                                },
                                                "required": ["label", "description"],
                                            },
                                        },
                                        "question": {
                                            "type": "string",
                                            "description": "Complete question",
                                        },
                                    },
                                    "required": ["question", "header", "multiple", "options"],
                                },
                            },
                        },
                        "required": ["questions"],
                    },
                },
            },
        ]

        return tools

    def execute(
        self,
        tool_call: Dict[str, Any],
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        runtime: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Execute a tool call"""
        tool_name = tool_call.get("tool")
        params = tool_call.get("params", {})

        if tool_name not in self.tools:
            return f"Error: Unknown tool '{tool_name}'"

        try:
            if tool_name == "update_plan":
                return self.execute_update_plan(
                    params,
                    conversation_id=(
                        conversation_id
                        if conversation_id is not None
                        else tool_call.get("conversation_id", self.conversation_id)
                    ),
                    message_id=(
                        message_id
                        if message_id is not None
                        else tool_call.get("message_id", self.message_id)
                    ),
                )
            if tool_name == "project_preview":
                return self.execute_project_preview(
                    params,
                    conversation_id=(
                        conversation_id
                        if conversation_id is not None
                        else tool_call.get("conversation_id", self.conversation_id)
                    ),
                    message_id=(
                        message_id
                        if message_id is not None
                        else tool_call.get("message_id", self.message_id)
                    ),
                )
            if tool_name in {"bash", "shell"}:
                return self.execute_shell(params, runtime=runtime)
            result = self.tools[tool_name](params)
            return result
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"

    @staticmethod
    def _plan_key(
        conversation_id: Optional[str], message_id: Optional[str]
    ) -> str:
        conversation = str(conversation_id or "").strip()
        message = str(message_id or "").strip()
        return f"{conversation}:{message}" if conversation or message else "default"

    def _plan_tool_for(
        self, conversation_id: Optional[str], message_id: Optional[str]
    ) -> PlanTool:
        key = self._plan_key(conversation_id, message_id)
        with self._plan_tools_lock:
            return self._plan_tools.setdefault(key, PlanTool())

    def execute_update_plan(
        self,
        params: Dict[str, Any],
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> str:
        """Replace the plan isolated to the active task message."""
        return self._plan_tool_for(conversation_id, message_id).update(params)

    def get_plan_snapshot(
        self,
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the latest snapshot for one task without creating it."""
        key = self._plan_key(conversation_id, message_id)
        with self._plan_tools_lock:
            tool = self._plan_tools.get(key)
        return tool.snapshot() if tool else None

    def discard_plan_snapshot(
        self,
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> None:
        """Release one completed task's in-memory plan state."""
        key = self._plan_key(conversation_id, message_id)
        with self._plan_tools_lock:
            self._plan_tools.pop(key, None)

    def clear_plan_snapshots(self, conversation_id: Optional[str] = None) -> None:
        """Release plan state for one conversation or the whole executor."""
        conversation = str(conversation_id or "").strip()
        with self._plan_tools_lock:
            if not conversation:
                self._plan_tools.clear()
                return
            prefix = f"{conversation}:"
            for key in tuple(self._plan_tools):
                if key == conversation or key.startswith(prefix):
                    self._plan_tools.pop(key, None)

    def execute_shell(
        self,
        params: Dict[str, Any],
        runtime: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Execute shell command"""
        command = params.get("command", "")
        if not command:
            return "Error: command parameter required"

        timeout = params.get("timeout")
        if timeout is not None:
            try:
                timeout = max(float(timeout) / 1000, 0.1)
            except (TypeError, ValueError):
                return "Error: timeout must be a number of milliseconds"

        result = self.shell_tool.execute(
            command,
            cwd=params.get("workdir"),
            timeout=timeout,
            cancel_event=(runtime or {}).get("cancel_event"),
            cancelled=(runtime or {}).get("cancelled"),
        )
        return self.shell_tool.format_result(result)

    def execute_file_read(self, params: Dict[str, Any]) -> str:
        """Read file with pagination support - aligned with OpenCode"""
        file_path = params.get("filePath", "") or params.get("path", "")
        if not file_path:
            return "Error: filePath parameter required"

        suffix = os.path.splitext(str(file_path))[1].lower()
        if suffix in {".pdf", ".doc", ".docx"}:
            return self.execute_read_pdf({"path": file_path})
        if suffix in {".xlsx", ".xlsm"}:
            return self.execute_read_excel({"path": file_path})

        offset = params.get("offset")
        limit = params.get("limit")

        success, content = self.file_tool.read_file(file_path, offset, limit)

        if success:
            return content
        return f"Error: {content}"

    def execute_read_excel(self, params: Dict[str, Any]) -> str:
        """Read an Excel workbook as tab-separated sheet content."""
        path = params.get("path", "") or params.get("filePath", "")
        if not path:
            return "Error: path parameter required"
        try:
            import openpyxl

            workbook = openpyxl.load_workbook(
                FileTool.expand_path(path), read_only=True, data_only=True
            )
            lines = []
            for sheet in workbook.worksheets:
                lines.append(f"## Sheet: {sheet.title}")
                for row in sheet.iter_rows(values_only=True):
                    values = ["" if value is None else str(value) for value in row]
                    if any(values):
                        lines.append("\t".join(values))
                    if sum(len(line) + 1 for line in lines) >= 50000:
                        lines.append("[Workbook content truncated]")
                        break
                if lines and lines[-1] == "[Workbook content truncated]":
                    break
            workbook.close()
            return "Excel contents:\n" + "\n".join(lines)
        except ImportError:
            return "Error: openpyxl not installed. Try: pip install openpyxl"
        except Exception as exc:
            return f"Error reading Excel workbook: {str(exc)}"

    def execute_file_write(self, params: Dict[str, Any]) -> str:
        """Write file"""
        path = params.get("path", "")
        content = params.get("content", "")
        if not path:
            return "Error: path parameter required"

        success, message = self.file_tool.write_file(path, content)
        return message if success else f"Error: {message}"

    def execute_file_list(self, params: Dict[str, Any]) -> str:
        """List files"""
        path = params.get("path", ".")
        success, files = self.file_tool.list_files(path)

        if success:
            if not files:
                return f"Files in {path}:\nnone"
            file_list = "\n".join(files)
            return f"Files in {path}:\n{file_list}"
        return f"Error: {files[0] if files else 'Unknown error'}"

    def execute_file_delete(self, params: Dict[str, Any]) -> str:
        """Delete file or directory"""
        path = params.get("path", "")
        if not path:
            return "Error: path parameter required"

        # 先检查是文件还是目录
        from pathlib import Path

        file_path = Path(path).resolve()

        if file_path.is_dir():
            success, message = self.file_tool.delete_directory(path)
        else:
            success, message = self.file_tool.delete_file(path)
        return message if success else f"Error: {message}"

    def execute_dir_create(self, params: Dict[str, Any]) -> str:
        """Create directory"""
        path = params.get("path", "")
        if not path:
            return "Error: path parameter required"

        success, message = self.file_tool.create_directory(path)
        return message if success else f"Error: {message}"

    def execute_dir_change(self, params: Dict[str, Any]) -> str:
        """Change directory"""
        path = params.get("path", "")
        if not path:
            return "Error: path parameter required"

        success, message = self.shell_tool.change_dir(path)
        return message if success else f"Error: {message}"

    def execute_read_pdf(self, params: Dict[str, Any]) -> str:
        """Read PDF or document file"""
        path = params.get("path", "")
        if not path:
            return "Error: path parameter required"

        try:
            expanded_path = FileTool.expand_path(path)

            # 检查文件类型
            if expanded_path.endswith(".docx") or expanded_path.endswith(".doc"):
                # 处理Word文档
                try:
                    from docx import Document

                    doc = Document(expanded_path)
                    text = ""
                    for para in doc.paragraphs:
                        if para.text.strip():
                            text += para.text + "\n"

                    # 也提取表格内容
                    for table in doc.tables:
                        for row in table.rows:
                            row_text = " | ".join([cell.text for cell in row.cells])
                            text += row_text + "\n"

                    return f"Document contents:\n{text}"
                except ImportError:
                    return (
                        "Error: python-docx not installed. Try: pip install python-docx"
                    )

            elif expanded_path.endswith(".pdf"):
                # 处理PDF文件
                try:
                    import PyPDF2

                    with open(expanded_path, "rb") as file:
                        reader = PyPDF2.PdfReader(file)
                        text = ""
                        for page in reader.pages:  # Read all pages
                            text += page.extract_text() + "\n"
                    return f"PDF contents:\n{text}"
                except ImportError:
                    return "Error: PyPDF2 not installed. Try: pip install PyPDF2"

            else:
                return f"Error: Unsupported file format. Supported: .pdf, .docx, .doc"

        except Exception as e:
            return f"Error reading document: {str(e)}"

    def execute_read_markdown(self, params: Dict[str, Any]) -> str:
        """Read markdown file"""
        path = params.get("path", "")
        if not path:
            return "Error: path parameter required"

        success, content = self.file_tool.read_file(path)
        if success:
            return f"Markdown contents:\n{content}"
        return f"Error: {content}"

    def execute_read_json(self, params: Dict[str, Any]) -> str:
        """Read and parse JSON file"""
        path = params.get("path", "")
        if not path:
            return "Error: path parameter required"

        try:
            success, content = self.file_tool.read_file(path)
            if success:
                data = json.loads(content)
                return (
                    f"JSON contents:\n{json.dumps(data, indent=2, ensure_ascii=False)}"
                )
            return f"Error: {content}"
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON format - {str(e)}"

    def execute_search_files(self, params: Dict[str, Any]) -> str:
        """Search for files"""
        pattern = params.get("pattern", "")
        path = params.get("path", ".")
        if not pattern:
            return "Error: pattern parameter required"

        try:
            result = self.shell_tool.execute(
                f"find {FileTool.expand_path(path)} -name '*{pattern}*' -type f | head -20"
            )
            if result.success:
                return f"Found files:\n{result.stdout}"
            return f"No files found matching pattern: {pattern}"
        except Exception as e:
            return f"Error searching files: {str(e)}"

    def execute_get_file_info(self, params: Dict[str, Any]) -> str:
        """Get file information"""
        path = params.get("path", "")
        if not path:
            return "Error: path parameter required"

        success, info = self.file_tool.get_file_info(path)
        if success:
            return f"File info:\n{json.dumps(info, indent=2, ensure_ascii=False)}"
        return f"Error: {info.get('error', 'Unknown error')}"

    def execute_copy_file(self, params: Dict[str, Any]) -> str:
        """Copy file"""
        source = params.get("source", "")
        destination = params.get("destination", "")
        if not source or not destination:
            return "Error: source and destination parameters required"

        try:
            import shutil

            source_path = FileTool.expand_path(source)
            dest_path = FileTool.expand_path(destination)
            shutil.copy2(source_path, dest_path)
            return f"File copied: {source} -> {destination}"
        except Exception as e:
            return f"Error copying file: {str(e)}"

    def execute_move_file(self, params: Dict[str, Any]) -> str:
        """Move or rename file"""
        source = params.get("source", "")
        destination = params.get("destination", "")
        if not source or not destination:
            return "Error: source and destination parameters required"

        try:
            import shutil

            source_path = FileTool.expand_path(source)
            dest_path = FileTool.expand_path(destination)
            shutil.move(source_path, dest_path)
            return f"File moved: {source} -> {destination}"
        except Exception as e:
            return f"Error moving file: {str(e)}"

    def execute_create_file(self, params: Dict[str, Any]) -> str:
        """Create file with content"""
        path = params.get("path", "")
        content = params.get("content", "")
        if not path:
            return "Error: path parameter required"

        success, message = self.file_tool.write_file(path, content)
        return message if success else f"Error: {message}"

    def execute_web_search(self, params: Dict[str, Any]) -> str:
        """Search the web using Tavily API"""
        query = params.get("query", "")
        if not query:
            return "Error: query parameter required"

        try:
            tavily_api_key = os.getenv("TAVILY_API_KEY")
            if not tavily_api_key:
                return "Error: TAVILY_API_KEY not found in environment variables"

            search_url = "https://api.tavily.com/search"
            payload = {
                "api_key": tavily_api_key,
                "query": query,
                "include_answer": True,
                "max_results": 5,
            }

            response = requests.post(search_url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()

            results = []

            # Add answer if available
            if data.get("answer"):
                results.append(f"答案: {data['answer']}")
                results.append("")

            # Add search results
            if data.get("results"):
                results.append("搜索结果:")
                for result in data.get("results", []):
                    if result.get("title"):
                        results.append(f"- {result['title']}")
                    if result.get("content"):
                        results.append(f"  {result['content']}")
                    if result.get("url"):
                        results.append(f"  链接: {result['url']}")
                    results.append("")

            if results:
                return "搜索结果:\n" + "\n".join(results)
            else:
                return f"未找到关于 '{query}' 的搜索结果"

        except requests.exceptions.Timeout:
            return "Error: 搜索请求超时"
        except requests.exceptions.RequestException as e:
            return f"Error: 网络请求失败 - {str(e)}"
        except Exception as e:
            return f"Error: 搜索失败 - {str(e)}"

    def execute_read_url(self, params: Dict[str, Any]) -> str:
        """Read and extract content from a URL"""
        url = params.get("url", "")
        if not url:
            return "Error: url parameter required"

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(url, headers=headers, timeout=15)

            # Try to detect and set correct encoding
            if response.encoding is None or response.encoding.lower() == "iso-8859-1":
                # Try to detect encoding from content
                try:
                    import chardet

                    detected = chardet.detect(response.content)
                    if detected and detected.get("encoding"):
                        response.encoding = detected["encoding"]
                    else:
                        response.encoding = "utf-8"
                except ImportError:
                    # If chardet not available, try common encodings
                    for encoding in ["utf-8", "gb2312", "gbk", "big5", "iso-8859-1"]:
                        try:
                            response.content.decode(encoding)
                            response.encoding = encoding
                            break
                        except:
                            continue

            response.raise_for_status()

            # Get text content
            content = response.text

            # Try using BeautifulSoup if available
            try:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(content, "html.parser")

                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()

                # Get text
                text = soup.get_text()

                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (
                    phrase.strip() for line in lines for phrase in line.split("  ")
                )
                text = "\n".join(chunk for chunk in chunks if chunk)

                if text:
                    return f"URL 内容:\n{text}"
                else:
                    return "Error: 无法从 URL 提取内容"

            except ImportError:
                # If BeautifulSoup not available, try simple regex extraction
                import re

                # Remove script and style tags
                content = re.sub(
                    r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL
                )
                content = re.sub(
                    r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL
                )

                # Remove HTML tags
                content = re.sub(r"<[^>]+>", "", content)

                # Clean up whitespace
                content = re.sub(r"\s+", " ", content).strip()

                if content:
                    return f"URL 内容:\n{content}"
                else:
                    return "Error: 无法从 URL 提取内容"

        except requests.exceptions.Timeout:
            return "Error: 请求超时"
        except requests.exceptions.RequestException as e:
            return f"Error: 网络请求失败 - {str(e)}"
        except Exception as e:
            return f"Error: 读取 URL 失败 - {str(e)}"

    def execute_set_timer(self, params: Dict[str, Any]) -> str:
        """Set a timer that will trigger after specified minutes"""
        import time
        import threading

        minutes = params.get("minutes", 0)
        message = params.get("message", "时间到了！")
        executor = params.get("executor", None)  # 获取执行器引用

        if not isinstance(minutes, (int, float)) or minutes <= 0:
            return "Error: minutes 必须是正数"

        try:
            seconds = minutes * 60

            def timer_callback():
                """Timer callback function"""
                time.sleep(seconds)
                print(f"\n⏰ 【定时器触发】{message}\n")

                # 如果有执行器引用，设置标志
                if executor:
                    executor.timer_triggered = True
                    executor.waiting_for_timer = False

            # 在后台线程中运行定时器
            timer_thread = threading.Thread(target=timer_callback, daemon=True)
            timer_thread.start()

            return f"✅ 定时器已设置：{minutes}分钟后将显示 '{message}'"

        except Exception as e:
            return f"Error: 设置定时器失败 - {str(e)}"

    def execute_send_file(self, params: Dict[str, Any]) -> str:
        """Send a file to the user via Feishu"""
        import asyncio
        from agent.bus.events import OutboundMessage

        file_path = params.get("path", "")

        if not file_path:
            return "Error: 必须指定文件路径"

        import os

        if not os.path.isfile(file_path):
            return f"Error: 文件不存在 - {file_path}"

        # Get the current executor context to access bus and chat info
        # This is a bit hacky but necessary for the current architecture
        import inspect

        frame = inspect.currentframe()
        executor = None

        # Walk up the stack to find NaturalTaskExecutor
        while frame:
            if "self" in frame.f_locals:
                obj = frame.f_locals["self"]
                if hasattr(obj, "bus") and hasattr(obj, "current_chat_id"):
                    executor = obj
                    break
            frame = frame.f_back

        if not executor or not executor.bus or not executor.current_chat_id:
            return "Error: 无法发送文件 - 未在网关模式下运行"

        try:
            # Create outbound message with file path
            msg = OutboundMessage(
                channel=executor.current_channel or "feishu",
                chat_id=executor.current_chat_id,
                content=file_path,  # Pass file path as content
            )

            # Send via bus (non-blocking)
            asyncio.create_task(executor.bus.publish_outbound(msg))

            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            return f"✅ 文件已发送: {file_name} ({file_size} bytes)"

        except Exception as e:
            return f"Error: 发送文件失败 - {str(e)}"

    def execute_generate_pdf(self, params: Dict[str, Any]) -> str:
        """Generate PDF from various formats"""
        input_path = params.get("input_path", "")
        output_path = params.get("output_path", "")
        format_type = params.get("format", "")

        # Parameter validation
        if not input_path or not output_path:
            return "Error: input_path and output_path parameters required"

        # Auto-detect format from file extension if not specified
        if not format_type:
            if input_path.lower().endswith(".md"):
                format_type = "markdown"
            elif input_path.lower().endswith(".html"):
                format_type = "html"
            elif input_path.lower().endswith(".docx") or input_path.lower().endswith(
                ".doc"
            ):
                format_type = "docx"
            else:
                format_type = "text"

        if format_type not in ["markdown", "text", "html", "docx"]:
            return f"Error: Unsupported format '{format_type}'. Supported: markdown, text, html, docx"

        # Path expansion
        expanded_input = FileTool.expand_path(input_path)
        expanded_output = FileTool.expand_path(output_path)

        # Call PDF tool
        success, message = self.pdf_tool.generate_pdf(
            expanded_input, expanded_output, format_type
        )

        if success:
            return f"✅ {message}"
        else:
            return message

    def execute_load_skill(self, params: Dict[str, Any]) -> str:
        """Load a skill's complete content"""
        if not self.skill_tool:
            return "Error: Skill tool not initialized"

        skill_name = params.get("skill_name", "").strip()
        if not skill_name:
            return "Error: skill_name parameter required"

        success, content = self.skill_tool.load_skill(skill_name)
        return content

    def execute_question(self, params: Dict[str, Any]) -> str:
        """Execute question - ask user for input"""
        questions = params.get("questions", [])
        if not questions:
            return "Error: questions parameter required"

        # Format question for user
        formatted = []
        for q in questions:
            header = q.get("header", "Question")
            question_text = q.get("question", "")
            options = q.get("options", [])

            formatted.append(f"【{header}】")
            formatted.append(question_text)
            if options:
                formatted.append("选项:")
                for opt in options:
                    formatted.append(
                        f"  - {opt.get('label', '')}: {opt.get('description', '')}"
                    )
            formatted.append("")

        return "请回复你的选择:\n" + "\n".join(formatted)

    def execute_project_preview(
        self,
        params: Dict[str, Any],
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> str:
        """Execute a persistent project preview lifecycle action."""
        action = str(params.get("action", "")).strip().lower()
        preview_id = str(params.get("preview_id", "")).strip()

        if action == "start":
            result = self.preview_manager.start(
                command=params.get("command", ""),
                workdir=params.get("workdir", "."),
                name=params.get("name"),
                port=params.get("port", 0),
                health_path=params.get("health_path", "/"),
                startup_timeout=params.get("startup_timeout", 20),
                conversation_id=conversation_id,
                message_id=message_id,
            )
        elif action == "status":
            result = self.preview_manager.status(
                preview_id=preview_id or None,
                conversation_id=conversation_id,
            )
        elif action == "stop":
            if not preview_id:
                return "Error: preview_id parameter required for stop"
            result = self.preview_manager.stop(preview_id)
        else:
            return "Error: action must be start, status, or stop"

        return json.dumps(result, ensure_ascii=False)
