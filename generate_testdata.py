#!/usr/bin/env python3
"""
Generate large-scale test data for access control system.
Creates 10,000 users, 1,000 doors, and 100-200 groups with realistic hierarchies.
"""

import sqlite3
import random
from pathlib import Path

DB_PATH = Path(__file__).parent / "access_control_large.db"

def generate_large_testdata():
    """Generate test data with 10k users, 1k doors, 100-200 groups."""

    # Remove existing DB
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)

    # Load schema
    schema_path = Path(__file__).parent / "schema.sql"
    conn.executescript(schema_path.read_text())

    print("Generating test data...")

    # Configuration
    NUM_USERS = 10000
    NUM_DOORS = 1000
    NUM_USER_GROUPS = 150  # 100-200 range
    NUM_DOOR_GROUPS = 120

    # Generate User Groups (hierarchical)
    print(f"Creating {NUM_USER_GROUPS} user groups...")
    user_groups = []

    # Top-level departments
    departments = [
        "Engineering", "Sales", "Marketing", "HR", "Finance",
        "Operations", "Legal", "IT", "Support", "Management"
    ]

    group_id = 1
    for dept in departments:
        user_groups.append((group_id, dept, None))
        parent_id = group_id
        group_id += 1

        # Sub-departments (2-3 levels deep)
        for i in range(random.randint(8, 15)):
            sub_name = f"{dept}-Team-{i+1}"
            user_groups.append((group_id, sub_name, parent_id))
            sub_parent = group_id
            group_id += 1

            # Sub-sub teams
            for j in range(random.randint(0, 3)):
                subsub_name = f"{sub_name}-Unit-{j+1}"
                user_groups.append((group_id, subsub_name, sub_parent))
                group_id += 1

                if group_id >= NUM_USER_GROUPS:
                    break
            if group_id >= NUM_USER_GROUPS:
                break
        if group_id >= NUM_USER_GROUPS:
            break

    conn.executemany(
        "INSERT INTO groups (group_id, name, parent_id) VALUES (?, ?, ?)",
        user_groups
    )

    # Generate Door Groups (hierarchical)
    print(f"Creating {NUM_DOOR_GROUPS} door groups...")
    door_groups = []

    # Buildings/Floors structure
    buildings = ["Building-A", "Building-B", "Building-C", "Building-D", "Building-E"]

    dgroup_id = 1
    for building in buildings:
        door_groups.append((dgroup_id, building, None))
        building_id = dgroup_id
        dgroup_id += 1

        # Floors
        for floor in range(1, 6):
            floor_name = f"{building}-Floor-{floor}"
            door_groups.append((dgroup_id, floor_name, building_id))
            floor_id = dgroup_id
            dgroup_id += 1

            # Areas on each floor
            areas = ["Office", "Lab", "Storage", "Meeting", "Common"]
            for area in areas:
                area_name = f"{floor_name}-{area}"
                door_groups.append((dgroup_id, area_name, floor_id))
                dgroup_id += 1

                if dgroup_id >= NUM_DOOR_GROUPS:
                    break
            if dgroup_id >= NUM_DOOR_GROUPS:
                break
        if dgroup_id >= NUM_DOOR_GROUPS:
            break

    conn.executemany(
        "INSERT INTO door_groups (dgroup_id, name, parent_id) VALUES (?, ?, ?)",
        door_groups
    )

    # Generate Users
    print(f"Creating {NUM_USERS} users...")
    first_names = ["Max", "Anna", "Tom", "Lisa", "Peter", "Sarah", "Mike", "Emma", "John", "Maria"]
    last_names = ["Mueller", "Schmidt", "Weber", "Fischer", "Meyer", "Wagner", "Becker", "Schulz", "Koch", "Richter"]

    users = []
    for i in range(1, NUM_USERS + 1):
        first = random.choice(first_names)
        last = random.choice(last_names)
        name = f"{first} {last} {i}"
        email = f"user{i}@company.com"
        users.append((i, name, email))

    conn.executemany(
        "INSERT INTO users (user_id, name, email) VALUES (?, ?, ?)",
        users
    )

    # Generate User-Group assignments (each user in 1-3 groups)
    print("Assigning users to groups...")
    user_group_assignments = []
    all_group_ids = [g[0] for g in user_groups]

    for user_id in range(1, NUM_USERS + 1):
        num_groups = random.randint(1, 3)
        assigned_groups = random.sample(all_group_ids, min(num_groups, len(all_group_ids)))
        for gid in assigned_groups:
            user_group_assignments.append((user_id, gid))

    conn.executemany(
        "INSERT OR IGNORE INTO user_groups (user_id, group_id) VALUES (?, ?)",
        user_group_assignments
    )

    # Generate Doors
    print(f"Creating {NUM_DOORS} doors...")
    door_types = ["Main", "Side", "Emergency", "Service", "Lab", "Office", "Storage", "Server"]

    doors = []
    for i in range(1, NUM_DOORS + 1):
        door_type = random.choice(door_types)
        name = f"{door_type}-Door-{i}"
        location = f"Location-{i % 100}"
        doors.append((i, name, location))

    conn.executemany(
        "INSERT INTO doors (door_id, name, location) VALUES (?, ?, ?)",
        doors
    )

    # Assign doors to door groups
    print("Assigning doors to door groups...")
    door_group_assignments = []
    all_dgroup_ids = [dg[0] for dg in door_groups]

    for door_id in range(1, NUM_DOORS + 1):
        # Each door in 1-2 door groups
        num_dgroups = random.randint(1, 2)
        assigned_dgroups = random.sample(all_dgroup_ids, min(num_dgroups, len(all_dgroup_ids)))
        for dgid in assigned_dgroups:
            door_group_assignments.append((door_id, dgid))

    conn.executemany(
        "INSERT OR IGNORE INTO door_in_group (door_id, dgroup_id) VALUES (?, ?)",
        door_group_assignments
    )

    # Generate Allow Permissions
    print("Creating allow permissions...")
    allow_permissions = []

    # Each user group gets access to 3-10 door groups
    for group_id in all_group_ids:
        num_allows = random.randint(3, 10)
        allowed_dgroups = random.sample(all_dgroup_ids, min(num_allows, len(all_dgroup_ids)))
        for dgid in allowed_dgroups:
            allow_permissions.append((group_id, dgid))

    conn.executemany(
        "INSERT OR IGNORE INTO allow_permissions (group_id, dgroup_id) VALUES (?, ?)",
        allow_permissions
    )

    # Generate Deny Permissions (sparse - only 5-10% of groups have denies)
    print("Creating deny permissions...")
    deny_permissions = []

    # About 10% of groups have deny rules
    groups_with_denies = random.sample(all_group_ids, len(all_group_ids) // 10)

    for group_id in groups_with_denies:
        num_denies = random.randint(1, 3)
        denied_dgroups = random.sample(all_dgroup_ids, min(num_denies, len(all_dgroup_ids)))
        for dgid in denied_dgroups:
            deny_permissions.append((group_id, dgid))

    conn.executemany(
        "INSERT OR IGNORE INTO deny_permissions (group_id, dgroup_id) VALUES (?, ?)",
        deny_permissions
    )

    conn.commit()

    # Print statistics
    stats = {
        "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "groups": conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0],
        "user_groups": conn.execute("SELECT COUNT(*) FROM user_groups").fetchone()[0],
        "doors": conn.execute("SELECT COUNT(*) FROM doors").fetchone()[0],
        "door_groups": conn.execute("SELECT COUNT(*) FROM door_groups").fetchone()[0],
        "door_in_group": conn.execute("SELECT COUNT(*) FROM door_in_group").fetchone()[0],
        "allow_permissions": conn.execute("SELECT COUNT(*) FROM allow_permissions").fetchone()[0],
        "deny_permissions": conn.execute("SELECT COUNT(*) FROM deny_permissions").fetchone()[0],
    }

    conn.close()

    print("\n" + "=" * 50)
    print("TEST DATA GENERATED")
    print("=" * 50)
    for key, value in stats.items():
        print(f"{key}: {value:,}")
    print(f"\nDatabase: {DB_PATH}")

    return stats

if __name__ == "__main__":
    generate_large_testdata()
