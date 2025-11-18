#!/usr/bin/env python3
"""
Access Control System with "Deny overrides Allow" Pattern
Gold-Standard 2025 for Professional Access Control & RBAC
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "access_control.db"

def init_db():
    """Initialize database with schema and demo data."""
    conn = sqlite3.connect(DB_PATH)

    # Load schema
    schema_path = Path(__file__).parent / "schema.sql"
    conn.executescript(schema_path.read_text())

    # Load demo data
    data_path = Path(__file__).parent / "demo_data.sql"
    conn.executescript(data_path.read_text())

    conn.commit()
    conn.close()
    print(f"Database initialized: {DB_PATH}")

def get_user_doors(user_id: int) -> list[dict]:
    """
    Get all doors a user can access using "Deny overrides Allow" pattern.

    This is the core query that implements the gold-standard RBAC pattern:
    1. Collect all user groups (including inherited)
    2. Collect explicit denies (highest priority)
    3. Collect allows and expand transitively to child door groups
    4. Expand denies transitively to child door groups
    5. Final result = allowed - denied
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    query = """
    WITH RECURSIVE

    -- 1. All groups the user belongs to (direct membership only)
    direct_user_groups AS (
        SELECT group_id FROM user_groups WHERE user_id = ?
    ),

    -- 2. All groups including inherited parent groups
    all_user_groups AS (
        SELECT group_id FROM direct_user_groups
        UNION
        SELECT g.parent_id
        FROM groups g
        JOIN all_user_groups ug ON g.group_id = ug.group_id
        WHERE g.parent_id IS NOT NULL
    ),

    -- 3. Direct allows from user's DIRECT groups (highest priority)
    direct_allowed_dgroups AS (
        SELECT DISTINCT ap.dgroup_id
        FROM allow_permissions ap
        JOIN direct_user_groups dug ON ap.group_id = dug.group_id
    ),

    -- 4. Expand direct allows to child door groups
    direct_allowed_expanded AS (
        SELECT dgroup_id FROM direct_allowed_dgroups
        UNION
        SELECT dg.dgroup_id
        FROM door_groups dg
        JOIN direct_allowed_expanded dae ON dg.parent_id = dae.dgroup_id
    ),

    -- 5. Denies from inherited groups (NOT from direct groups)
    inherited_denied_dgroups AS (
        SELECT DISTINCT dp.dgroup_id
        FROM deny_permissions dp
        JOIN all_user_groups aug ON dp.group_id = aug.group_id
        WHERE dp.group_id NOT IN (SELECT group_id FROM direct_user_groups)
    ),

    -- 6. Denies from direct groups (apply to all)
    direct_denied_dgroups AS (
        SELECT DISTINCT dp.dgroup_id
        FROM deny_permissions dp
        JOIN direct_user_groups dug ON dp.group_id = dug.group_id
    ),

    -- 7. Expand inherited denies to child door groups
    inherited_denied_expanded AS (
        SELECT dgroup_id FROM inherited_denied_dgroups
        UNION
        SELECT dg.dgroup_id
        FROM door_groups dg
        JOIN inherited_denied_expanded ide ON dg.parent_id = ide.dgroup_id
    ),

    -- 8. Expand direct denies to child door groups
    direct_denied_expanded AS (
        SELECT dgroup_id FROM direct_denied_dgroups
        UNION
        SELECT dg.dgroup_id
        FROM door_groups dg
        JOIN direct_denied_expanded dde ON dg.parent_id = dde.dgroup_id
    ),

    -- 9. All allows from all groups (for inherited permissions)
    all_allowed_dgroups AS (
        SELECT DISTINCT ap.dgroup_id
        FROM allow_permissions ap
        JOIN all_user_groups aug ON ap.group_id = aug.group_id
    ),

    -- 10. Expand all allows
    all_allowed_expanded AS (
        SELECT dgroup_id FROM all_allowed_dgroups
        UNION
        SELECT dg.dgroup_id
        FROM door_groups dg
        JOIN all_allowed_expanded aae ON dg.parent_id = aae.dgroup_id
    ),

    -- 11. Final calculation:
    -- Direct allows override inherited denies
    -- Direct denies always apply
    -- Inherited allows minus inherited denies
    final_dgroups AS (
        -- Direct allows always win (unless direct deny)
        SELECT dgroup_id FROM direct_allowed_expanded
        WHERE dgroup_id NOT IN (SELECT dgroup_id FROM direct_denied_expanded)
        UNION
        -- Inherited allows minus all denies (when no direct allow overrides)
        SELECT dgroup_id FROM all_allowed_expanded
        WHERE dgroup_id NOT IN (SELECT dgroup_id FROM direct_allowed_expanded)
        AND dgroup_id NOT IN (SELECT dgroup_id FROM inherited_denied_expanded)
        AND dgroup_id NOT IN (SELECT dgroup_id FROM direct_denied_expanded)
    )

    SELECT DISTINCT d.door_id, d.name, d.location
    FROM doors d
    JOIN door_in_group dig ON d.door_id = dig.door_id
    JOIN final_dgroups fd ON dig.dgroup_id = fd.dgroup_id
    ORDER BY d.name;
    """

    cursor = conn.execute(query, (user_id,))
    doors = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return doors

