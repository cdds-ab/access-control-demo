# Project Context: Access Control System

## Project Overview

A Python-based RBAC (Role-Based Access Control) system implementing the **"Deny overrides Allow"** pattern with hierarchical permission inheritance.

## Current State

- **Status**: Initial development, documentation improved
- **Branch**: `main`
- **Git Status**: Modified (README updates)

## Technology Stack

- **Language**: Python 3
- **Database**: SQLite
- **Web Framework**: Flask
- **Pattern**: Deny-overrides-Allow with hierarchical inheritance

## Key Components

| File | Purpose |
|------|---------|
| `schema.sql` | Database schema definition |
| `demo_data.sql` | Small demo dataset (Coffee Kitchen example) |
| `generate_testdata.py` | Large test dataset generator (10k users, 1k doors) |
| `access_control.py` | Core library with permission queries |
| `demo_fetch.py` | CLI tool for fetching permissions |
| `app.py` | Flask web application with REST API |

## Running the Project

```bash
# Generate test data
python3 generate_testdata.py

# Start web app
python3 app.py
# Open http://localhost:5000

# CLI usage
python3 demo_fetch.py --large --user 42
python3 demo_fetch.py --large --check 42 100
python3 demo_fetch.py --large --benchmark 1000
```

## Core Concepts Understood

### Door Group Hierarchy (Primary)
- **Default: Everything is denied**
- Allow on a door group opens that branch (including children)
- Deny cuts off a sub-branch (including children)
- A deeper Allow can re-open a cut-off branch

### User Group Hierarchy (Secondary)
- Adds Direct vs. Inherited distinction
- Direct Allow overrides Inherited Deny
- Direct Deny always applies
- Inherited vs. Inherited: Deny wins

### Design Insight
- Door group hierarchy should mirror physical building structure
- User group hierarchy is optional - flat groups often suffice
- Use hierarchy only when inheritance genuinely reduces complexity

## Architecture Highlights

- Recursive CTEs for permission resolution
- Performance: ~480 queries/second, ~2ms average
- Supports both flat and hierarchical user groups

## Open Tasks / Next Steps

- Structure optimization analysis (suggest merging groups with identical permissions)
- Better visualization of why a user has/doesn't have access to a door
- AI-guided data import (natural language, pattern recognition, or guided dialog)

## Blockers

- (none)

## Notes

- Original "Gold Standard" claims about Siemens, Lenel, etc. were removed - not verified
- The system works, but complexity needs careful documentation
- Flat user groups are often sufficient for simpler use cases
