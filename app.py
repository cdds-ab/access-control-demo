#!/usr/bin/env python3
"""
Access Control Web Application
REST API for managing users, groups, doors, and permissions.
"""

from flask import Flask, request, jsonify, render_template_string
import sqlite3
import time
from pathlib import Path

app = Flask(__name__)

# Database paths
SMALL_DB = Path(__file__).parent / "access_control.db"
LARGE_DB = Path(__file__).parent / "access_control_large.db"

# Use large DB by default if it exists
DB_PATH = LARGE_DB if LARGE_DB.exists() else SMALL_DB

def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def get_user_doors(conn, user_id: int) -> tuple[list[dict], dict]:
    """Get all doors a user can access with timing."""
    timings = {}

    query = """
    WITH RECURSIVE
    direct_user_groups AS (
        SELECT group_id FROM user_groups WHERE user_id = ?
    ),
    all_user_groups AS (
        SELECT group_id FROM direct_user_groups
        UNION
        SELECT g.parent_id
        FROM groups g
        JOIN all_user_groups ug ON g.group_id = ug.group_id
        WHERE g.parent_id IS NOT NULL
    ),
    direct_allowed_dgroups AS (
        SELECT DISTINCT ap.dgroup_id
        FROM allow_permissions ap
        JOIN direct_user_groups dug ON ap.group_id = dug.group_id
    ),
    direct_allowed_expanded AS (
        SELECT dgroup_id FROM direct_allowed_dgroups
        UNION
        SELECT dg.dgroup_id
        FROM door_groups dg
        JOIN direct_allowed_expanded dae ON dg.parent_id = dae.dgroup_id
    ),
    inherited_denied_dgroups AS (
        SELECT DISTINCT dp.dgroup_id
        FROM deny_permissions dp
        JOIN all_user_groups aug ON dp.group_id = aug.group_id
        WHERE dp.group_id NOT IN (SELECT group_id FROM direct_user_groups)
    ),
    direct_denied_dgroups AS (
        SELECT DISTINCT dp.dgroup_id
        FROM deny_permissions dp
        JOIN direct_user_groups dug ON dp.group_id = dug.group_id
    ),
    inherited_denied_expanded AS (
        SELECT dgroup_id FROM inherited_denied_dgroups
        UNION
        SELECT dg.dgroup_id
        FROM door_groups dg
        JOIN inherited_denied_expanded ide ON dg.parent_id = ide.dgroup_id
    ),
    direct_denied_expanded AS (
        SELECT dgroup_id FROM direct_denied_dgroups
        UNION
        SELECT dg.dgroup_id
        FROM door_groups dg
        JOIN direct_denied_expanded dde ON dg.parent_id = dde.dgroup_id
    ),
    all_allowed_dgroups AS (
        SELECT DISTINCT ap.dgroup_id
        FROM allow_permissions ap
        JOIN all_user_groups aug ON ap.group_id = aug.group_id
    ),
    all_allowed_expanded AS (
        SELECT dgroup_id FROM all_allowed_dgroups
        UNION
        SELECT dg.dgroup_id
        FROM door_groups dg
        JOIN all_allowed_expanded aae ON dg.parent_id = aae.dgroup_id
    ),
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

    start = time.time()
    cursor = conn.execute(query, (user_id,))
    doors = [dict(row) for row in cursor.fetchall()]
    timings['query_ms'] = round((time.time() - start) * 1000, 3)
    timings['door_count'] = len(doors)

    return doors, timings

# HTML Template for the UI
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Access Control System</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #333; }
        .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .card h2 { margin-top: 0; color: #555; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        label { display: block; margin-bottom: 5px; font-weight: 500; }
        input, select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 10px; }
        button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0056b3; }
        button.danger { background: #dc3545; }
        button.danger:hover { background: #c82333; }
        button.success { background: #28a745; }
        .result { margin-top: 15px; padding: 15px; background: #f8f9fa; border-radius: 4px; max-height: 400px; overflow-y: auto; }
        .result pre { margin: 0; white-space: pre-wrap; font-size: 12px; }
        .timing { color: #6c757d; font-size: 12px; margin-top: 5px; }
        .status { padding: 5px 10px; border-radius: 4px; display: inline-block; }
        .status.granted { background: #d4edda; color: #155724; }
        .status.denied { background: #f8d7da; color: #721c24; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; }
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; }
        .tab { padding: 10px 20px; background: #e9ecef; border-radius: 4px; cursor: pointer; }
        .tab.active { background: #007bff; color: white; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Access Control System</h1>
        <p>Database: {{ db_name }} | Users: {{ stats.users }} | Doors: {{ stats.doors }} | Groups: {{ stats.groups }}</p>

        <div class="tabs">
            <div class="tab active" onclick="showTab('permissions')">Permissions</div>
            <div class="tab" onclick="showTab('assignments')">Assignments</div>
            <div class="tab" onclick="showTab('browse')">Browse Data</div>
        </div>

        <!-- Permissions Tab -->
        <div id="permissions" class="tab-content active">
            <div class="grid">
                <div class="card">
                    <h2>Check User Access</h2>
                    <label>User ID:</label>
                    <input type="number" id="user_id" value="1">
                    <button onclick="getUserDoors()">Get Accessible Doors</button>
                    <div id="user_doors_result" class="result"></div>
                </div>

                <div class="card">
                    <h2>Check Specific Access</h2>
                    <label>User ID:</label>
                    <input type="number" id="check_user_id" value="1">
                    <label>Door ID:</label>
                    <input type="number" id="check_door_id" value="1">
                    <button onclick="checkAccess()">Check Access</button>
                    <div id="access_result" class="result"></div>
                </div>
            </div>
        </div>

        <!-- Assignments Tab -->
        <div id="assignments" class="tab-content">
            <div class="grid">
                <div class="card">
                    <h2>Assign User to Group</h2>
                    <label>User ID:</label>
                    <input type="number" id="assign_user_id">
                    <label>Group ID:</label>
                    <input type="number" id="assign_group_id">
                    <button onclick="assignUserToGroup()">Assign</button>
                    <button class="danger" onclick="removeUserFromGroup()">Remove</button>
                    <div id="user_group_result" class="result"></div>
                </div>

                <div class="card">
                    <h2>Allow Permission</h2>
                    <label>Group ID:</label>
                    <input type="number" id="allow_group_id">
                    <label>Door Group ID:</label>
                    <input type="number" id="allow_dgroup_id">
                    <button class="success" onclick="addAllowPermission()">Add Allow</button>
                    <button class="danger" onclick="removeAllowPermission()">Remove</button>
                    <div id="allow_result" class="result"></div>
                </div>

                <div class="card">
                    <h2>Deny Permission</h2>
                    <label>Group ID:</label>
                    <input type="number" id="deny_group_id">
                    <label>Door Group ID:</label>
                    <input type="number" id="deny_dgroup_id">
                    <button class="danger" onclick="addDenyPermission()">Add Deny</button>
                    <button onclick="removeDenyPermission()">Remove</button>
                    <div id="deny_result" class="result"></div>
                </div>
            </div>
        </div>

        <!-- Browse Tab -->
        <div id="browse" class="tab-content">
            <div class="grid">
                <div class="card">
                    <h2>Users</h2>
                    <button onclick="loadUsers()">Load Users (first 50)</button>
                    <div id="users_list" class="result"></div>
                </div>

                <div class="card">
                    <h2>Groups</h2>
                    <button onclick="loadGroups()">Load Groups</button>
                    <div id="groups_list" class="result"></div>
                </div>

                <div class="card">
                    <h2>Door Groups</h2>
                    <button onclick="loadDoorGroups()">Load Door Groups</button>
                    <div id="dgroups_list" class="result"></div>
                </div>

                <div class="card">
                    <h2>Doors</h2>
                    <button onclick="loadDoors()">Load Doors (first 50)</button>
                    <div id="doors_list" class="result"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function showTab(tabId) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.querySelector(`[onclick="showTab('${tabId}')"]`).classList.add('active');
            document.getElementById(tabId).classList.add('active');
        }

        async function apiCall(url, method = 'GET', data = null) {
            const options = { method, headers: { 'Content-Type': 'application/json' } };
            if (data) options.body = JSON.stringify(data);
            const response = await fetch(url, options);
            return response.json();
        }

        async function getUserDoors() {
            const userId = document.getElementById('user_id').value;
            const result = await apiCall(`/api/users/${userId}/doors`);
            const div = document.getElementById('user_doors_result');
            if (result.error) {
                div.innerHTML = `<span style="color: red">${result.error}</span>`;
            } else {
                div.innerHTML = `
                    <strong>${result.user.name}</strong><br>
                    <span class="timing">Query: ${result.timing.query_ms}ms | Doors: ${result.door_count}</span>
                    <table>
                        <tr><th>ID</th><th>Name</th><th>Location</th></tr>
                        ${result.doors.slice(0, 20).map(d => `<tr><td>${d.door_id}</td><td>${d.name}</td><td>${d.location}</td></tr>`).join('')}
                        ${result.doors.length > 20 ? `<tr><td colspan="3">... and ${result.doors.length - 20} more</td></tr>` : ''}
                    </table>`;
            }
        }

        async function checkAccess() {
            const userId = document.getElementById('check_user_id').value;
            const doorId = document.getElementById('check_door_id').value;
            const result = await apiCall(`/api/check/${userId}/${doorId}`);
            const div = document.getElementById('access_result');
            const status = result.access_granted ? 'granted' : 'denied';
            const icon = result.access_granted ? '✅' : '❌';
            div.innerHTML = `
                <span class="status ${status}">${icon} ${status.toUpperCase()}</span>
                <span class="timing">Query: ${result.timing.query_ms}ms</span>
                <br><br>
                <strong>${result.user?.name || 'Unknown'}</strong> → <strong>${result.door?.name || 'Unknown'}</strong>`;
        }

        async function assignUserToGroup() {
            const userId = document.getElementById('assign_user_id').value;
            const groupId = document.getElementById('assign_group_id').value;
            const result = await apiCall('/api/user-groups', 'POST', { user_id: parseInt(userId), group_id: parseInt(groupId) });
            document.getElementById('user_group_result').innerHTML = `<pre>${JSON.stringify(result, null, 2)}</pre>`;
        }

        async function removeUserFromGroup() {
            const userId = document.getElementById('assign_user_id').value;
            const groupId = document.getElementById('assign_group_id').value;
            const result = await apiCall(`/api/user-groups/${userId}/${groupId}`, 'DELETE');
            document.getElementById('user_group_result').innerHTML = `<pre>${JSON.stringify(result, null, 2)}</pre>`;
        }

        async function addAllowPermission() {
            const groupId = document.getElementById('allow_group_id').value;
            const dgroupId = document.getElementById('allow_dgroup_id').value;
            const result = await apiCall('/api/permissions/allow', 'POST', { group_id: parseInt(groupId), dgroup_id: parseInt(dgroupId) });
            document.getElementById('allow_result').innerHTML = `<pre>${JSON.stringify(result, null, 2)}</pre>`;
        }

        async function removeAllowPermission() {
            const groupId = document.getElementById('allow_group_id').value;
            const dgroupId = document.getElementById('allow_dgroup_id').value;
            const result = await apiCall(`/api/permissions/allow/${groupId}/${dgroupId}`, 'DELETE');
            document.getElementById('allow_result').innerHTML = `<pre>${JSON.stringify(result, null, 2)}</pre>`;
        }

        async function addDenyPermission() {
            const groupId = document.getElementById('deny_group_id').value;
            const dgroupId = document.getElementById('deny_dgroup_id').value;
            const result = await apiCall('/api/permissions/deny', 'POST', { group_id: parseInt(groupId), dgroup_id: parseInt(dgroupId) });
            document.getElementById('deny_result').innerHTML = `<pre>${JSON.stringify(result, null, 2)}</pre>`;
        }

        async function removeDenyPermission() {
            const groupId = document.getElementById('deny_group_id').value;
            const dgroupId = document.getElementById('deny_dgroup_id').value;
            const result = await apiCall(`/api/permissions/deny/${groupId}/${dgroupId}`, 'DELETE');
            document.getElementById('deny_result').innerHTML = `<pre>${JSON.stringify(result, null, 2)}</pre>`;
        }

        async function loadUsers() {
            const result = await apiCall('/api/users?limit=50');
            document.getElementById('users_list').innerHTML = `
                <table><tr><th>ID</th><th>Name</th><th>Email</th></tr>
                ${result.map(u => `<tr><td>${u.user_id}</td><td>${u.name}</td><td>${u.email}</td></tr>`).join('')}
                </table>`;
        }

        async function loadGroups() {
            const result = await apiCall('/api/groups');
            document.getElementById('groups_list').innerHTML = `
                <table><tr><th>ID</th><th>Name</th><th>Parent</th></tr>
                ${result.map(g => `<tr><td>${g.group_id}</td><td>${g.name}</td><td>${g.parent_id || '-'}</td></tr>`).join('')}
                </table>`;
        }

        async function loadDoorGroups() {
            const result = await apiCall('/api/door-groups');
            document.getElementById('dgroups_list').innerHTML = `
                <table><tr><th>ID</th><th>Name</th><th>Parent</th></tr>
                ${result.map(g => `<tr><td>${g.dgroup_id}</td><td>${g.name}</td><td>${g.parent_id || '-'}</td></tr>`).join('')}
                </table>`;
        }

        async function loadDoors() {
            const result = await apiCall('/api/doors?limit=50');
            document.getElementById('doors_list').innerHTML = `
                <table><tr><th>ID</th><th>Name</th><th>Location</th></tr>
                ${result.map(d => `<tr><td>${d.door_id}</td><td>${d.name}</td><td>${d.location}</td></tr>`).join('')}
                </table>`;
        }
    </script>
</body>
</html>
"""

