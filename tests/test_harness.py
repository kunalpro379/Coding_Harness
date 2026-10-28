import pytest
from harness.core.types import Message, Role, TokenUsage, TodoItem, TodoStatus
from harness.tools.base import ToolRegistry, BaseTool
from harness.tools.filesystem import ReadFileTool, WriteFileTool, StrReplaceTool
from harness.tools.browser import clean_html_to_markdown, BrowserFetchTool
from harness.memory.trimmer import ContextTrimmer
from harness.tools.planner import PlannerState
from harness.mcp.client import MCPToolDefinition
from harness.agents.orchestrator import AgentOrchestrator


def test_message_serialization():
    msg = Message(role=Role.USER, content="Hello World")
    data = msg.to_dict()
    assert data["role"] == "user"
    assert data["content"] == "Hello World"


def test_token_usage_calculation():
    usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    assert usage.total_tokens == 150


def test_filesystem_tools(tmp_path):
    write_tool = WriteFileTool()
    read_tool = ReadFileTool()
    replace_tool = StrReplaceTool()

    test_file = tmp_path / "sample.py"
    write_tool.run(str(test_file), "def hello():\n    return 'world'\n")

    read_out = read_tool.run(str(test_file))
    assert "def hello():" in read_out

    replace_tool.run(str(test_file), "return 'world'", "return 'universe'")
    read_out2 = read_tool.run(str(test_file))
    assert "return 'universe'" in read_out2


def test_planner_state():
    items = [
        TodoItem(content="Task 1", active_form="Doing task 1", status=TodoStatus.DONE),
        TodoItem(content="Task 2", active_form="Doing task 2", status=TodoStatus.IN_PROGRESS),
        TodoItem(content="Task 3", active_form="Doing task 3", status=TodoStatus.PENDING),
    ]
    res = PlannerState.set_todos(items)
    assert "[x] Task 1" in res
    assert "[~] Task 2" in res
    assert "[ ] Task 3" in res
    assert PlannerState.active_action_form() == "Doing task 2"


def test_context_trimmer_cap():
    trimmer = ContextTrimmer(cap_chars=50, stub_chars=20)
    huge_text = "A" * 150
    capped = trimmer.cap(huge_text)
    assert len(capped) > 50
    assert "[output trimmed:" in capped
    trimmer.sweep()


def test_browser_html_cleaner():
    html = "<html><body><h1>Doc Title</h1><p>Sample text with <a href='https://example.com'>link</a></p></body></html>"
    md = clean_html_to_markdown(html)
    assert "### Doc Title" in md
    assert "[link](https://example.com)" in md


def test_mcp_tool_model():
    mcp_def = MCPToolDefinition(name="test_tool", description="A test tool", input_schema={"type": "object"})
    assert mcp_def.name == "test_tool"


def test_agent_orchestrator_initialization():
    orchestrator = AgentOrchestrator()
    registered_tools = [t.name for t in orchestrator.registry.list_tools()]
    assert "read_file" in registered_tools
    assert "write_file" in registered_tools
    assert "task" in registered_tools
    assert "research" in registered_tools
    assert "browser_fetch" in registered_tools
    assert "web_search" in registered_tools
