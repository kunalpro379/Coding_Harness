"""Code Knowledge Graph (GraphRAG) powered by NetworkX and Python AST parsing.

Constructs an in-memory directed dependency graph across the codebase:
- File imports (who imports what)
- Function/Class definitions and callers
- Blast radius analysis (what files/modules break if file X is modified)
Enables structural navigation and impact analysis with 0 context token bloat.
"""

import ast
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import networkx as nx
from ..core.config import settings
from ..tools.base import BaseTool

logger = logging.getLogger(__name__)


class CodeKnowledgeGraph:
    """Directed Knowledge Graph representing codebase topology, imports, and symbol dependencies."""

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or settings.workspace_root
        self.graph = nx.DiGraph()
        self.indexed_files: Set[str] = set()

    def build_graph(self):
        """Index all python files in the workspace and build import dependency edges."""
        self.graph.clear()
        self.indexed_files.clear()

        for py_path in self.root_dir.rglob("*.py"):
            # Skip virtualenvs, git, cache
            if any(part in py_path.parts for part in {".git", ".venv", "__pycache__", "site-packages"}):
                continue

            rel_path = str(py_path.relative_to(self.root_dir)).replace("\\", "/")
            self.indexed_files.add(rel_path)
            self.graph.add_node(rel_path, node_type="file", path=str(py_path))

            try:
                content = py_path.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content, filename=str(py_path))
                self._extract_dependencies(rel_path, tree)
            except Exception as e:
                logger.debug(f"Failed to parse AST for {rel_path}: {e}")

    def _extract_dependencies(self, source_file: str, tree: ast.AST):
        """Parse imports, classes, and top-level functions."""
        for node in ast.walk(tree):
            # 1. Direct imports: import harness.core.types
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imp_mod = alias.name.replace(".", "/") + ".py"
                    self.graph.add_edge(source_file, imp_mod, relation="imports")

            # 2. From imports: from ..core.types import Message
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imp_mod = node.module.replace(".", "/") + ".py"
                    self.graph.add_edge(source_file, imp_mod, relation="imports_from")
                    for alias in node.names:
                        self.graph.add_edge(source_file, f"{imp_mod}::{alias.name}", relation="uses_symbol")

            # 3. Class definitions
            elif isinstance(node, ast.ClassDef):
                symbol_id = f"{source_file}::{node.name}"
                self.graph.add_node(symbol_id, node_type="class", name=node.name)
                self.graph.add_edge(source_file, symbol_id, relation="defines")

            # 4. Function definitions
            elif isinstance(node, ast.FunctionDef):
                symbol_id = f"{source_file}::{node.name}"
                self.graph.add_node(symbol_id, node_type="function", name=node.name)
                self.graph.add_edge(source_file, symbol_id, relation="defines")

    def get_blast_radius(self, target_path: str) -> List[str]:
        """Find all files that depend directly or transitively on this target path."""
        target_norm = target_path.replace("\\", "/")
        matches = [n for n in self.graph.nodes if target_norm in n]
        if not matches:
            return []

        affected = set()
        for node in matches:
            # Predecessors in directed graph = components that depend on `node`
            predecessors = nx.ancestors(self.graph, node)
            for p in predecessors:
                if self.graph.nodes[p].get("node_type") == "file":
                    affected.add(p)
        return sorted(list(affected))

    def get_dependencies(self, target_path: str) -> List[str]:
        """Find what this target path imports or depends upon."""
        target_norm = target_path.replace("\\", "/")
        matches = [n for n in self.graph.nodes if target_norm in n]
        if not matches:
            return []

        deps = set()
        for node in matches:
            successors = nx.descendants(self.graph, node)
            for s in successors:
                deps.add(s)
        return sorted(list(deps))

    def summarize_topology(self) -> Dict[str, Any]:
        return {
            "total_files": len(self.indexed_files),
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
        }


default_code_graph = CodeKnowledgeGraph()


class QueryCodeGraphTool(BaseTool):
    """Tool allowing agents to query codebase dependencies and blast radius."""

    name = "query_code_graph"
    description = (
        "Query the Code Knowledge Graph (GraphRAG) using NetworkX. "
        "Allows analyzing what files import a target module, finding symbol definitions, "
        "or calculating the 'blast radius' (which files might break if you modify a file)."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "File path (e.g. 'harness/core/types.py') or symbol name to inspect.",
            },
            "query_type": {
                "type": "string",
                "enum": ["blast_radius", "dependencies", "topology"],
                "description": "'blast_radius' (who depends on this), 'dependencies' (what this needs), or 'topology' (overall repo graph stats).",
            },
        },
        "required": ["query_type"],
    }

    def __init__(self, graph: Optional[CodeKnowledgeGraph] = None):
        self.graph = graph or default_code_graph

    def run(self, query_type: str, target: Optional[str] = None) -> str:
        if self.graph.graph.number_of_nodes() == 0:
            self.graph.build_graph()

        if query_type == "topology":
            stats = self.graph.summarize_topology()
            return f"=== Codebase Graph Topology ===\nIndexed Files: {stats['total_files']}\nTotal Nodes (Files + Symbols): {stats['total_nodes']}\nDependency Edges: {stats['total_edges']}"

        if not target:
            return "Error: 'target' parameter is required for blast_radius and dependencies queries."

        if query_type == "blast_radius":
            affected = self.graph.get_blast_radius(target)
            if not affected:
                return f"Blast radius for '{target}': No dependent files found (leaf module or unindexed)."
            return f"=== Blast Radius for '{target}' (Modifying this may impact {len(affected)} files) ===\n" + "\n".join(f" - {f}" for f in affected)

        elif query_type == "dependencies":
            deps = self.graph.get_dependencies(target)
            if not deps:
                return f"Dependencies for '{target}': No outbound dependencies found."
            return f"=== Dependencies for '{target}' ({len(deps)} components) ===\n" + "\n".join(f" - {d}" for d in deps[:25])
        return "Invalid query_type specified."