# Routes

@app.route('/')
def index():
    """Main UI."""
    conn = get_db()
    stats = {
        'users': conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        'doors': conn.execute("SELECT COUNT(*) FROM doors").fetchone()[0],
        'groups': conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0],
    }
    conn.close()
    return render_template_string(HTML_TEMPLATE, stats=stats, db_name=DB_PATH.name)

@app.route('/api/users')
def get_users():
    """List users."""
    limit = request.args.get('limit', 100, type=int)
    conn = get_db()
    users = [dict(row) for row in conn.execute(
        "SELECT * FROM users ORDER BY user_id LIMIT ?", (limit,)
    ).fetchall()]
    conn.close()
    return jsonify(users)

@app.route('/api/users/<int:user_id>')
def get_user(user_id):
    """Get user details."""
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    groups = [dict(row) for row in conn.execute("""
        SELECT g.* FROM groups g
        JOIN user_groups ug ON g.group_id = ug.group_id
        WHERE ug.user_id = ?
    """, (user_id,)).fetchall()]

    conn.close()
    return jsonify({"user": dict(user), "groups": groups})

@app.route('/api/users/<int:user_id>/doors')
def get_user_doors_api(user_id):
    """Get all doors a user can access."""
    conn = get_db()

    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    doors, timings = get_user_doors(conn, user_id)
    conn.close()

    return jsonify({
        "user": dict(user),
        "doors": doors,
        "door_count": len(doors),
        "timing": timings
    })

