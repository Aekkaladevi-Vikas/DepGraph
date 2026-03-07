"""
parser.py — Uses Python's built-in AST module to extract
imports, classes, functions, and calls from a .py file.
No code is executed — purely static analysis.
"""

import ast
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ParsedModule:
    """All extracted information from a single Python file."""
    filepath: Path
    module_name: str                    # e.g. "payments.processor"
    imports: List[str] = field(default_factory=list)        # modules imported
    from_imports: List[str] = field(default_factory=list)   # from X import Y
    classes: List[str] = field(default_factory=list)        # class definitions
    functions: List[str] = field(default_factory=list)      # top-level functions
    calls: List[str] = field(default_factory=list)          # function/method calls
    errors: List[str] = field(default_factory=list)         # parse errors


def filepath_to_module(filepath: Path, root: Path) -> str:
    """
    Convert a file path to a dotted module name.
    e.g. /project/payments/processor.py -> payments.processor
    """
    try:
        relative = filepath.relative_to(root)
        parts = list(relative.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts) if parts else filepath.stem
    except ValueError:
        return filepath.stem


def parse_file(filepath: Path, root: Path) -> ParsedModule:
    """
    Parse a single Python file and extract all dependency information.

    Args:
        filepath: Absolute path to the .py file.
        root:     Root of the project (for module naming).

    Returns:
        ParsedModule with all extracted symbols.
    """
    module_name = filepath_to_module(filepath, root)
    result = ParsedModule(filepath=filepath, module_name=module_name)

    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as e:
        result.errors.append(f"SyntaxError: {e}")
        return result
    except Exception as e:
        result.errors.append(f"ParseError: {e}")
        return result

    for node in ast.walk(tree):

        # import os, sys
        if isinstance(node, ast.Import):
            for alias in node.names:
                result.imports.append(alias.name)

        # from pathlib import Path  OR  from . import utils  OR  from ..models import User
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            level  = node.level or 0   # 0=absolute, 1=., 2=..

            if level > 0:
                # Relative import — resolve against current module's package
                parts = module_name.split(".")
                # Go up 'level' levels
                base_parts = parts[:max(0, len(parts) - level)]
                if module:
                    base_parts.append(module)
                base = ".".join(base_parts)
                for alias in node.names:
                    if alias.name == "*":
                        result.from_imports.append(base)
                    else:
                        full = f"{base}.{alias.name}" if base else alias.name
                        result.from_imports.append(full)
            else:
                # Absolute import
                for alias in node.names:
                    if alias.name == "*":
                        result.from_imports.append(module)
                    else:
                        full = f"{module}.{alias.name}" if module else alias.name
                        result.from_imports.append(full)

        # class MyClass:
        elif isinstance(node, ast.ClassDef):
            qualified = f"{module_name}.{node.name}"
            result.classes.append(qualified)

            # Methods inside the class
            for item in node.body:
                if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                    result.functions.append(f"{qualified}.{item.name}")

        # def my_function():  (top-level only)
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            # Only add if it's a top-level function (not inside a class)
            result.functions.append(f"{module_name}.{node.name}")

        # Function calls: foo() or obj.method()
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                result.calls.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                result.calls.append(node.func.attr)

    return result


def parse_project(py_files: List[Path], root: Path) -> List[ParsedModule]:
    """
    Parse all Python files in the project.

    Args:
        py_files: List of .py file paths from crawler.
        root:     Project root for module naming.

    Returns:
        List of ParsedModule objects.
    """
    modules = []
    for filepath in py_files:
        parsed = parse_file(filepath, root)
        modules.append(parsed)
    return modules