def check_access(user_id: int, door_id: int) -> dict:
    """Check if a specific user can access a specific door."""
    doors = get_user_doors(user_id)
    door_ids = [d['door_id'] for d in doors]

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Get user and door info
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    door = conn.execute("SELECT * FROM doors WHERE door_id = ?", (door_id,)).fetchone()
    conn.close()

    if not user or not door:
        return {"error": "User or door not found"}

    return {
        "user": dict(user),
        "door": dict(door),
        "access_granted": door_id in door_ids,
        "reason": "Deny overrides Allow pattern"
    }

def get_all_users_access() -> dict:
    """Get access matrix for all users."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    users = conn.execute("SELECT * FROM users ORDER BY name").fetchall()
    conn.close()

    result = {}
    for user in users:
        doors = get_user_doors(user['user_id'])
        result[user['name']] = {
            "user_id": user['user_id'],
            "email": user['email'],
            "accessible_doors": [d['name'] for d in doors],
            "door_count": len(doors)
        }

    return result

def explain_access(user_id: int) -> dict:
    """Explain why a user has certain access (for debugging/auditing)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Get user info
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not user:
        return {"error": "User not found"}

    # Get user's groups
    groups = conn.execute("""
        SELECT g.group_id, g.name
        FROM groups g
        JOIN user_groups ug ON g.group_id = ug.group_id
        WHERE ug.user_id = ?
    """, (user_id,)).fetchall()

    # Get allows
    allows = conn.execute("""
        SELECT g.name as group_name, dg.name as dgroup_name
        FROM allow_permissions ap
        JOIN groups g ON ap.group_id = g.group_id
        JOIN door_groups dg ON ap.dgroup_id = dg.dgroup_id
        JOIN user_groups ug ON g.group_id = ug.group_id
        WHERE ug.user_id = ?
    """, (user_id,)).fetchall()

    # Get denies
    denies = conn.execute("""
        SELECT g.name as group_name, dg.name as dgroup_name
        FROM deny_permissions dp
        JOIN groups g ON dp.group_id = g.group_id
        JOIN door_groups dg ON dp.dgroup_id = dg.dgroup_id
        JOIN user_groups ug ON g.group_id = ug.group_id
        WHERE ug.user_id = ?
    """, (user_id,)).fetchall()

    conn.close()

    doors = get_user_doors(user_id)

    return {
        "user": dict(user),
        "member_of_groups": [dict(g) for g in groups],
        "allow_rules": [dict(a) for a in allows],
        "deny_rules": [dict(d) for d in denies],
        "final_access": [d['name'] for d in doors]
    }

def main():
    """Demo the access control system."""
    # Initialize if DB doesn't exist
    if not DB_PATH.exists():
        init_db()

    print("=" * 60)
    print("ACCESS CONTROL DEMO - Deny Overrides Allow Pattern")
    print("=" * 60)

    # Show all users access
    print("\n📊 ACCESS MATRIX FOR ALL USERS:\n")
    access_matrix = get_all_users_access()

    for name, data in access_matrix.items():
        print(f"👤 {name}:")
        print(f"   Doors: {', '.join(data['accessible_doors']) or 'None'}")
        print()

    # Detailed explanation for Max (general Entwicklung)
    print("\n" + "=" * 60)
    print("🔍 DETAILED EXPLANATION: Max Mustermann (Entwicklung)")
    print("=" * 60)
    explanation = explain_access(1)
    print(json.dumps(explanation, indent=2, ensure_ascii=False))

    # Detailed explanation for Tom (Hardware-Entwicklung)
    print("\n" + "=" * 60)
    print("🔍 DETAILED EXPLANATION: Tom Hardware (Hardware-Entwicklung)")
    print("=" * 60)
    explanation = explain_access(3)
    print(json.dumps(explanation, indent=2, ensure_ascii=False))

    # Check specific access
    print("\n" + "=" * 60)
    print("🚪 ACCESS CHECK EXAMPLES")
    print("=" * 60)

    # Max trying to access Kaffeeküche (should work)
    result = check_access(1, 2)
    print(f"\nMax -> Kaffeeküche: {'✅ GRANTED' if result['access_granted'] else '❌ DENIED'}")

    # Max trying to access Serverraum (should fail)
    result = check_access(1, 10)
    print(f"Max -> Serverraum: {'✅ GRANTED' if result['access_granted'] else '❌ DENIED'}")

    # Lisa trying to access Serverraum (should work)
    result = check_access(4, 10)
    print(f"Lisa -> Serverraum: {'✅ GRANTED' if result['access_granted'] else '❌ DENIED'}")

    # Tom trying to access HW-Labor (should work)
    result = check_access(3, 5)
    print(f"Tom -> HW-Labor: {'✅ GRANTED' if result['access_granted'] else '❌ DENIED'}")

if __name__ == "__main__":
    main()
