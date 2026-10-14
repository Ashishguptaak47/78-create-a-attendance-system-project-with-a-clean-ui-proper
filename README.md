# AttendX - Modern Attendance Management System

AttendX is a lightweight, full-featured attendance tracking system built with Python and Flask. It provides an intuitive web interface for managing members, recording daily attendance, tracking check-in/check-out times, and generating attendance summaries with CSV exports.

## Features
- **Dashboard**: Real-time stats on today's attendance rates, present/late/absent counts, and recent activity.
- **Quick Punch / Badge Scanner**: Instant check-in/check-out using member badge ID codes.
- **Bulk Attendance**: Mark attendance for all members on any given date with one click.
- **Member Roster**: Manage member profiles, departments, and unique ID badges.
- **Reports & Analytics**: Filter logs by date range and department, view individual attendance rates, and export data directly to CSV.
- **Zero Config**: Uses a file-based SQLite database with automatic migration.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the application
python main.py
```

Open your browser and navigate to `http://127.0.0.1:5000`.

## Running Tests

```bash
pytest tests/
```
