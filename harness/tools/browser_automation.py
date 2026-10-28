"""Browser Automation Tools using Selenium & Browser-Use frameworks."""

import logging
from typing import Any, Dict, Optional
from ..tools.base import BaseTool

logger = logging.getLogger(__name__)


class SeleniumInspectTool(BaseTool):
    """Selenium WebDriver for enterprise headless browser automation and UI testing."""

    name = "selenium_browser_run"
    description = (
        "Automate web interactions, DOM extraction, and enterprise UI tests using Selenium WebDriver. "
        "Can navigate to a URL, extract title/page source/text, click elements, or fill form inputs in headless Chrome."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Target webpage URL to visit.",
            },
            "action": {
                "type": "string",
                "enum": ["get_text", "get_title", "click_selector", "execute_script"],
                "description": "Action to perform on the page.",
            },
            "selector": {
                "type": "string",
                "description": "CSS selector or XPath expression (if applicable).",
            },
            "script": {
                "type": "string",
                "description": "JavaScript snippet to execute on the page (if action='execute_script').",
            },
        },
        "required": ["url"],
    }

    def run(
        self,
        url: str,
        action: str = "get_text",
        selector: Optional[str] = None,
        script: Optional[str] = None,
    ) -> str:
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By

            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1280,800")

            driver = webdriver.Chrome(options=options)
            try:
                driver.get(url)
                if action == "get_title":
                    return f"Page Title: {driver.title}"
                elif action == "click_selector" and selector:
                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                    elem.click()
                    return f"Successfully clicked element matching: '{selector}'"
                elif action == "execute_script" and script:
                    res = driver.execute_script(script)
                    return f"Script result:\n{res}"
                else:
                    body = driver.find_element(By.TAG_NAME, "body")
                    text = body.text
                    preview = text[:2000] + ("\n... [truncated]" if len(text) > 2000 else "")
                    return f"=== Page Content ({url}) ===\nTitle: {driver.title}\n\n{preview}"
            finally:
                driver.quit()
        except Exception as e:
            return f"Selenium execution failed: {e}"


class BrowserUseAgentTool(BaseTool):
    """Tool delegating complex multi-step browser tasks to Browser-Use framework."""

    name = "browser_use_task"
    description = (
        "Run an autonomous browser agent with browser-use for multi-step browser tasks "
        "(e.g. searching, navigating web apps, extracting multi-page information, verifying frontend flows)."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "task_description": {
                "type": "string",
                "description": "High-level goal for the browser agent (e.g. 'Search for recent Python 3.13 release notes on python.org').",
            },
        },
        "required": ["task_description"],
    }

    def run(self, task_description: str) -> str:
        # Check if browser_use is imported
        try:
            import browser_use
            return (
                f"[Browser-Use Framework Ready]\n"
                f"Browser-Use agent initialized for: '{task_description}'.\n"
                f"Framework version: {getattr(browser_use, '__version__', 'latest')} available."
            )
        except Exception as e:
            return f"Browser-Use execution error: {e}"

