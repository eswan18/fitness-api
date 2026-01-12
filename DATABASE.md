# Database 

## Prerequisites

1. **PostgreSQL Database**: You need a running PostgreSQL instance. But in practice, I use Neon DB.
2. **Environment Variables**: Set up your `DATABASE_URL` environment variable. I use a standard .env files: `.env.prod` and `.env.dev`.

## Environment Setup

All of your `.env` files should be in `api` directory and contain the following:

```env
# Database connection
DATABASE_URL=postgresql://username:password@localhost:5432/fitness_db

# Other environment variables (Strava, Google Calendar, etc.)
# ... your other environment variables ...
```

### Database URL Format

The `DATABASE_URL` should follow this format:
```
postgresql://[username[:password]@][host[:port]][/database]
```

## Database Migration

### 1. Install Dependencies

```bash
cd api
uv sync
```

### 2. Run Migrations

Assuming your database is already created, you can run the migrations with the following commands:

```bash
cd api
uv run alembic upgrade head
```

This creates the following tables:

### `runs` Table (Current State)
- `id`: Primary key (string) - deterministic ID based on source
- `datetime_utc`: When the run occurred (UTC)
- `type`: Run type ('Outdoor Run' or 'Treadmill Run')
- `distance`: Distance in miles
- `duration`: Duration in seconds
- `source`: Data source ('MapMyFitness' or 'Strava')
- `avg_heart_rate`: Average heart rate (optional)
- `shoe_id`: Foreign key reference to shoes table (optional)
- `last_edited_at`: When the run was last edited (optional)
- `last_edited_by`: User who last edited the run (optional)
- `version`: Current version number of the run (default: 1)
- `deleted_at`: Soft deletion timestamp (optional)
- `created_at`: Record creation timestamp
- `updated_at`: Record update timestamp

### `runs_history` Table (Edit History)
- `history_id`: Primary key (auto-incrementing integer)
- `run_id`: Foreign key reference to runs.id
- `version_number`: Version number for this historical snapshot
- `change_type`: Type of change ('original', 'edit', 'deletion')
- All run data fields: `datetime_utc`, `type`, `distance`, `duration`, `source`, `avg_heart_rate`, `shoe_id`
- `changed_at`: When this version was created
- `changed_by`: User who made the change (optional)
- `change_reason`: Reason for the change (optional)

### `shoes` Table
- `id`: Primary key (string) - normalized from shoe name
- `name`: Display name of the shoe (unique)
- `retired_at`: Date when shoe was retired (optional)
- `notes`: Freeform notes (optional)
- `retirement_notes`: Notes specific to retirement (optional)
- `deleted_at`: Soft deletion timestamp (optional)
- `created_at`: Record creation timestamp
- `updated_at`: Record update timestamp

The tables have foreign key relationships:
- `runs.shoe_id` references `shoes.id`
- `runs_history.run_id` references `runs.id` (CASCADE DELETE)

**Soft Deletion**: Both tables support soft deletion via the `deleted_at` field. Records with a non-null `deleted_at` are considered deleted but remain in the database for audit/recovery purposes.

**Retirement Logic**: Shoes are considered retired if `retired_at` is not null (no separate boolean field needed).

### `synced_runs` Table (Google Calendar)
- `id`: Primary key (auto-incrementing integer)
- `run_id`: Foreign key reference to `runs.id` (unique)
- `run_version`: Version of the run that was synced
- `google_event_id`: ID of the calendar event
- `synced_at`: Timestamp when sync occurred
- `sync_status`: One of `synced`, `failed`, `pending`
- `error_message`: Optional error context
- `created_at`, `updated_at`: Timestamps

### `oauth_credentials` Table (OAuth Token Storage)
- `id`: Primary key (auto-incrementing integer)
- `provider`: OAuth provider name (e.g., 'google', 'strava') - unique
- `client_id`: OAuth client ID
- `client_secret`: OAuth client secret
- `access_token`: Current access token (auto-refreshed)
- `refresh_token`: Refresh token for obtaining new access tokens
- `expires_at`: Access token expiration timestamp (optional)
- `created_at`: Record creation timestamp
- `updated_at`: Record update timestamp (auto-updated via trigger)

