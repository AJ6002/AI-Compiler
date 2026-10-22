# ADR-001: Language & Package Management — Python 3.12 and uv

## Status
Accepted

## Context
The AICONNEX Excel Compiler requires high-performance tabular manipulation, strict typing, and rapid, reproducible dependency locking across development, testing, and production environments.

## Decision
1. **Python 3.12:** Selected for modern type hint improvements (PEP 695 type parameter syntax), performance optimizations, and comprehensive ecosystem support for Arrow, Pydantic, and openpyxl.
2. **uv:** Selected as the package and environment manager. Replaces legacy pip/virtualenv setups with millisecond resolution, strict lockfile generation (`uv.lock`), and unified workspace execution (`uv run`).

## Consequences
- Fast, deterministic CI and local setup across Windows, macOS, and Linux.
- Zero dependency drift between developer machines and deployed containers.
