#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class RouteSpec:
    method: str
    path: str
    handler_name: str
    request_model: str | None
    response_model: str | None
    description: str


@dataclass
class ModelSpec:
    name: str
    fields: list[tuple[str, str]]


def expr_to_text(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def normalize_type(type_text: str) -> str:
    return (
        type_text.replace(" | None", " (optional)")
        .replace("None | ", "")
        .replace("dict[str, Any]", "object")
        .replace("list[dict[str, Any]]", "array<object>")
        .replace("list", "array")
    )


def extract_models(module: ast.Module) -> dict[str, ModelSpec]:
    models: dict[str, ModelSpec] = {}
    for node in module.body:
        if not isinstance(node, ast.ClassDef):
            continue
        is_basemodel = any(expr_to_text(base).endswith("BaseModel") for base in node.bases)
        if not is_basemodel:
            continue
        fields: list[tuple[str, str]] = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                fields.append((item.target.id, normalize_type(expr_to_text(item.annotation))))
        models[node.name] = ModelSpec(name=node.name, fields=fields)
    return models


def first_docstring(func: ast.FunctionDef) -> str:
    return ast.get_docstring(func) or ""


def infer_description(path: str, handler_name: str, docstring: str) -> str:
    if docstring:
        return " ".join(docstring.strip().split())
    manual = {
        "/rag/query": "Receive a question and return retrieval results such as prompt, contexts, token estimate, and metadata without final answer generation.",
        "/rag/answer": "Receive a question, retrieve relevant contexts, and generate the final grounded answer with supporting metadata.",
        "/v1/models": "Return the list of configured models through an OpenAI-compatible models endpoint.",
        "/v1/chat/completions": "Provide an OpenAI-compatible chat completions endpoint for OpenWebUI and compatible clients.",
        "/health": "Return service health status for monitoring, deployment checks, and troubleshooting.",
        "/debug/config": "Return selected runtime configuration values for debugging when the debug endpoint is enabled.",
    }
    if path in manual:
        return manual[path]
    return handler_name.replace("_", " ").strip().capitalize()


def extract_request_model(func: ast.FunctionDef) -> str | None:
    for arg in func.args.args:
        if arg.arg in {"self", "cls"}:
            continue
        ann = expr_to_text(arg.annotation)
        if ann:
            return ann
    return None


def extract_routes(module: ast.Module) -> list[RouteSpec]:
    routes: list[RouteSpec] = []
    for node in module.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            func = dec.func
            if not isinstance(func, ast.Attribute):
                continue
            if not isinstance(func.value, ast.Name) or func.value.id != "app":
                continue
            method = func.attr.upper()
            if method not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
                continue
            path = ""
            if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                path = dec.args[0].value
            response_model = None
            for kw in dec.keywords:
                if kw.arg == "response_model":
                    response_model = expr_to_text(kw.value)
            request_model = extract_request_model(node)
            routes.append(
                RouteSpec(
                    method=method,
                    path=path,
                    handler_name=node.name,
                    request_model=request_model,
                    response_model=response_model,
                    description=infer_description(path, node.name, first_docstring(node)),
                )
            )
    return routes


def markdown_for_models(models: dict[str, ModelSpec], names: list[str]) -> str:
    out: list[str] = []
    for name in names:
        spec = models.get(name)
        if not spec:
            continue
        out.append(f"### `{name}`")
        out.append("")
        out.append("| Field | Type |")
        out.append("|---|---|")
        for field_name, field_type in spec.fields:
            out.append(f"| `{field_name}` | `{field_type}` |")
        out.append("")
    return "\n".join(out).rstrip() + ("\n" if out else "")


def build_markdown(source: Path, routes: list[RouteSpec], models: dict[str, ModelSpec]) -> str:
    lines: list[str] = []
    lines.append("# Back-end API Specification")
    lines.append("")
    lines.append(f"Generated from `{source}`.")
    lines.append("")
    lines.append("## Routes")
    lines.append("")
    lines.append("| Route | Description | Method | Request Model | Response Model |")
    lines.append("|---|---|---|---|---|")
    for route in routes:
        lines.append(
            f"| `{route.path}` | {route.description} | `{route.method}` | "
            f"`{route.request_model or '-'}` | `{route.response_model or '-'}` |"
        )
    lines.append("")
    lines.append("## Request/Response Models")
    lines.append("")
    ordered_names: list[str] = []
    for route in routes:
        if route.request_model and route.request_model not in ordered_names and route.request_model in models:
            ordered_names.append(route.request_model)
        if route.response_model and route.response_model not in ordered_names and route.response_model in models:
            ordered_names.append(route.response_model)
    lines.append(markdown_for_models(models, ordered_names).rstrip())
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export FastAPI route and schema documentation as Markdown.")
    parser.add_argument(
        "--source",
        default="services/rag-service/app/main.py",
        help="Path to the FastAPI source file.",
    )
    parser.add_argument(
        "--output",
        default="out/api_spec.md",
        help="Output Markdown path.",
    )
    args = parser.parse_args()

    source = Path(args.source)
    module = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    routes = extract_routes(module)
    models = extract_models(module)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_markdown(source, routes, models), encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