@app.route('/api/check/<int:user_id>/<int:door_id>')
def check_access(user_id, door_id):
    """Check if user can access door."""
    conn = get_db()

    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    door = conn.execute("SELECT * FROM doors WHERE door_id = ?", (door_id,)).fetchone()

    doors, timings = get_user_doors(conn, user_id)
    conn.close()

    granted = any(d['door_id'] == door_id for d in doors)

    return jsonify({
        "user": dict(user) if user else None,
        "door": dict(door) if door else None,
        "access_granted": granted,
        "timing": timings
    })

@app.route('/api/groups')
def get_groups():
    """List all groups."""
    conn = get_db()
    groups = [dict(row) for row in conn.execute(
        "SELECT * FROM groups ORDER BY group_id"
    ).fetchall()]
    conn.close()
    return jsonify(groups)

@app.route('/api/door-groups')
def get_door_groups():
    """List all door groups."""
    conn = get_db()
    dgroups = [dict(row) for row in conn.execute(
        "SELECT * FROM door_groups ORDER BY dgroup_id"
    ).fetchall()]
    conn.close()
    return jsonify(dgroups)

@app.route('/api/doors')
def get_doors():
    """List doors."""
    limit = request.args.get('limit', 100, type=int)
    conn = get_db()
    doors = [dict(row) for row in conn.execute(
        "SELECT * FROM doors ORDER BY door_id LIMIT ?", (limit,)
    ).fetchall()]
    conn.close()
    return jsonify(doors)

