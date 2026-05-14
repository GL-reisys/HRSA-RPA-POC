# SQL Server Connection Setup

## Overview
The application now supports connecting to the GEMS database on SQL Server instead of using JSON mock data.

## Prerequisites

### 1. Install SQL Server ODBC Driver
Download and install **ODBC Driver 17 for SQL Server** from Microsoft:
https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server

Verify installation by running in PowerShell:
```powershell
Get-OdbcDriver | Where-Object {$_.Name -like "*SQL Server*"}
```

### 2. Install Python Package
```bash
pip install pyodbc==5.1.0
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

## Configuration

### 1. Create .env File
Copy `.env.example` to `.env` in the backend directory:
```bash
cp .env.example .env
```

### 2. Enable SQL Server Connection
Edit your `.env` file and set:
```env
USE_SQL_SERVER=true
DB_SERVER=your-sql-server-hostname
DB_NAME=your-database-name
DB_USER=your-username
DB_PASSWORD=your-password
DB_DRIVER=ODBC Driver 17 for SQL Server
```

**Important:** Credentials are stored securely in `.env` which is gitignored.

### 3. Verify Network Access
Ensure you can reach the SQL Server:
```powershell
Test-NetConnection -ComputerName your-sql-server-hostname -Port 1433
```

## Database Tables Used

The application queries these GEMS database tables:
- `dbo.ExternalOrganizations` - UEI validation
- `dbo.FundingCycles` - Funding Opportunity validation
- `dbo.Grants` - Grant Number validation
- `dbo.GrantOrganizations` - Grant ownership verification
- `dbo.Awards` - Active grant checking
- `dbo.Applications` - Duplicate application detection
- `dbo.ApplicationExternalOrganizations` - Application linking

## Testing Connection

### Test Script
Create `backend/test_db_connection.py`:
```python
import os
from dotenv import load_dotenv
from services.database_service import DatabaseService

# Load environment variables
load_dotenv()

print(f"USE_SQL_SERVER: {os.getenv('USE_SQL_SERVER')}")
print(f"DB_SERVER: {os.getenv('DB_SERVER')}")
print(f"DB_NAME: {os.getenv('DB_NAME')}")
print()

try:
    # Initialize database service (will use SQL Server if USE_SQL_SERVER=true)
    db = DatabaseService()
    
    if db.use_sql_server:
        print("✅ Connected to SQL Server!")
        
        # Test UEI lookup
        test_uei = "K9WSHYN40ML6"
        org = db.get_organization_by_uei(test_uei)
        
        if org:
            print(f"✅ UEI Test Passed: Found organization '{org.organization_name}'")
        else:
            print(f"⚠️  UEI Test: No organization found for {test_uei}")
            
        # Test FON lookup
        test_fon = "HRSA-26-094"
        fo = db.get_funding_cycle_by_code(test_fon)
        
        if fo:
            print(f"✅ FON Test Passed: Found funding opportunity {fo.announcement_number}")
        else:
            print(f"⚠️  FON Test: No funding opportunity found for {test_fon}")
    else:
        print("ℹ️  Using JSON mock database")
        
except Exception as e:
    print(f"❌ Connection Failed: {str(e)}")
    import traceback
    traceback.print_exc()
```

Run the test:
```bash
cd backend
python test_db_connection.py
```

## Switching Between SQL Server and JSON

### Use SQL Server (Production)
Set in `.env`:
```env
USE_SQL_SERVER=true
```

### Use JSON Mock Data (Development)
Set in `.env`:
```env
USE_SQL_SERVER=false
```

## Troubleshooting

### Error: "Data source name not found"
- Install ODBC Driver 17 for SQL Server
- Or change `DB_DRIVER` in `.env` to match your installed driver

### Error: "Login failed for user"
- Verify credentials in .env file are correct
- Check SQL Server allows SQL authentication
- Verify user has read access to the database

### Error: "Cannot open database"
- Verify database name is correct in .env
- Check user has access to the database

### Error: "Connection timeout"
- Verify server name in .env is correct
- Check firewall allows port 1433
- Verify you're on the correct network/VPN

## Security Notes

1. **Never commit `.env` file** - It contains credentials
2. **.env is gitignored** - Safe to store credentials locally
3. **For production deployment** - Use environment variables or Azure Key Vault
4. **Credentials** - Contact your database administrator for access credentials

## SQL Queries

All SQL queries are defined in `backend/sql/queries.py` and use parameterized queries (?) to prevent SQL injection.

Query mapping:
- `validate_uei` → Checks if UEI exists
- `get_organization_by_uei` → Gets org details by UEI
- `get_funding_cycle_by_code` → Gets FON details
- `get_grant_by_number` → Gets grant details
- `get_active_grants_by_organization` → Lists active grants
- `check_program_match` → Verifies grant-FON alignment
- `find_related_applications` → Finds duplicate applications
