-- Demo Data: Kaffeeküche/Entwicklung Example
-- Demonstrates "Deny overrides Allow" pattern

-- Users
INSERT INTO users (user_id, name, email) VALUES
(1, 'Max Mustermann', 'max@company.com'),
(2, 'Anna Schmidt', 'anna@company.com'),
(3, 'Tom Hardware', 'tom@company.com'),
(4, 'Lisa Software', 'lisa@company.com'),
(5, 'Chef Boss', 'chef@company.com');

-- User Groups (hierarchical)
-- Alle Mitarbeiter
--   └── Entwicklung
--         ├── Hardware-Entwicklung
--         └── Software-Entwicklung
INSERT INTO groups (group_id, name, parent_id) VALUES
(1, 'Alle Mitarbeiter', NULL),
(2, 'Entwicklung', 1),
(3, 'Hardware-Entwicklung', 2),
(4, 'Software-Entwicklung', 2),
(5, 'Management', 1);

-- User to Group assignments
INSERT INTO user_groups (user_id, group_id) VALUES
(1, 2),  -- Max: Entwicklung (general)
(2, 2),  -- Anna: Entwicklung (general)
(3, 3),  -- Tom: Hardware-Entwicklung
(4, 4),  -- Lisa: Software-Entwicklung
(5, 5);  -- Chef: Management

-- Door Groups (hierarchical)
-- Gebäude
--   ├── Allgemeine Bereiche
--   │     ├── Kaffeeküche
--   │     └── Konferenzräume
--   └── Entwicklungsbereiche
--         ├── Hardware-Labor
--         │     └── Reinraum
--         └── Software-Bereich
--               └── Serverraum
INSERT INTO door_groups (dgroup_id, name, parent_id) VALUES
(1, 'Gebäude', NULL),
(2, 'Allgemeine Bereiche', 1),
(3, 'Kaffeeküche', 2),
(4, 'Konferenzräume', 2),
(5, 'Entwicklungsbereiche', 1),
(6, 'Hardware-Labor', 5),
(7, 'Reinraum', 6),
(8, 'Software-Bereich', 5),
(9, 'Serverraum', 8);

-- Doors
INSERT INTO doors (door_id, name, location) VALUES
(1, 'Haupteingang', 'EG'),
(2, 'Kaffeeküche Tür', 'EG'),
(3, 'Konferenzraum A', '1. OG'),
(4, 'Konferenzraum B', '1. OG'),
(5, 'HW-Labor Eingang', '2. OG'),
(6, 'HW-Labor Werkstatt', '2. OG'),
(7, 'Reinraum Schleuse', '2. OG'),
(8, 'SW-Bereich Eingang', '3. OG'),
(9, 'Dev-Office', '3. OG'),
(10, 'Serverraum', '3. OG');

-- Door to Door Group assignments
INSERT INTO door_in_group (door_id, dgroup_id) VALUES
(1, 1),   -- Haupteingang -> Gebäude
(2, 3),   -- Kaffeeküche Tür -> Kaffeeküche
(3, 4),   -- Konferenzraum A -> Konferenzräume
(4, 4),   -- Konferenzraum B -> Konferenzräume
(5, 6),   -- HW-Labor Eingang -> Hardware-Labor
(6, 6),   -- HW-Labor Werkstatt -> Hardware-Labor
(7, 7),   -- Reinraum Schleuse -> Reinraum
(8, 8),   -- SW-Bereich Eingang -> Software-Bereich
(9, 8),   -- Dev-Office -> Software-Bereich
(10, 9);  -- Serverraum -> Serverraum

-- PERMISSIONS

-- Allow Permissions
INSERT INTO allow_permissions (group_id, dgroup_id) VALUES
(1, 2),   -- Alle Mitarbeiter -> Allgemeine Bereiche (Kaffee, Konferenz)
(2, 5),   -- Entwicklung -> Entwicklungsbereiche (ALLE!)
(3, 6),   -- Hardware-Entwicklung -> Hardware-Labor
(4, 8),   -- Software-Entwicklung -> Software-Bereich
(5, 1);   -- Management -> Gebäude (alles)

-- Deny Permissions (THE MAGIC!)
-- Entwicklung (allgemein) darf NICHT in spezialisierte Bereiche
INSERT INTO deny_permissions (group_id, dgroup_id) VALUES
(2, 6),   -- Entwicklung -> Hardware-Labor DENY
(2, 8);   -- Entwicklung -> Software-Bereich DENY

-- Erklärung:
-- Max und Anna (Entwicklung allgemein) bekommen durch allow_permissions Zugang zu "Entwicklungsbereiche"
-- ABER: Die deny_permissions für Hardware-Labor und Software-Bereich überschreiben das!
-- Ergebnis: Sie dürfen in die Kaffeeküche, aber NICHT ins HW-Labor oder SW-Bereich
-- Tom (HW-Entwicklung) hat explizites Allow für HW-Labor -> überschreibt das Deny nicht,
-- aber er erbt es von Entwicklung... AUSSER er hat sein eigenes Allow