@app.route('/api/user-groups', methods=['POST'])
def assign_user_to_group():
    """Assign user to group."""
    data = request.json
    user_id = data.get('user_id')
    group_id = data.get('group_id')

    if not user_id or not group_id:
        return jsonify({"error": "user_id and group_id required"}), 400

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO user_groups (user_id, group_id) VALUES (?, ?)",
            (user_id, group_id)
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"User {user_id} assigned to group {group_id}"})
    except sqlite3.IntegrityError as e:
        conn.close()
        return jsonify({"error": str(e)}), 400

@app.route('/api/user-groups/<int:user_id>/<int:group_id>', methods=['DELETE'])
def remove_user_from_group(user_id, group_id):
    """Remove user from group."""
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM user_groups WHERE user_id = ? AND group_id = ?",
        (user_id, group_id)
    )
    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if deleted:
        return jsonify({"success": True, "message": f"User {user_id} removed from group {group_id}"})
    return jsonify({"error": "Assignment not found"}), 404

@app.route('/api/permissions/allow', methods=['POST'])
def add_allow_permission():
    """Add allow permission."""
    data = request.json
    group_id = data.get('group_id')
    dgroup_id = data.get('dgroup_id')

    if not group_id or not dgroup_id:
        return jsonify({"error": "group_id and dgroup_id required"}), 400

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO allow_permissions (group_id, dgroup_id) VALUES (?, ?)",
            (group_id, dgroup_id)
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"Allow permission added: group {group_id} -> door group {dgroup_id}"})
    except sqlite3.IntegrityError as e:
        conn.close()
        return jsonify({"error": str(e)}), 400

