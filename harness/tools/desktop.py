"""Desktop GUI Automation Tools.

Provides the agent with the ability to control mouse, keyboard, launch apps,
take screenshots, list windows, and interact directly with the desktop environment.
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Optional
from .base import BaseTool
from ..core.config import settings

# Attempt to import pyautogui safely
try:
    import pyautogui
    # Disable PyAutoGUI fail-safe pause for faster automated workflows, but keep safe corners
    pyautogui.PAUSE = 0.1
    PYAUTOGUI_AVAILABLE = True
except Exception:
    PYAUTOGUI_AVAILABLE = False


class DesktopScreenshotTool(BaseTool):
    name = "desktop_screenshot"
    description = (
        "Capture a screenshot of the entire desktop screen or save to a file path. "
        "Returns the path of the saved screenshot image."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "output_path": {
                "type": "string",
                "description": "Optional file path to save the screenshot (.png). Defaults to a temp artifact file.",
            },
        },
    }

    def run(self, output_path: str = None) -> str:
        if not PYAUTOGUI_AVAILABLE:
            return "Error: pyautogui is not available in the environment."

        try:
            if not output_path:
                dump_dir = settings.workspace_root / ".screenshots"
                dump_dir.mkdir(exist_ok=True)
                filename = f"screenshot_{int(time.time())}.png"
                target = dump_dir / filename
            else:
                target = Path(output_path).expanduser().resolve()
                target.parent.mkdir(parents=True, exist_ok=True)

            img = pyautogui.screenshot()
            img.save(str(target))
            width, height = img.size
            return f"Screenshot successfully saved to '{target}' (Resolution: {width}x{height})."
        except Exception as e:
            return f"Error capturing screenshot: {str(e)}"


class DesktopMouseTool(BaseTool):
    name = "desktop_mouse"
    description = (
        "Perform mouse actions: move, click, double_click, right_click, drag, or scroll."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["click", "double_click", "right_click", "move", "scroll"],
                "description": "Mouse action to execute",
            },
            "x": {"type": "integer", "description": "X coordinate on screen"},
            "y": {"type": "integer", "description": "Y coordinate on screen"},
            "scroll_amount": {"type": "integer", "description": "Scroll clicks (positive for up, negative for down)"},
        },
        "required": ["action"],
    }

    def run(self, action: str, x: int = None, y: int = None, scroll_amount: int = None) -> str:
        if not PYAUTOGUI_AVAILABLE:
            return "Error: pyautogui is not available."

        try:
            curr_x, curr_y = pyautogui.position()
            target_x = x if x is not None else curr_x
            target_y = y if y is not None else curr_y

            if action == "move":
                pyautogui.moveTo(target_x, target_y)
                return f"Mouse moved to ({target_x}, {target_y})."
            elif action == "click":
                pyautogui.click(target_x, target_y)
                return f"Clicked mouse at ({target_x}, {target_y})."
            elif action == "double_click":
                pyautogui.doubleClick(target_x, target_y)
                return f"Double-clicked mouse at ({target_x}, {target_y})."
            elif action == "right_click":
                pyautogui.rightClick(target_x, target_y)
                return f"Right-clicked mouse at ({target_x}, {target_y})."
            elif action == "scroll":
                clicks = scroll_amount or 0
                pyautogui.scroll(clicks, x=target_x, y=target_y)
                return f"Scrolled mouse {clicks} clicks at ({target_x}, {target_y})."
            else:
                return f"Unknown mouse action '{action}'."
        except Exception as e:
            return f"Error executing mouse action '{action}': {str(e)}"


class DesktopKeyboardTool(BaseTool):
    name = "desktop_keyboard"
    description = (
        "Send keyboard keystrokes, shortcuts, or type text directly onto the active window."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["type", "press", "hotkey"],
                "description": "Action type: 'type' enters raw text, 'press' presses a single key (e.g. 'enter', 'esc'), 'hotkey' presses combinations (e.g. 'ctrl+c', 'alt+tab')",
            },
            "text": {"type": "string", "description": "Text to type or key/hotkey combination (e.g. 'ctrl+shift+esc', 'enter')"},
        },
        "required": ["action", "text"],
    }

    def run(self, action: str, text: str) -> str:
        if not PYAUTOGUI_AVAILABLE:
            return "Error: pyautogui is not available."

        try:
            if action == "type":
                pyautogui.write(text, interval=0.01)
                return f"Typed text ({len(text)} characters)."
            elif action == "press":
                key = text.strip().lower()
                pyautogui.press(key)
                return f"Pressed key '{key}'."
            elif action == "hotkey":
                keys = [k.strip().lower() for k in text.replace("+", " ").split()]
                pyautogui.hotkey(*keys)
                return f"Executed hotkey: {' + '.join(keys)}."
            else:
                return f"Unknown keyboard action: {action}"
        except Exception as e:
            return f"Error executing keyboard action: {str(e)}"


class DesktopGetWindowsTool(BaseTool):
    name = "desktop_get_windows"
    description = "List currently open desktop application windows and their titles."
    parameters_schema = {
        "type": "object",
        "properties": {
            "filter": {"type": "string", "description": "Optional substring to filter window titles"},
        },
    }

    def run(self, filter: str = None) -> str:
        try:
            import pygetwindow as gw
            windows = gw.getAllWindows()
            results = []
            for w in windows:
                title = w.title.strip()
                if not title:
                    continue
                if filter and filter.lower() not in title.lower():
                    continue
                results.append(f"- '{title}' (Position: {w.left},{w.top} | Size: {w.width}x{w.height} | Visible: {w.visible})")

            if not results:
                return "No matching visible windows found."
            return "=== Open Windows ===\n" + "\n".join(results[:30])
        except Exception:
            # Fallback using powershell command to list processes with main window handles
            try:
                ps_script = 'Get-Process | Where-Object { [string]::IsNullOrWhiteSpace($_.MainWindowTitle) -eq $false } | Select-Object Id, ProcessName, MainWindowTitle | Out-String'
                proc = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                    timeout=8,
                )
                output = proc.stdout.strip()
                if not output:
                    return "No open desktop windows with titles detected."
                return f"=== Open Windows (Process View) ===\n{output}"
            except Exception as ex:
                return f"Error retrieving windows: {str(ex)}"


class DesktopLaunchTool(BaseTool):
    name = "desktop_launch"
    description = "Launch an application, open a file in its default OS app, or open a URL in default browser."
    parameters_schema = {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Executable name, file path, or URL to launch (e.g. 'notepad', 'calc', 'https://google.com')"},
            "args": {"type": "string", "description": "Optional command line arguments"},
        },
        "required": ["target"],
    }

    def run(self, target: str, args: str = None) -> str:
        try:
            cmd = f'start "" "{target}"'
            if args:
                cmd += f" {args}"
            subprocess.Popen(cmd, shell=True)
            return f"Successfully initiated launch for: {target}"
        except Exception as e:
            return f"Error launching target: {str(e)}"
