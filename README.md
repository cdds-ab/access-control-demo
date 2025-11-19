# Access Control System

A professional RBAC (Role-Based Access Control) system implementing the **"Deny overrides Allow"** pattern with hierarchical permission inheritance - a model commonly used in enterprise access control systems like Lenel OnGuard, Genetec Security Center, and Siemens SiPass.

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

**By default, everything is denied.** No Allow = no access.

When you grant an Allow to a door group, all its children are also allowed (inheritance down the tree). To restrict part of that tree, you add an explicit Deny, which also inherits down to its children.

### How It Works

1. **Default: Everything is denied**
   - Without any permissions, no user can access any door

2. **Allow opens a branch:**
   ```
   UserGroup → Allow DoorGroup1
   ```
   → DoorGroup1 and all its children are now accessible

3. **Deny cuts off a sub-branch:**
   ```
   UserGroup → Deny DoorGroup2 (child of DoorGroup1)
   ```
   → DoorGroup2 and its children are blocked again

4. **A new Allow can re-open deeper:**
   ```
   UserGroup → Allow DoorGroup3 (child of DoorGroup2)
   ```
   → DoorGroup3 is accessible again

Think of it as sculpting a tree: Allow opens branches, Deny cuts them off.

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

### Understanding Door Group Inheritance

*This explanation was contributed by a human who found it clearer than the technical documentation.*

Before understanding the full system, focus on just **one user group** and **door group hierarchy**:

```
Door Groups:
dg1 (Building)
└── dg2 (Office Area)
    └── dg3 (Server Room)
```

**Key insight:** Permissions flow DOWN the door group tree.

#### Allow-first approach

```
ug1 → Allow dg1
ug1 → Deny dg3
```

- Allow on dg1 automatically grants access to dg2 and dg3 (children)
- Deny on dg3 blocks only dg3

**Result:** ug1 can access dg1 ✅, dg2 ✅, dg3 ❌

#### Deny-first approach

```
ug1 → Deny dg1
ug1 → Allow dg2
```

- Deny on dg1 automatically blocks dg2 and dg3 (children)
- Allow on dg2 overrides the inherited Deny for dg2 **and its children**

**Result:** ug1 can access dg1 ❌, dg2 ✅, dg3 ✅

This is the foundation. The user group hierarchy (with Direct/Inherited rules) adds a second layer on top of this.

### When Do You Need User Group Hierarchy?

The system supports hierarchical user groups, but they're not always necessary.

#### Flat User Groups Suffice When:

- Groups are disjoint (Employees, Guests, Contractors)
- Few overlapping permissions

**Example with flat groups:**

```
User Groups (flat):     Door Groups (hierarchical):
- Employees             Building
- Guests                ├── Common Areas
                        │   ├── Coffee Kitchen
                        │   └── Meeting Rooms
                        └── Executive Floor

Permissions:
Employees → Allow: Building
Employees → Deny: Executive Floor
Guests → Allow: Meeting Rooms
```

Result: Employees access everything except Executive Floor. Guests only access Meeting Rooms.

#### Hierarchical User Groups Help When:

- Roles inherit from other roles (Executive Assistant inherits from Employee)
- Avoiding duplicate permission assignments

**Example with hierarchy:**

```
User Groups (hierarchical):
Employees
└── Executive Assistants

Permissions:
Employees → Allow: Building
Employees → Deny: Executive Floor
Executive Assistants → Allow: Executive Floor  (Direct Allow overrides Inherited Deny)
```

Result: Executive Assistants inherit all Employee permissions AND get Executive Floor access.

#### Design Recommendation

Structure your data based on:
1. **Building/physical layout** → Door group hierarchy
2. **Organizational structure** → User group hierarchy (if needed)

A flat user group structure is often sufficient. Use hierarchy only when inheritance genuinely reduces complexity. The system supports both approaches.

**Future feature idea:** Automatic analysis to suggest structure optimizations (e.g., "These 5 groups have identical permissions → merge?" or "This group could inherit from that one → save 12 rules").

### Best Practice: Optimizing Permission Count

Choose your strategy based on how many permissions a group needs:

| Group needs... | Strategy | Result |
|----------------|----------|--------|
| Many permissions (e.g., 47/50 doors) | **Allow-first, Deny explicit** | Fewer rules |
| Few permissions (e.g., 3/50 doors) | **Deny-first, Allow explicit** | Fewer rules |

#### Example: Interns (few permissions)

Instead of creating 47 individual Deny rules:

```
# Bad: 47+ rules
Interns → Allow: Door 1, 2, 3
Interns → Deny: Door 4, 5, 6, ... 50
```

Use Deny-first with explicit Allow:

```
# Good: 2 rules
Interns → Deny: Building (top-level door group)
Interns → Allow: Coffee Kitchen
```

Result: Interns can only access the Coffee Kitchen.

#### Example: Management (many permissions)

Instead of creating 47 individual Allow rules:

```
# Bad: 47 rules
Management → Allow: Door 1, 2, 3, ... 47
```

Use Allow-first with explicit Deny:

```
# Good: 4 rules
Management → Allow: Building (top-level door group)
Management → Deny: High-Security-Lab
Management → Deny: Vault
Management → Deny: Server-Room
```

Result: Management can access everything except the three restricted areas.

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

### Industry Context

This permission model follows patterns commonly found in enterprise physical access control systems:

- **Deny overrides Allow** at the same level (fail-safe default)
- **Direct permissions override inherited ones** (specificity wins)
- **Hierarchical inheritance** for both door groups and user groups

Similar approaches are documented in systems like Lenel OnGuard, Genetec Security Center, Siemens SiPass integrated, and others. The model also aligns with NIST SP 800-162 (ABAC) principles regarding explicit deny precedence.

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
