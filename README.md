<!-- ============================================================ -->

<!--                         EOP README                           -->

<!-- ============================================================ -->

<p align="center">
  <img src="assets/banner.png" alt="Enterprise Operations Platform Banner" width="100%">
</p>

<h1 align="center">
Enterprise Operations Platform
</h1>

<p align="center">
<strong>Build enterprise software once. Reuse it everywhere.</strong>
</p>

<p align="center">
A modular, API-first backend platform built with FastAPI, PostgreSQL, Redis, and MinIO.
</p>

<p align="center">

![Python](https://img.shields.io/badge/Python-3.13+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-success?style=for-the-badge)
![CI](https://img.shields.io/badge/CI-Passing-brightgreen?style=for-the-badge)
![Coverage](https://img.shields.io/badge/Coverage-100%25-green?style=for-the-badge)

</p>

---

# Overview

Enterprise Operations Platform (EOP) is a modular backend platform designed for building enterprise applications using reusable business modules and shared infrastructure.

Instead of repeatedly implementing authentication, authorization, storage, auditing, dashboards, and search in every project, EOP provides these capabilities as platform foundations that every module can reuse.

The result is a scalable architecture that enables teams to build enterprise systems faster while maintaining consistency across the platform.

---

# Features

| Business Modules | Platform Foundations |
| ---------------- | -------------------- |
| Organizations    | Authentication       |
| Projects         | RBAC                 |
| Employees        | Dashboard            |
| Assignments      | Pagination           |
| Tasks            | Search               |
| _(More coming)_  | Audit Log            |
|                  | File Storage         |
|                  | Repository Pattern   |
|                  | Unit of Work         |

---

# Architecture

<p align="center">

<img src="assets/architecture.svg" width="900">

</p>

---

# Module Ecosystem

| Module          | Status      |
| --------------- | ----------- |
| Organizations   | ✅ Complete |
| Projects        | ✅ Complete |
| Employees       | ✅ Complete |
| Assignments     | ✅ Complete |
| Tasks           | ✅ Complete |
| Authentication  | ✅ Complete |
| RBAC            | ✅ Complete |
| Dashboard       | ✅ Complete |
| Pagination      | ✅ Complete |
| Search          | ✅ Complete |
| Audit Log       | ✅ Complete |
| File Storage    | ✅ Complete |
| Background Jobs | 🚧 Planned  |
| Notifications   | 🚧 Planned  |
| API Versioning  | 🚧 Planned  |
| SDK Generation  | 🚧 Planned  |

---

# Quick Start

Clone the repository.

```bash
git clone <repository-url>
cd Enterprise-Operations-Platform-EOP
```

Start the development environment.

```bash
docker compose up --build
```

Run database migrations.

```bash
alembic upgrade head
```

Run the test suite.

```bash
pytest
```

---

# Screenshots

> Screenshots and animated GIFs will be added once the frontend becomes available.

```
assets/screenshots/

├── dashboard.png
├── organizations.png
├── projects.png
├── tasks.png
└── demo.gif
```

---

# Documentation

Detailed documentation is available inside the **docs/** directory.

| Document                | Description             |
| ----------------------- | ----------------------- |
| docs/getting-started.md | Installation & setup    |
| docs/architecture.md    | System architecture     |
| docs/development.md     | Development workflow    |
| docs/modules.md         | Business modules        |
| docs/api.md             | API conventions         |
| docs/contributing.md    | Contribution guidelines |
| docs/roadmap.md         | Product roadmap         |

---

# Development Workflow

```text
Feature Branch
      │
Implementation
      │
Tests
      │
Ruff
      │
MyPy
      │
Technical Review
      │
Pull Request
      │
Merge
```

---

# Roadmap

## ✅ Completed

- Docker Infrastructure
- PostgreSQL Integration
- Repository Pattern
- Unit of Work
- Authentication
- RBAC
- Dashboard
- Pagination
- Search
- Audit Log
- File Storage
- Core Business Modules

## 🚧 In Progress

- Background Jobs Foundation

## 📌 Planned

- Notification Framework
- API Versioning
- SDK Generation
- Workflow Engine
- Reporting Engine
- Frontend
- Mobile

---

# Contributing

We welcome contributions that follow the project's architecture and engineering standards.

Before opening a Pull Request:

- Keep changes focused.
- Add tests.
- Run Ruff.
- Run MyPy.
- Ensure the entire test suite passes.

---

# License

Released under the MIT License.
