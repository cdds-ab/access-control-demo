#!/usr/bin/env python3
"""
Demo program to fetch permissions from the access control system.
Supports both small demo DB and large test DB.
"""

import sqlite3
import json
import time
import argparse
from pathlib import Path

# Database paths
SMALL_DB = Path(__file__).parent / "access_control.db"
LARGE_DB = Path(__file__).parent / "access_control_large.db"

def get_connection(use_large: bool = False):
    """Get database connection."""
    db_path = LARGE_DB if use_large else SMALL_DB
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        print("Run 'python3 access_control.py' or 'python3 generate_testdata.py' first.")
        exit(1)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_user_doors(conn, user_id: int) -> tuple[list[dict], dict]:
    """
    Get all doors a user can access using "Deny overrides Allow" pattern.
    Direct allows override inherited denies.

    Returns: (doors, timing_info)
    """
    timings = {}

    query = """
    WITH RECURSIVE

    -- 1. Direct group memberships
    direct_user_groups AS (
        SELECT group_id FROM user_groups WHERE user_id = ?
    ),

    -- 2. All groups including parents
    all_user_groups AS (
        SELECT group_id FROM direct_user_groups
        UNION
        SELECT g.parent_id
        FROM groups g
        JOIN all_user_groups ug ON g.group_id = ug.group_id
        WHERE g.parent_id IS NOT NULL
    ),

    -- 3. Direct allows (highest priority)
    direct_allowed_dgroups AS (
        SELECT DISTINCT ap.dgroup_id
        FROM allow_permissions ap
        JOIN direct_user_groups dug ON ap.group_id = dug.group_id
    ),

    -- 4. Expand direct allows to children
    direct_allowed_expanded AS (
        SELECT dgroup_id FROM direct_allowed_dgroups
        UNION
        SELECT dg.dgroup_id
        FROM door_groups dg
        JOIN direct_allowed_expanded dae ON dg.parent_id = dae.dgroup_id
    ),

    -- 5. Inherited denies
    inherited_denied_dgroups AS (
        SELECT DISTINCT dp.dgroup_id
        FROM deny_permissions dp
        JOIN all_user_groups aug ON dp.group_id = aug.group_id
        WHERE dp.group_id NOT IN (SELECT group_id FROM direct_user_groups)
    ),

    -- 6. Direct denies
    direct_denied_dgroups AS (
        SELECT DISTINCT dp.dgroup_id
        FROM deny_permissions dp
        JOIN direct_user_groups dug ON dp.group_id = dug.group_id
    ),

    -- 7. Expand inherited denies
    inherited_denied_expanded AS (
        SELECT dgroup_id FROM inherited_denied_dgroups
        UNION
        SELECT dg.dgroup_id
        FROM door_groups dg
        JOIN inherited_denied_expanded ide ON dg.parent_id = ide.dgroup_id
    ),

    -- 8. Expand direct denies
    direct_denied_expanded AS (
        SELECT dgroup_id FROM direct_denied_dgroups
        UNION
        SELECT dg.dgroup_id
        FROM door_groups dg
        JOIN direct_denied_expanded dde ON dg.parent_id = dde.dgroup_id
    ),

    -- 9. All allows
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

    -- 11. Final: direct allows win over inherited denies
    final_dgroups AS (
        SELECT dgroup_id FROM direct_allowed_expanded
        WHERE dgroup_id NOT IN (SELECT dgroup_id FROM direct_denied_expanded)
        UNION
        SELECT dgroup_id FROM all_allowed_expanded
        WHERE dgroup_id NOT IN (SELECT dgroup_id FROM direct_allowed_expanded)
        AND dgroup_id NOT IN (SELECT dgroup_id FROM inherited_denied_expanded)
        AND dgroup_id NOT IN (SELECT dgroup_id FROM direct_denied_expanded)
    )

    SELECT DISTINCT d.door_id, d.name, d.location
    FROM doors d
    JOIN door_in_group dig ON d.door_id = dig.door_id
    JOIN final_dgroups fd ON dig.dgroup_id = fd.dgroup_id
    ORDER BY d.door_id;
    """

    # Total query time
    start_total = time.time()
    cursor = conn.execute(query, (user_id,))
    doors = [dict(row) for row in cursor.fetchall()]
    timings['total_ms'] = (time.time() - start_total) * 1000

    # Get detailed timing with EXPLAIN QUERY PLAN (optional debug info)
    timings['door_count'] = len(doors)

    return doors, timings

