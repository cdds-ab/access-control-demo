-- Access Control System with "Deny overrides Allow" Pattern
-- Gold-Standard 2025 for Professional Access Control & RBAC

PRAGMA foreign_keys = ON;

-- Users
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE
);

-- User Groups (hierarchical)
CREATE TABLE groups (
    group_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    parent_id INTEGER REFERENCES groups(group_id)
);

-- User to Group assignment
CREATE TABLE user_groups (
    user_id INTEGER REFERENCES users(user_id),
    group_id INTEGER REFERENCES groups(group_id),
    PRIMARY KEY (user_id, group_id)
);

-- Door Groups (hierarchical)
CREATE TABLE door_groups (
    dgroup_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    parent_id INTEGER REFERENCES door_groups(dgroup_id)
);

-- Doors
CREATE TABLE doors (
    door_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    location TEXT
);

-- Door to Door Group assignment
CREATE TABLE door_in_group (
    door_id INTEGER REFERENCES doors(door_id),
    dgroup_id INTEGER REFERENCES door_groups(dgroup_id),
    PRIMARY KEY (door_id, dgroup_id)
);

-- Allow Permissions (normal permissions)
CREATE TABLE allow_permissions (
    group_id INTEGER REFERENCES groups(group_id),
    dgroup_id INTEGER REFERENCES door_groups(dgroup_id),
    PRIMARY KEY (group_id, dgroup_id)
);

-- Deny Permissions (override allow, highest priority)
CREATE TABLE deny_permissions (
    group_id INTEGER REFERENCES groups(group_id),
    dgroup_id INTEGER REFERENCES door_groups(dgroup_id),
    PRIMARY KEY (group_id, dgroup_id)
);

-- Indexes for performance
CREATE INDEX idx_groups_parent ON groups(parent_id);
CREATE INDEX idx_door_groups_parent ON door_groups(dgroup_id);
CREATE INDEX idx_user_groups_user ON user_groups(user_id);
CREATE INDEX idx_door_in_group_dgroup ON door_in_group(dgroup_id);
