# PC Monitoring System

This PC Activity Monitor is a system-wide tracking tool that monitors keystrokes, mouse movement/clicks, and active applications. It features a real-time dashboard with productivity scoring, project tagging, and idle annotations. Users can export detailed reports in CSV, Markdown, or fortnightly formats.

# Quick Start

# Install Dependencies:
Run the following in your terminal: pip install pynput psutil.
Windows Users: Also run pip install pywin32.

# Run the Script:
Execute python monitor.py.

# Access Dashboard:
Navigate to http://localhost:8765 in your web browser.

# Key Features

Passive Tracking: Monitors every keystroke, mouse click, scroll, and movement distance.

App Awareness: Automatically detects the active application and window titles to categorize time.

Browser Analysis: Sub-categorizes web activity into groups like Social, Work, and Video.

Idle Recovery: Prompts for "Where was I?" annotations when you return to your desk to log breaks.

Project Tagging: Allows you to assign specific time blocks to custom projects with icons.

Reporting: Exports daily, weekly, or fortnightly summaries as Obsidian Markdown or CSV.

# Project Structure

monitor.py: The Python backend handling listeners and the local API server.

index.html: The Tailwind-based frontend dashboard.

activity_data/: Automatically generated folder where daily JSON logs are stored.

# Privacy
All data is stored locally in the activity_data folder. No information is sent to external servers.