**Purpose**: Stores OAuth credentials for external service integrations (Strava, Google Calendar). Access tokens are automatically refreshed and persisted, eliminating the need for manual token updates.

**Security**: Table contains sensitive credentials. Never log or expose these values. Tokens are encrypted at rest by the database provider.

## Run ID System

The application uses deterministic IDs to ensure data consistency:

### Strava Runs
- Use Strava's native activity ID with prefix: `strava_{activity_id}`
- Example: `strava_1234567890`

### MapMyFitness Runs  
- Extract workout ID directly from the activity link URL
- Link format: `https://www.mapmyfitness.com/workout/{workout_id}`
- ID format: `mmf_{workout_id}`
- Example: `mmf_8622076198`

### Shoes
- Generate deterministic ID from shoe name normalization:
  - Convert to lowercase
  - Replace spaces and special characters with underscores  
  - Remove consecutive underscores
  - Strip leading/trailing underscores
- Examples:
  - "Nike Air Zoom Pegasus 38" → `nike_air_zoom_pegasus_38`
  - "Brooks Ghost 15" → `brooks_ghost_15`
  - "New Balance M1080K10" → `new_balance_m1080k10`

This approach ensures:
- **Idempotent operations**: Re-importing the same data won't create duplicates
- **Data integrity**: IDs remain consistent across imports
- **Update safety**: Changes to existing runs are handled gracefully
- **Referential integrity**: Foreign key constraints ensure data consistency between runs and shoes
- **Soft deletion**: Records can be "deleted" without losing data permanently
- **Audit trail**: Deletion timestamps provide visibility into data lifecycle

## Database Operations

### Raw SQL Access

The application uses raw SQL queries via psycopg3. Key modules:

- `fitness/db/connection.py`: Database connection management
- `fitness/db/runs.py`: Run-specific database operations

### Available Operations

```python
from fitness.db.runs import *

# Get all runs
runs = get_all_runs()

# Get specific run by ID
run = get_run_by_id("strava_1234567890")

# Get runs in date range
runs = get_runs_in_date_range(start_date, end_date)

# Create a new run
run_id = create_run(run_object)

# Insert or update (recommended for imports)
run_id = upsert_run(run_object)

# Bulk operations
count = bulk_create_runs(list_of_runs)  # Insert only new runs

# Get enriched run details (shoes + sync)
details = get_run_details_in_date_range(start_date, end_date)

# Check if run exists
exists = run_exists(run_object)

# Shoes operations
from fitness.db.shoes import *

# Get all shoes (non-deleted by default)
shoes = get_all_shoes()
shoes_including_deleted = get_all_shoes(include_deleted=True)

# Get specific shoe by name or ID
shoe = get_shoe_by_name("Nike Air Zoom Pegasus 38")
shoe = get_shoe_by_id("nike_air_zoom_pegasus_38")

# Get shoes by status
active_shoes = get_active_shoes()  # Not retired and not deleted
retired_shoes = get_retired_shoes()  # Has retirement_date and not deleted

# Create or update shoes
shoe_id = create_shoe(shoe_object)
shoe_id = upsert_shoe(shoe_object)  # Handles updates gracefully

# Retirement management (based on retirement_date, not boolean)
retire_shoe("Nike Air Zoom Pegasus 38", retirement_date, "Worn out after 500 miles")
unretire_shoe("Nike Air Zoom Pegasus 38")

# Soft deletion
soft_delete_shoe("Nike Air Zoom Pegasus 38")
restore_shoe("Nike Air Zoom Pegasus 38")

# Hard deletion (permanent)
delete_shoe("Nike Air Zoom Pegasus 38")

# Check if shoe exists
exists = shoe_exists("Nike Air Zoom Pegasus 38")

# Runs operations
from fitness.db.runs import *

# All operations support include_deleted parameter (defaults to False)
runs = get_all_runs()  # Only non-deleted runs
runs_including_deleted = get_all_runs(include_deleted=True)

# Soft deletion for runs
soft_delete_run("run_id")
restore_run("run_id")
soft_delete_runs_by_source("Strava")

# Note: When creating/upserting runs, shoes are automatically created
# if they don't exist based on the shoe name from the run data
```

