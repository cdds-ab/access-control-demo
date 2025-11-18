# Access Control System

A professional RBAC (Role-Based Access Control) system implementing the **"Deny overrides Allow"** pattern - the gold standard in enterprise access control systems (Siemens SiPass, Lenel OnGuard, Genetec, Dormakaba).

## Quick Start

```bash
# 1. Generate test data (10,000 users, 1,000 doors)
python3 generate_testdata.py

# 2. Start the web application
python3 app.py

# 3. Open browser at http://localhost:5000
```

The web application provides:
- **Permissions Tab**: Query which doors a user can access, check specific user-door combinations
- **Assignments Tab**: Assign users to groups, add/remove Allow and Deny permissions
- **Browse Tab**: View all users, groups, door groups, and doors in the system

All queries display timing information (query duration in milliseconds).

### Alternative: CLI Tool

```bash
# Query user permissions
python3 demo_fetch.py --large --user 42

# Check if user 42 can access door 100
python3 demo_fetch.py --large --check 42 100

# Run performance benchmark
python3 demo_fetch.py --large --benchmark 1000
```

## Architecture

### Data Model

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐
│   Users     │────▶│ User Groups │────▶│ Allow/Deny Perms │
└─────────────┘     └─────────────┘     └──────────────────┘
                          │                      │
                          ▼                      ▼
                    ┌───────────┐         ┌─────────────┐
                    │  Groups   │         │ Door Groups │
                    │(hierarchy)│         │ (hierarchy) │
                    └───────────┘         └─────────────┘
                                                │
                                                ▼
                                          ┌─────────┐
                                          │  Doors  │
                                          └─────────┘
```

### Database Schema

```sql
-- Users
users (user_id, name, email)

-- User Groups (hierarchical via parent_id)
groups (group_id, name, parent_id)

-- User to Group assignment (many-to-many)
user_groups (user_id, group_id)

-- Door Groups (hierarchical via parent_id)
door_groups (dgroup_id, name, parent_id)

-- Doors
doors (door_id, name, location)

-- Door to Door Group assignment
door_in_group (door_id, dgroup_id)

-- Allow Permissions (Group -> Door Group)
allow_permissions (group_id, dgroup_id)

-- Deny Permissions (Group -> Door Group) - HIGHEST PRIORITY
deny_permissions (group_id, dgroup_id)
```

## The Gold Standard: "Deny Overrides Allow"

### Core Principle

In professional access control systems, explicit **Deny rules always take precedence** over Allow rules. This ensures security by default - if there's any doubt, access is denied.

### Permission Resolution Rules

1. **Direct Allow overrides Inherited Deny**: If a user's direct group has an explicit Allow for a door group, it overrides Deny rules inherited from parent groups
2. **Direct Deny always applies**: Deny rules on a user's direct group always take effect
3. **Inherited permissions propagate down**: Both Allow and Deny permissions cascade to child door groups
4. **Deny wins on conflict**: When both Allow and Deny apply at the same level, Deny wins

### Example: Coffee Kitchen Scenario

```
User Groups:                    Door Groups:
─────────────                   ─────────────
Entwicklung (Development)       Entwicklungsbereiche (Dev Areas)
├── Hardware-Entwicklung        ├── Hardware-Labor
│                               │   └── Reinraum
└── Software-Entwicklung        └── Software-Bereich
                                    └── Serverraum

Allgemeine Bereiche (Common)
├── Kaffeeküche (Coffee Kitchen)
└── Konferenzräume
```

**Permissions:**
- `Entwicklung` → Allow `Entwicklungsbereiche` (all dev areas)
- `Entwicklung` → Deny `Hardware-Labor`
- `Entwicklung` → Deny `Software-Bereich`
- `Hardware-Entwicklung` → Allow `Hardware-Labor`
- `Software-Entwicklung` → Allow `Software-Bereich`

**Result:**
- Max (in `Entwicklung`): ✅ Coffee Kitchen, ❌ HW-Labor, ❌ SW-Bereich
- Tom (in `Hardware-Entwicklung`): ✅ Coffee Kitchen, ✅ HW-Labor, ❌ SW-Bereich
- Lisa (in `Software-Entwicklung`): ✅ Coffee Kitchen, ❌ HW-Labor, ✅ SW-Bereich

The inherited Deny from `Entwicklung` is overridden by the direct Allow on the specialized groups.

### SQL Query Implementation

The core access check uses recursive CTEs to:

1. Collect all user groups (direct + inherited via hierarchy)
2. Collect direct allows and expand to child door groups
3. Collect inherited denies and expand to child door groups
4. Collect direct denies and expand to child door groups
5. Calculate final access: `(Direct Allows - Direct Denies) ∪ (All Allows - All Denies)`

See `access_control.py` for the complete implementation.

## Performance

Tested with 10,000 users, 1,000 doors, 150 groups:

| Metric | Value |
|--------|-------|
| Queries/second | ~480 |
| Average query time | ~2ms |
| Median (p50) | ~2ms |
| p95 | ~2.7ms |
| p99 | ~3ms |

## Usage

### Setup

```bash
# Generate large test dataset
python3 generate_testdata.py

# Or use small demo dataset
python3 access_control.py
```

### CLI Demo Tool

```bash
# Get user permissions
python3 demo_fetch.py --large --user 42

# Check specific access
python3 demo_fetch.py --large --check 42 100

# Benchmark performance
python3 demo_fetch.py --large --benchmark 1000

# JSON output
python3 demo_fetch.py --large --user 42 --json

# Database stats
python3 demo_fetch.py --large --stats
```

### Web Application

```bash
python3 app.py
# Open http://localhost:5000
```

**REST API Endpoints:**

```bash
# Permissions
GET /api/users/{id}/doors     # Get accessible doors for user
GET /api/check/{user}/{door}  # Check specific access

# Data browsing
GET /api/users?limit=50
GET /api/groups
GET /api/door-groups
GET /api/doors?limit=50
GET /api/stats

# Assignments
POST   /api/user-groups                    # Assign user to group
DELETE /api/user-groups/{user}/{group}     # Remove assignment

# Allow Permissions
POST   /api/permissions/allow              # Add allow rule
DELETE /api/permissions/allow/{group}/{dgroup}

# Deny Permissions
POST   /api/permissions/deny               # Add deny rule
DELETE /api/permissions/deny/{group}/{dgroup}
```

## Files

| File | Description |
|------|-------------|
| `schema.sql` | Database schema |
| `demo_data.sql` | Small demo dataset (Coffee Kitchen example) |
| `generate_testdata.py` | Generate large test dataset (10k users, 1k doors) |
| `access_control.py` | Core library with permission query |
| `demo_fetch.py` | CLI tool for fetching permissions |
| `app.py` | Flask web application with REST API |

## Why This Pattern?

### Industry Standard
- Siemens SiPass, Lenel OnGuard, Genetec, AMAG, Kaba/dormakaba
- NIST RBAC Standard
- ISO 27001 recommendations

### Benefits
- **Security by default**: Deny always wins on conflict
- **Auditable**: Clear trace of which rule caused denial
- **Scalable**: Hierarchical groups reduce permission explosion
- **Flexible**: Direct allows can override inherited denies for specialized roles

### Alternatives (and why they're worse)

| Pattern | Problem |
|---------|---------|
| Allow-only | Can't restrict inherited permissions |
| Inheritance blocking | Complex, hard to audit |
| Priority numbers | Confusing, error-prone |

## License

MIT