@app.route('/api/permissions/allow/<int:group_id>/<int:dgroup_id>', methods=['DELETE'])
def remove_allow_permission(group_id, dgroup_id):
    """Remove allow permission."""
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM allow_permissions WHERE group_id = ? AND dgroup_id = ?",
        (group_id, dgroup_id)
    )
    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if deleted:
        return jsonify({"success": True, "message": f"Allow permission removed"})
    return jsonify({"error": "Permission not found"}), 404

@app.route('/api/permissions/deny', methods=['POST'])
def add_deny_permission():
    """Add deny permission."""
    data = request.json
    group_id = data.get('group_id')
    dgroup_id = data.get('dgroup_id')

    if not group_id or not dgroup_id:
        return jsonify({"error": "group_id and dgroup_id required"}), 400

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO deny_permissions (group_id, dgroup_id) VALUES (?, ?)",
            (group_id, dgroup_id)
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"Deny permission added: group {group_id} -> door group {dgroup_id}"})
    except sqlite3.IntegrityError as e:
        conn.close()
        return jsonify({"error": str(e)}), 400

@app.route('/api/permissions/deny/<int:group_id>/<int:dgroup_id>', methods=['DELETE'])
def remove_deny_permission(group_id, dgroup_id):
    """Remove deny permission."""
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM deny_permissions WHERE group_id = ? AND dgroup_id = ?",
        (group_id, dgroup_id)
    )
    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if deleted:
        return jsonify({"success": True, "message": f"Deny permission removed"})
    return jsonify({"error": "Permission not found"}), 404

@app.route('/api/stats')
def get_stats():
    """Get database statistics."""
    conn = get_db()
    stats = {
        "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "groups": conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0],
        "doors": conn.execute("SELECT COUNT(*) FROM doors").fetchone()[0],
        "door_groups": conn.execute("SELECT COUNT(*) FROM door_groups").fetchone()[0],
        "user_groups": conn.execute("SELECT COUNT(*) FROM user_groups").fetchone()[0],
        "allow_permissions": conn.execute("SELECT COUNT(*) FROM allow_permissions").fetchone()[0],
        "deny_permissions": conn.execute("SELECT COUNT(*) FROM deny_permissions").fetchone()[0],
    }
    conn.close()
    return jsonify(stats)

if __name__ == '__main__':
    print(f"Using database: {DB_PATH}")
    print("Starting Access Control API on http://localhost:5000")
    app.run(debug=True, port=5000)