def check_access(conn, user_id: int, door_id: int) -> tuple[bool, dict]:
    """Quick check if user can access a specific door."""
    doors, timings = get_user_doors(conn, user_id)
    granted = any(d['door_id'] == door_id for d in doors)
    return granted, timings

def get_user_info(conn, user_id: int) -> dict | None:
    """Get user information."""
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return dict(row) if row else None

def get_user_groups(conn, user_id: int) -> list[dict]:
    """Get groups a user belongs to."""
    query = """
        SELECT g.group_id, g.name
        FROM groups g
        JOIN user_groups ug ON g.group_id = ug.group_id
        WHERE ug.user_id = ?
        ORDER BY g.name
    """
    return [dict(row) for row in conn.execute(query, (user_id,)).fetchall()]

def list_users(conn, limit: int = 20) -> list[dict]:
    """List users."""
    query = "SELECT * FROM users ORDER BY user_id LIMIT ?"
    return [dict(row) for row in conn.execute(query, (limit,)).fetchall()]

def list_doors(conn, limit: int = 20) -> list[dict]:
    """List doors."""
    query = "SELECT * FROM doors ORDER BY door_id LIMIT ?"
    return [dict(row) for row in conn.execute(query, (limit,)).fetchall()]

def get_stats(conn) -> dict:
    """Get database statistics."""
    return {
        "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "groups": conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0],
        "doors": conn.execute("SELECT COUNT(*) FROM doors").fetchone()[0],
        "door_groups": conn.execute("SELECT COUNT(*) FROM door_groups").fetchone()[0],
        "allow_permissions": conn.execute("SELECT COUNT(*) FROM allow_permissions").fetchone()[0],
        "deny_permissions": conn.execute("SELECT COUNT(*) FROM deny_permissions").fetchone()[0],
    }

