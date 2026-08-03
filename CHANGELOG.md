# Changelog

All notable changes to **Windows Developer MCP** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-03

### Added
- **Dual-Profile Provider Registry Architecture**:
  - `MINIMAL`, `DEVELOPER`, and `FULL` execution profiles to balance Glama quality with Local LLM context efficiency.
  - Dynamic meta-tools: `mcp_search_tools`, `mcp_list_profiles`, `mcp_enable_provider`.
  - Dynamic `register()`, `unregister()`, and `lazy_load()` capability negotiation.
- **Enhanced AI Project Analysis Suite (`providers/project.py`)**:
  - `project_analyze`: Comprehensive workspace tech stack detection.
  - `project_dependencies`: Cross-language dependency tree inspection.
  - `project_summarize`: Hierarchical file tree generator.
  - `project_architecture`: Component topology and design pattern discovery.
  - `project_generate_readme`: Automated README draft builder.
  - `project_generate_docs`: AST-based docstring extraction and API documentation generator.
  - `project_security_scan`: Static analysis scan for hardcoded credentials and unsafe constructs.
  - `project_generate_tests`: Automated pytest skeleton code generator.
- **Security Hardening**:
  - `security/rate_limiter.py` sliding-window execution limiter.
  - Comprehensive path traversal normalization and workspace sandbox enforcement.
- **Repository Infrastructure & Glama Indexing**:
  - `glama.json` manifest.
  - `.github/workflows/ci.yml` GitHub Actions pipeline for `uv`, `ruff`, `basedpyright`, and `pytest`.
  - Complete documentation suite under `docs/`.
