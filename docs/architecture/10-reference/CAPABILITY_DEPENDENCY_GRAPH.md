# EOP Capability Dependency Graph

Version: 1.0

---

# 1. Purpose

Dokumen ini menentukan dependency antar capability.

Digunakan untuk:

- menentukan urutan PR,
- mencegah architectural drift,
- menentukan prerequisite capability.

---

# 2. Capability Layers

Enterprise Capability
↑
Automation Capability
↑
Workflow Capability
↑
Operational Capability
↑
Domain Foundation
↑
Platform Foundation

---

# 3. Dependency Graph

Authentication
|

    v

Authorization Context
|

    +----------------+

    |                |

    v                v

Employee Context Permission Model
|

    v

Operational Capability
+-------------+-------------+-------------+
Leave Attendance Timesheet Overtime
|

    v

Approval Workflow
|

    v

Workflow History
|

    v

Notification
|

    v

Enterprise Integration

---

# 4. Capability Status

| Capability             | Status   |
| ---------------------- | -------- |
| Authentication         | Existing |
| Employee               | Existing |
| Organization           | Existing |
| Master Data            | Existing |
| Project                | Existing |
| Authorization          | Missing  |
| Approval Authorization | Missing  |
| Workflow History       | Missing  |
| Notification           | Missing  |
| Reporting Model        | Early    |
| Integration            | Missing  |

---

# 5. Critical Path

Primary:

Authentication
↓
Authorization Context
↓
Approval Authorization
↓
Workflow History

Secondary:

Leave Rules
↓
Leave Balance Engine
↓
Payroll Integration

---

# 6. Architectural Rule

Capability tidak boleh dibangun sebelum dependency-nya tersedia.

Contoh:

Tidak membangun:

- Notification sebelum Event/Workflow History
- Leave Engine sebelum Business Rule
- Integration sebelum stable domain boundary