def benchmark(conn, num_queries: int = 100):
    """Benchmark permission queries with detailed timing."""
    # Get random user IDs
    user_ids = [row[0] for row in conn.execute(
        f"SELECT user_id FROM users ORDER BY RANDOM() LIMIT {num_queries}"
    ).fetchall()]

    print(f"\nBenchmarking {num_queries} permission queries...")

    start = time.time()
    total_doors = 0
    all_timings = []
    min_time = float('inf')
    max_time = 0

    for user_id in user_ids:
        doors, timings = get_user_doors(conn, user_id)
        total_doors += len(doors)
        query_time = timings['total_ms']
        all_timings.append(query_time)
        min_time = min(min_time, query_time)
        max_time = max(max_time, query_time)

    elapsed = time.time() - start

    # Calculate percentiles
    sorted_timings = sorted(all_timings)
    p50 = sorted_timings[len(sorted_timings) // 2]
    p95 = sorted_timings[int(len(sorted_timings) * 0.95)]
    p99 = sorted_timings[int(len(sorted_timings) * 0.99)]
    avg_time = sum(all_timings) / len(all_timings)

    print(f"\n{'='*50}")
    print("BENCHMARK RESULTS")
    print(f"{'='*50}")
    print(f"Total queries:     {num_queries:,}")
    print(f"Total time:        {elapsed:.3f}s")
    print(f"Queries/second:    {num_queries/elapsed:.1f}")
    print(f"Avg doors/user:    {total_doors/num_queries:.1f}")
    print(f"\n{'Query Timing':^50}")
    print(f"{'-'*50}")
    print(f"Min:               {min_time:.2f}ms")
    print(f"Max:               {max_time:.2f}ms")
    print(f"Average:           {avg_time:.2f}ms")
    print(f"Median (p50):      {p50:.2f}ms")
    print(f"p95:               {p95:.2f}ms")
    print(f"p99:               {p99:.2f}ms")

def main():
    parser = argparse.ArgumentParser(description="Access Control Demo")
    parser.add_argument("--large", action="store_true", help="Use large test database")
    parser.add_argument("--user", type=int, help="Get permissions for user ID")
    parser.add_argument("--check", nargs=2, type=int, metavar=("USER", "DOOR"),
                        help="Check if user can access door")
    parser.add_argument("--list-users", type=int, nargs="?", const=20, metavar="N",
                        help="List N users (default 20)")
    parser.add_argument("--list-doors", type=int, nargs="?", const=20, metavar="N",
                        help="List N doors (default 20)")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--benchmark", type=int, nargs="?", const=100, metavar="N",
                        help="Benchmark N queries (default 100)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    conn = get_connection(args.large)

    try:
        if args.stats:
            stats = get_stats(conn)
            if args.json:
                print(json.dumps(stats, indent=2))
            else:
                print("\nDatabase Statistics:")
                for k, v in stats.items():
                    print(f"  {k}: {v:,}")

        elif args.user:
            user = get_user_info(conn, args.user)
            if not user:
                print(f"User {args.user} not found")
                return

            groups = get_user_groups(conn, args.user)

            doors, timings = get_user_doors(conn, args.user)

            result = {
                "user": user,
                "groups": groups,
                "accessible_doors": doors,
                "door_count": len(doors),
                "timing": {
                    "query_ms": round(timings['total_ms'], 3)
                }
            }

            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(f"\nUser: {user['name']} ({user['email']})")
                print(f"Groups: {', '.join(g['name'] for g in groups)}")
                print(f"Accessible doors: {len(doors)}")
                print(f"Query time: {timings['total_ms']:.3f}ms")
                if len(doors) <= 50:
                    print("\nDoors:")
                    for d in doors:
                        print(f"  - {d['name']} ({d['location']})")
                else:
                    print(f"\nFirst 10 doors:")
                    for d in doors[:10]:
                        print(f"  - {d['name']} ({d['location']})")
                    print(f"  ... and {len(doors)-10} more")

        elif args.check:
            user_id, door_id = args.check
            granted, timings = check_access(conn, user_id, door_id)

            user = get_user_info(conn, user_id)
            door = conn.execute("SELECT * FROM doors WHERE door_id = ?", (door_id,)).fetchone()

            result = {
                "user_id": user_id,
                "door_id": door_id,
                "access_granted": granted,
                "timing": {
                    "query_ms": round(timings['total_ms'], 3)
                }
            }

            if args.json:
                print(json.dumps(result, indent=2))
            else:
                user_name = user['name'] if user else f"User {user_id}"
                door_name = door['name'] if door else f"Door {door_id}"
                status = "✅ GRANTED" if granted else "❌ DENIED"
                print(f"\n{user_name} -> {door_name}: {status}")
                print(f"Query time: {timings['total_ms']:.3f}ms")

        elif args.list_users:
            users = list_users(conn, args.list_users)
            if args.json:
                print(json.dumps(users, indent=2, ensure_ascii=False))
            else:
                print(f"\nUsers (first {args.list_users}):")
                for u in users:
                    print(f"  {u['user_id']}: {u['name']} ({u['email']})")

        elif args.list_doors:
            doors = list_doors(conn, args.list_doors)
            if args.json:
                print(json.dumps(doors, indent=2, ensure_ascii=False))
            else:
                print(f"\nDoors (first {args.list_doors}):")
                for d in doors:
                    print(f"  {d['door_id']}: {d['name']} ({d['location']})")

        elif args.benchmark:
            benchmark(conn, args.benchmark)

        else:
            # Default: show stats and sample query
            stats = get_stats(conn)
            print("\nAccess Control Demo")
            print("=" * 40)
            print(f"Database: {'LARGE' if args.large else 'SMALL'}")
            for k, v in stats.items():
                print(f"  {k}: {v:,}")

            print("\nUsage examples:")
            print("  python3 demo_fetch.py --user 1")
            print("  python3 demo_fetch.py --check 1 5")
            print("  python3 demo_fetch.py --large --benchmark 1000")
            print("  python3 demo_fetch.py --large --user 42 --json")

    finally:
        conn.close()

if __name__ == "__main__":
    main()
