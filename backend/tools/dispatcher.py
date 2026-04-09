"""
Tool dispatcher — routes tool calls from the brain to the right handler.

Handles both power tools (powershell, http, file) and plugins.
"""

import json
from typing import Any
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def dispatch_tool(tool_name: str, arguments: str | dict) -> str:
    """
    Execute a tool call and return the result as a string.
    
    Args:
        tool_name: Function name from the LLM tool call
        arguments: JSON string or dict of parameters
    
    Returns:
        Result string to feed back to the LLM.
    """
    # Parse arguments if string
    if isinstance(arguments, str):
        try:
            params = json.loads(arguments)
        except json.JSONDecodeError:
            return f"Invalid arguments JSON: {arguments[:100]}"
    else:
        params = arguments

    logger.info(f"[DISPATCH] {tool_name}({params})")

    try:
        # ── Power tools ──────────────────────────────────────────────────
        if tool_name == "run_powershell":
            from backend.tools.powershell import run_powershell
            return run_powershell(
                script=params.get("script", ""),
                timeout=params.get("timeout", 10),
            )

        elif tool_name == "http_get":
            from backend.tools.http_request import http_get
            return http_get(
                url=params.get("url", ""),
                timeout=params.get("timeout", 8),
            )

        elif tool_name == "find_file":
            from backend.tools.file_search import find_file
            return find_file(
                name=params.get("name", ""),
                search_dirs=params.get("search_dirs"),
            )

        elif tool_name == "search_internet":
            from duckduckgo_search import DDGS
            query = params.get("query", "")
            try:
                results = DDGS().text(query, max_results=4)
                if not results:
                    return f"No internet results found for '{query}'."
                
                output = f"Internet search results for '{query}':\n\n"
                for i, r in enumerate(results, 1):
                    output += f"{i}. {r.get('title')}\n{r.get('body')}\n\n"
                return output
            except Exception as e:
                return f"Internet search failed: {e}"

        elif tool_name == "read_file":
            return _read_file(params.get("path", ""))

        elif tool_name == "write_file":
            return _write_file(
                path=params.get("path", ""),
                content=params.get("content", ""),
                mode=params.get("mode", "overwrite"),
            )

        elif tool_name == "play_youtube":
            # GPT-4o picks the query — we just launch it
            query = params.get("query", "")
            if not query:
                return "No search query provided."
            from backend.plugins.youtube import YouTubePlugin
            result = YouTubePlugin().execute(query=query)
            return result

        elif tool_name == "open_app":
            # Use the existing executor's open_app action
            name = params.get("name", "")
            if not name:
                return "No app name provided."
            import subprocess, shutil, os
            # Common app name aliases
            aliases = {
                "chrome": "chrome.exe", "google chrome": "chrome.exe",
                "edge": "msedge.exe", "microsoft edge": "msedge.exe",
                "notepad": "notepad.exe", "calculator": "calc.exe",
                "spotify": "Spotify.exe", "discord": "Discord.exe",
                "vlc": "vlc.exe", "paint": "mspaint.exe",
                "explorer": "explorer.exe", "file explorer": "explorer.exe",
            }
            exe = aliases.get(name.lower(), name)
            try:
                subprocess.Popen([exe], shell=True)
                import time; time.sleep(1.5)  # Give app time to open
                return f"Opened {name}."
            except Exception as e:
                return f"Could not open {name}: {e}"

        # ── Plugin system ────────────────────────────────────────────────
        elif tool_name == "run_plugin":
            from backend.plugins import execute_plugin
            plugin_name = params.pop("plugin_name", "")
            return execute_plugin(plugin_name, params)

        # ── Legacy executor actions (used by fast router) ────────────────
        else:
            # Fall back to the existing executor for fast-router actions
            from backend.executor import execute
            action = {"type": tool_name, "params": params}
            result = execute(action)
            if result is None:
                return "Done."
            elif isinstance(result, dict):
                return result.get("speak", "") or result.get("ui_log", "") or "Done."
            return str(result)

    except Exception as e:
        logger.error(f"[DISPATCH] {tool_name} failed: {e}")
        return f"Tool '{tool_name}' failed: {str(e)[:150]}"


# ── File helpers ──────────────────────────────────────────────────────────────

MAX_FILE_CHARS = 8000  # Cap to avoid token explosion

