# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-06

### Added
- High-density x86 Windows application container runtime with Wine and TigerVNC.
- Copy-on-Write (COW) Wine prefix manager reducing storage overhead to <600 KB per session.
- FastAPI-based session orchestrator with dynamic cgroup memory guard admission control.
- Transparent bidirectional clipboard synchronization bridge (`novnc_bridge.js`).
- Headless print spool watcher and virtual CUPS-PDF Ghostscript generation.
- Hardened Kubernetes manifests (Deployment, Service, ConfigMap, Ingress) with non-root security context.
- Unit test suite covering session management, token validation, and memory guard.
- Automated CI pipeline (Python 3.10, 3.11, 3.12) and Bandit SAST security scan workflow.