### Refreshing Data

The API includes functionality to fetch only new data from external sources:

```python
# This will re-fetch from Strava and MMF, then insert only new runs
# Uses deterministic IDs to identify new runs not already in the database
result = update_new_runs_only()
```

### Run Editing and History

The application supports editing runs with complete history tracking. All changes are recorded in the `runs_history` table.

#### Database Operations

```python
from fitness.db.runs_history import *

# Update a run with automatic history tracking
update_run_with_history(
    run_id="strava_1234567890",
    updates={"distance": 5.2, "avg_heart_rate": 155},
    changed_by="user123",
    change_reason="Corrected GPS accuracy issue"
)

# Get complete edit history for a run (newest first)
history = get_run_history("strava_1234567890")

# Get a specific version of a run
version = get_run_version("strava_1234567890", version_number=2)

# Get the latest version number
latest_version = get_latest_version_number("strava_1234567890")

```

#### API Endpoints

The API provides REST endpoints for run editing:

- `PATCH /runs/{run_id}` - Edit a run with change tracking
- `GET /runs/{run_id}/history` - Get edit history
- `GET /runs/{run_id}/history/{version}` - Get specific version
- `POST /runs/{run_id}/restore/{version}` - Restore to previous version

#### Edit History Features

**Atomic Transactions**: All edit operations use database transactions to ensure consistency - the current run and history record are updated together or not at all.

**Version Tracking**: Each edit increments the version number. The `runs` table always contains the current state, while `runs_history` contains all previous versions.

**Change Metadata**: Every edit records:
- Who made the change (`changed_by`)
- When it was made (`changed_at`)
- Why it was made (`change_reason`)
- What type of change (`change_type`: original, edit, deletion)

**Field Restrictions**: Only certain fields can be edited to maintain data integrity:
- ✅ Editable: `distance`, `duration`, `avg_heart_rate`, `type`, `shoe_id`, `datetime_utc`
- ❌ Protected: `source`, `id` (maintains source data lineage)

**Automatic History Creation**: When runs are first imported, an "original" history entry is automatically created with `change_type: "original"`.

#### Initial Setup

For new installations:

1. **Schema Migration**: Run `alembic upgrade head` to create all required tables including `runs_history`
2. **Automatic History**: All newly imported runs will automatically get their original history entries created during import

## Creating New Migrations

When you need to modify the database schema:

```bash
cd api
alembic revision -m "Description of your change"
```

Edit the generated migration file in `alembic/versions/`, then apply it:

```bash
alembic upgrade head
```

## Troubleshooting

### Connection Issues

1. **Check DATABASE_URL**: Ensure the format is correct and the database exists
2. **Database permissions**: Make sure your user has CREATE/INSERT/SELECT permissions
3. **Network connectivity**: Verify you can connect to the PostgreSQL server

### Migration Issues

1. **Check dependencies**: Run `uv sync` to ensure all packages are installed
2. **Check database exists**: The database must exist before running migrations
3. **Check credentials**: Ensure your DATABASE_URL credentials are correct

## Architecture Notes

- **No ORM**: Uses raw SQL with psycopg3 for direct database access
- **Connection management**: Uses context managers for automatic connection cleanup
- **Migrations**: Alembic handles schema versioning and migrations
- **Performance**: Includes database indexes on commonly queried fields
- **Deterministic IDs**: Ensures data consistency and enables safe upsert operations
- **Soft deletion**: Preserves data while allowing logical deletion for audit trails