def _read_file(path: str) -> str:
    """Read and return text content from a file. Supports .txt, .md, .py, .json, .csv, .log, .docx, .pdf."""
    import os
    
    if not path:
        return "No file path provided."
    if not os.path.exists(path):
        return f"File not found: {path}"
    if not os.path.isfile(path):
        return f"Path is a directory, not a file: {path}"
    
    file_size = os.path.getsize(path)
    if file_size > 5 * 1024 * 1024:  # 5 MB cap
        return f"File is too large ({file_size // 1024} KB). Please use a smaller file."
    
    ext = os.path.splitext(path)[1].lower()
    
    try:
        # ── Plain text formats ────────────────────────────────────────────
        if ext in (".txt", ".md", ".py", ".js", ".ts", ".json", ".csv", ".log", ".ini", ".toml", ".yaml", ".yml", ".html", ".xml"):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if len(content) > MAX_FILE_CHARS:
                content = content[:MAX_FILE_CHARS] + f"\n\n[... truncated — file has {len(content)} chars total]"
            return f"Contents of '{os.path.basename(path)}':\n\n{content}"
        
        # ── Word documents (.docx) ────────────────────────────────────────
        elif ext == ".docx":
            try:
                import docx
                doc = docx.Document(path)
                text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
                if len(text) > MAX_FILE_CHARS:
                    text = text[:MAX_FILE_CHARS] + "\n[... truncated]"
                return f"Word document '{os.path.basename(path)}':\n\n{text}"
            except ImportError:
                return "python-docx not installed. Run: pip install python-docx"
        
        # ── PDF documents ─────────────────────────────────────────────────
        elif ext == ".pdf":
            try:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    text = "\n".join(
                        page.extract_text() or "" for page in pdf.pages[:15]
                    )
                if len(text) > MAX_FILE_CHARS:
                    text = text[:MAX_FILE_CHARS] + "\n[... truncated, max 8000 chars]"
                return f"PDF '{os.path.basename(path)}':\n\n{text}"
            except ImportError:
                return "pdfplumber not installed. Run: pip install pdfplumber"
        
        # ── PowerPoint presentations (.pptx) ─────────────────────────────
        elif ext == ".pptx":
            try:
                from pptx import Presentation
                from pptx.util import Pt
                
                prs = Presentation(path)
                slides_text: list[str] = []
                
                for i, slide in enumerate(prs.slides, 1):
                    parts: list[str] = [f"--- Slide {i} ---"]
                    
                    # Extract title
                    if slide.shapes.title and slide.shapes.title.text.strip():
                        parts.append(f"Title: {slide.shapes.title.text.strip()}")
                    
                    # Extract all text from shapes (skip title, already captured)
                    body_lines: list[str] = []
                    for shape in slide.shapes:
                        if shape == slide.shapes.title:
                            continue
                        if shape.has_text_frame:
                            for para in shape.text_frame.paragraphs:
                                line = para.text.strip()
                                if line:
                                    # Add bullet indent based on paragraph level
                                    indent = "  " * getattr(para, "level", 0)
                                    body_lines.append(f"{indent}• {line}")
                    
                    if body_lines:
                        parts.append("\n".join(body_lines))
                    
                    # Extract speaker notes
                    if slide.has_notes_slide:
                        notes = slide.notes_slide.notes_text_frame.text.strip()
                        if notes:
                            parts.append(f"[Speaker notes: {notes}]")
                    
                    slides_text.append("\n".join(parts))
                
                full_text = "\n\n".join(slides_text)
                if len(full_text) > MAX_FILE_CHARS:
                    full_text = full_text[:MAX_FILE_CHARS] + f"\n\n[... truncated — {len(prs.slides)} slides total]"
                
                return (
                    f"PowerPoint presentation '{os.path.basename(path)}' "
                    f"({len(prs.slides)} slides):\n\n{full_text}"
                )
            except ImportError:
                return "python-pptx not installed. Run: pip install python-pptx"
        
        else:
            return f"Unsupported file type: {ext}. Supported: .txt .md .py .json .csv .log .docx .pdf .pptx"
    
    except Exception as e:
        return f"Error reading file '{path}': {str(e)[:200]}"


def _write_file(path: str, content: str, mode: str = "overwrite") -> str:
    """Write or append content to a file."""
    import os
    
    if not path:
        return "No file path provided."
    if not content:
        return "No content to write."
    
    try:
        # Create parent directories if needed
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        
        write_mode = "a" if mode == "append" else "w"
        with open(path, write_mode, encoding="utf-8") as f:
            f.write(content)
        
        action = "Appended to" if mode == "append" else "Written"
        return f"{action} '{os.path.basename(path)}' ({len(content)} chars)."
    
    except Exception as e:
        return f"Error writing file '{path}': {str(e)[:200]}"
