#!/usr/bin/env python3
"""
==========================================================
  PC ACTIVITY MONITOR — Full System-Wide Tracking
  with App Tracking, Project Tagging & Idle Annotations
==========================================================

Tracks EVERY keyboard press, mouse click, mouse movement,
scroll event, AND which application/window is active.
Supports project tagging and fortnightly reporting.

Serves a real-time dashboard on http://localhost:8765

Requirements:
    pip install pynput psutil

    Windows only (for app tracking):
        pip install pywin32

Usage:
    python monitor.py
    Then open http://localhost:8765 in your browser
"""

import os
import sys
import json
import time
import math
import threading
import signal
import platform
import subprocess
from datetime import datetime, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

try:
    from pynput import keyboard, mouse
except ImportError:
    print()
    print("=" * 60)
    print("  ❌ MISSING DEPENDENCY: pynput")
    print()
    print("  Install it with:")
    print("    pip install pynput")
    print("=" * 60)
    sys.exit(1)

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# ===================== PLATFORM DETECTION =====================
PLATFORM = platform.system()
CAN_TRACK_APPS = False

if PLATFORM == 'Windows':
    try:
        import win32gui
        import win32process
        if HAS_PSUTIL:
            CAN_TRACK_APPS = True
    except ImportError:
        pass
elif PLATFORM == 'Darwin':
    CAN_TRACK_APPS = True
elif PLATFORM == 'Linux':
    try:
        r = subprocess.run(['which', 'xdotool'], capture_output=True, timeout=2)
        if r.returncode == 0 and HAS_PSUTIL:
            CAN_TRACK_APPS = True
    except Exception:
        pass

# ===================== CONFIGURATION =====================
PORT = 8765
IDLE_THRESHOLD = 300
AWAY_THRESHOLD = 300
SAVE_INTERVAL = 10
SCROLL_PX_PER_STEP = 100
MONITOR_DPI = 96
TYPING_SESSION_GAP = 5
MAX_TICK_GAP = 30
APP_POLL_INTERVAL = 2
MIN_APP_SWITCH_TIME = 1
HISTORY_DAYS = 90
DATA_DIR = Path("activity_data")

PIXELS_PER_INCH = MONITOR_DPI
INCHES_PER_MILE = 63360
INCHES_PER_FOOT = 12
PIXELS_PER_MILE = PIXELS_PER_INCH * INCHES_PER_MILE
PIXELS_PER_FOOT = PIXELS_PER_INCH * INCHES_PER_FOOT

# ===================== APP NAME MAPPING =====================
APP_NAMES = {
    'chrome': 'Google Chrome', 'firefox': 'Firefox',
    'msedge': 'Microsoft Edge', 'opera': 'Opera',
    'brave': 'Brave Browser', 'safari': 'Safari',
    'vivaldi': 'Vivaldi', 'arc': 'Arc',
    'code': 'VS Code', 'code - insiders': 'VS Code Insiders',
    'winword': 'Microsoft Word', 'excel': 'Microsoft Excel',
    'powerpnt': 'PowerPoint', 'outlook': 'Outlook',
    'onenote': 'OneNote', 'teams': 'Microsoft Teams', 'ms-teams': 'Ms-Teams',
    'explorer': 'File Explorer', 'notepad': 'Notepad',
    'notepad++': 'Notepad++', 'sublime_text': 'Sublime Text',
    'slack': 'Slack', 'discord': 'Discord', 'spotify': 'Spotify',
    'windowsterminal': 'Windows Terminal', 'wt': 'Windows Terminal',
    'cmd': 'Command Prompt', 'powershell': 'PowerShell',
    'pwsh': 'PowerShell', 'python': 'Python', 'pythonw': 'Python',
    'idea64': 'IntelliJ IDEA', 'pycharm64': 'PyCharm',
    'webstorm64': 'WebStorm', 'devenv': 'Visual Studio',
    'figma': 'Figma', 'photoshop': 'Photoshop',
    'illustrator': 'Illustrator', 'obs64': 'OBS Studio',
    'vlc': 'VLC', 'zoom': 'Zoom', 'skype': 'Skype',
    'telegram': 'Telegram', 'whatsapp': 'WhatsApp',
    'signal': 'Signal', 'postman': 'Postman',
    'gitkraken': 'GitKraken', 'filezilla': 'FileZilla',
    'putty': 'PuTTY', 'winscp': 'WinSCP',
    'obsidian': 'Obsidian', 'notion': 'Notion',
    'todoist': 'Todoist', 'anydesk': 'AnyDesk',
    'mstsc': 'Remote Desktop', 'snippingtool': 'Snipping Tool',
    'calculatorapp': 'Calculator', 'mspaint': 'Paint',
    'wordpad': 'WordPad', 'wmplayer': 'Windows Media Player',
    'acrobat': 'Adobe Acrobat', 'acrord32': 'Adobe Reader',
    'thunderbird': 'Thunderbird', 'gimp-2.10': 'GIMP',
    'blender': 'Blender', 'unity': 'Unity',
    'rider64': 'Rider', 'datagrip64': 'DataGrip',
    'matlab': 'MATLAB', 'spss': 'SPSS', 'psychopy': 'PsychoPy-2024.2.5', 'chatgpt': 'ChatGPT'
}

APP_CATEGORIES = {
    'Browsers': ['Google Chrome', 'Firefox', 'Microsoft Edge', 'Opera', 'Brave Browser', 'Safari', 'Vivaldi', 'Arc'],
    'Development': ['PsychoPy-2024.2.5', 'VS Code', 'VS Code Insiders', 'Visual Studio', 'IntelliJ IDEA', 'PyCharm', 'WebStorm', 'Rider', 'DataGrip', 'Sublime Text', 'Notepad++', 'Postman', 'GitKraken'],
    'Office': ['Microsoft Word', 'Microsoft Excel', 'PowerPoint', 'Outlook', 'OneNote', 'Adobe Acrobat', 'Adobe Reader'],
    'Communication': ['Slack', 'Discord', 'Microsoft Teams', 'Ms-Teams', 'Zoom', 'Skype', 'Telegram', 'WhatsApp', 'Signal', 'Thunderbird'],
    'Productivity': ['ChatGPT', 'Chatgpt', 'Clipchamp', 'Werfault', 'Thonny', 'Obsidian', 'Notion', 'Todoist', 'Notepad', 'Calculator', 'Snipping Tool', 'Paint', 'Python'],
    'Media': ['Spotify', 'VLC', 'Windows Media Player', 'OBS Studio'],
    'Design': ['Gimp-3', 'Photos', 'Figma', 'Photoshop', 'Illustrator', 'GIMP', 'Paint', 'Blender'],
    'Terminal': ['Windows Terminal', 'Command Prompt', 'PowerShell', 'PuTTY'],
    'Remote': ['AnyDesk', 'Remote Desktop', 'WinSCP', 'FileZilla'],
    'Research': ['MATLAB', 'SPSS'],
    'System': ['Searchhost', 'Searchapp', 'Applicationframehost', 'Lockapp', 'File Explorer', 'Phoneexperiencehost', 'Shellexperiencehost', 'Desktop', 'Shellhost']
}

BROWSER_APPS = {'Google Chrome', 'Firefox', 'Microsoft Edge', 'Opera', 'Brave Browser', 'Safari', 'Vivaldi', 'Arc'}

# Browser sub-category rules: ordered by priority (first match wins)
# Each entry: (sub_category, icon, productivity, keywords_in_title)
BROWSER_SUBCATEGORIES = [
    # Email
    ('📧 Email',        '📧', 'productive',   ['gmail', 'outlook', 'mail', 'inbox', 'webmail', 'yahoo mail', 'protonmail', 'hotmail', 'roundcube']),
    # Video / streaming
    ('🎬 Video',        '🎬', 'distracting',  ['youtube', 'netflix', 'twitch', 'disney+', 'bbc iplayer', 'itvx', 'channel 4', 'prime video', 'vimeo', 'dailymotion', 'hulu', 'plex', 'peacock', 'crunchyroll', 'now tv']),
    # Social media
    ('📱 Social',       '📱', 'distracting',  ['discord', 'facebook', 'instagram', 'twitter', 'x.com', 'tiktok', 'reddit', 'linkedin', 'snapchat', 'pinterest', 'tumblr', 'mastodon', 'threads', 'bluesky']),
    # Shopping
    ('🛒 Shopping',     '🛒', 'distracting',  ['amazon', 'ebay', 'etsy', 'asos', 'argos', 'temu', 'shein', 'zalando', 'currys', 'very.co', 'next.co', 'john lewis', 'boots.com', 'wayfair', 'ikea']),
    # News & media reading
    ('📰 News',         '📰', 'neutral',      ['bbc.co.uk', 'bbc.com/news', 'guardian', 'dailymail', 'the times', 'telegraph', 'sky news', 'independent.co', 'huffpost', 'buzzfeed', 'cnn', 'reuters', 'ap news', 'techcrunch', 'the verge', 'wired', 'ars technica']),
    # Work / productivity tools
    ('💼 Work Tools',   '💼', 'productive',   ['REDcap', 'research', 'scaner', 'qualtrics', 'self-service portal', 'questionpro', 'survey', 'home', 'workshop equipment', 'labs', 'find resource booking', 'dashboard', 'find resource', 'manage resource', 'find user', 'pavlovia', 'explore', 'experiments', 'surveys', 'andrew p']),
    # Meetings / calls
    ('📞 Meetings',     '📞', 'productive',   ['meet.google', 'zoom.us', 'teams.microsoft', 'whereby', 'webex', 'gotomeeting', 'bluejeans', 'skype']),
    # Docs / writing
    ('📝 Docs',         '📝', 'productive',   ['docs.google', 'sheets.google', 'slides.google', 'drive.google', 'forms.google', 'sharepoint', 'onedrive', 'office.com', 'overleaf', 'notion.so']),
    # Code / development
    ('💻 Dev',          '💻', 'productive',   ['Photopea', 'Canva', 'Poster', 'github', 'gitlab', 'stackoverflow', 'codepen', 'replit', 'codesandbox', 'vercel', 'netlify', 'heroku', 'aws.amazon', 'console.cloud.google', 'portal.azure', 'npmjs', 'pypi.org', 'localhost', '127.0.0.1']),
    # Learning / education
    ('🎓 Learning',     '🎓', 'productive',   ['udemy', 'coursera', 'edx', 'khan academy', 'pluralsight', 'linkedin learning', 'skillshare', 'brilliant.org', 'duolingo', 'moodle', 'canvas', 'blackboard', 'ac.uk', 'university', 'lecture']),
    # Research / reading
    ('🔬 Research',     '🔬', 'productive',   ['scholar.google', 'pubmed', 'researchgate', 'sciencedirect', 'springer', 'wiley', 'jstor', 'arxiv', 'semanticscholar', 'doi.org', 'ncbi.nlm', 'bps.org', 'apa.org', 'wikipedia']),
    # Finance / banking
    ('💰 Finance',      '💰', 'neutral',      ['banking', 'barclays', 'hsbc', 'natwest', 'lloyds', 'santander', 'monzo', 'revolut', 'starling', 'paypal', 'wise', 'trading', 'coinbase', 'binance', 'hargreaves lansdown', 'vanguard']),
    # AI tools
    ('🤖 AI Tools',     '🤖', 'productive',   ['arena', 'claude', 'chat.openai', 'gemini.google', 'copilot.microsoft']),
    # Music / podcasts
    ('🎵 Music',        '🎵', 'neutral',      ['spotify', 'soundcloud', 'apple music', 'deezer', 'tidal', 'bandcamp', 'last.fm', 'podcast', 'audible']),
    # Maps / travel
    ('🗺️ Travel',       '🗺️', 'neutral',      ['easyjet', 'google maps', 'maps.apple', 'tripadvisor', 'booking.com', 'airbnb', 'hoseasons', 'expedia', 'skyscanner', 'kayak', 'trainline', 'rightmove', 'zoopla']),
]


def classify_browser_window(window_title):
    """
    Given a browser window title, return (sub_category, icon, productivity_label).
    Falls back to ('🌐 General Browsing', '🌐', 'neutral') if nothing matches.
    """
    if not window_title:
        return ('🌐 General Browsing', '🌐', 'neutral')
    title_lower = window_title.lower()
    for sub_cat, icon, productivity, keywords in BROWSER_SUBCATEGORIES:
        if any(kw in title_lower for kw in keywords):
            return (sub_cat, icon, productivity)
    return ('🌐 General Browsing', '🌐', 'neutral')


class ActivityMonitor:
    """Core monitor — captures all system-wide input events + active app."""

    def __init__(self):
        self.lock = threading.Lock()
        self.running = True
        self.data_dir = DATA_DIR
        self.data_dir.mkdir(exist_ok=True)

        # ---- Core counters ----
        self.keystrokes = 0
        self.clicks = 0
        self.left_clicks = 0
        self.right_clicks = 0
        self.middle_clicks = 0
        self.scrolls = 0
        self.scroll_up = 0
        self.scroll_down = 0
        self.scroll_distance_px = 0.0
        self.mouse_distance_px = 0.0
        self.mouse_moves = 0
        self.last_mouse_pos = None

        # ---- Time tracking ----
        self.session_start = time.time()
        self.last_activity = time.time()
        self.last_tick = time.time()
        self.is_active = True
        self.idle_start = None
        self.active_time_ms = 0.0
        self.idle_time_ms = 0.0

        # ---- Rate tracking ----
        self.recent_keys = []
        self.recent_clicks = []
        self.recent_scrolls = []
        self.peak_kpm = 0
        self.peak_cpm = 0
        self.peak_spm = 0

        # ---- Typing sessions ----
        self.typing_sessions = []
        self.current_typing_session = None

        # ---- Sleep/Off periods ----
        self.sleep_periods = []

        # ---- Idle annotations ----
        self.idle_annotations = []

        # ---- Project tags ----
        self.project_tags = []
        self.current_project = None
        self.current_project_icon = None
        self.current_project_start = time.time()

        # ---- App tracking ----
        self.app_usage = {}
        self.current_app = None
        self.current_window = None
        self.app_switch_time = time.time()
        self.app_switches = []
        self.app_poll_counter = 0

        # ---- Hourly data ----
        self.hourly_keys = [0] * 24
        self.hourly_clicks = [0] * 24
        self.hourly_scrolls = [0] * 24
        self.hourly_active = [0.0] * 24
        self.hourly_idle = [0.0] * 24
        self.hourly_mouse_dist = [0.0] * 24
        self.hourly_scroll_dist = [0.0] * 24

        # ---- Key categories ----
        self.key_categories = {
            'letters': 0, 'numbers': 0, 'modifiers': 0,
            'special': 0, 'function': 0, 'navigation': 0,
            'space': 0, 'enter': 0, 'backspace': 0, 'other': 0
        }

        # ---- Logs ----
        self.activity_log = []
        self.idle_periods = []

        # ---- Mouse move throttle ----
        self.last_move_time = 0

        self.load_data()

    # ============ IDLE ANNOTATIONS ============

    def annotate_idle(self, data):
        """Store an annotation for an idle/away period."""
        with self.lock:
            annotation = {
                'idle_start': data.get('idle_start', 0),
                'idle_end': data.get('idle_end', 0),
                'duration_ms': data.get('duration_ms', 0),
                'category': data.get('category', 'Other'),
                'category_icon': data.get('category_icon', '❓'),
                'notes': data.get('notes', ''),
                'annotated_at': time.time() * 1000,
            }
            self.idle_annotations.append(annotation)
            if len(self.idle_annotations) > 500:
                self.idle_annotations = self.idle_annotations[-500:]

            cat = annotation['category']
            icon = annotation['category_icon']
            dur = self._fmt_dur(annotation['duration_ms'])
            notes = annotation['notes']
            msg = f'{icon} Away: {cat} ({dur})'
            if notes:
                msg += f' — {notes[:80]}'
            self._log('break', msg)
            print(f"  📝 Idle annotated: {cat} ({dur}) {notes[:50]}")
            return True

    # ============ PROJECT TAGGING ============

    def tag_project(self, data):
        """Tag current activity with a project/task."""
        with self.lock:
            now = time.time()
            # Close out previous project tag
            if self.current_project and self.current_project_start:
                duration_ms = (now - self.current_project_start) * 1000
                if duration_ms > 1000:  # At least 1 second
                    self.project_tags.append({
                        'project': self.current_project,
                        'icon': self.current_project_icon or '🏷️',
                        'start': self.current_project_start * 1000,
                        'end': now * 1000,
                        'duration_ms': duration_ms,
                        'notes': '',
                    })

            project = data.get('project', 'Other')
            icon = data.get('icon', '🏷️')
            notes = data.get('notes', '')

            if project == '__stop__':
                # Just stopping, no new project
                self.current_project = None
                self.current_project_icon = None
                self.current_project_start = None
                self._log('system', '🏷️ Project tracking stopped')
            else:
                self.current_project = project
                self.current_project_icon = icon
                self.current_project_start = now
                self._log('system', f'{icon} Working on: {project}' + (f' — {notes[:60]}' if notes else ''))
                print(f"  🏷️ Project tagged: {icon} {project}")

            if len(self.project_tags) > 1000:
                self.project_tags = self.project_tags[-1000:]
            return True

    # ============ ACTIVE WINDOW DETECTION ============

    def get_active_window(self):
        try:
            if PLATFORM == 'Windows':
                return self._get_window_windows()
            elif PLATFORM == 'Darwin':
                return self._get_window_macos()
            elif PLATFORM == 'Linux':
                return self._get_window_linux()
        except Exception:
            pass
        return None, None

    def _get_window_windows(self):
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None, None
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return 'Desktop', ''
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            proc_name = proc.name().lower().replace('.exe', '')
            app_name = APP_NAMES.get(proc_name, proc.name().replace('.exe', '').title())
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            app_name = self._app_from_title(title)
        return app_name, title

    def _get_window_macos(self):
        script = '''
tell application "System Events"
    set frontApp to first application process whose frontmost is true
    set appName to name of frontApp
    try
        tell frontApp
            set winTitle to name of front window
        end tell
    on error
        set winTitle to ""
    end try
    return appName & "|||" & winTitle
end tell'''
        result = subprocess.run(['osascript', '-e', script],
                                capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            parts = result.stdout.strip().split('|||')
            app_name = parts[0].strip() if parts else 'Unknown'
            title = parts[1].strip() if len(parts) > 1 else ''
            return app_name, title
        return None, None

    def _get_window_linux(self):
        wid = subprocess.run(['xdotool', 'getactivewindow'],
                             capture_output=True, text=True, timeout=2)
        if wid.returncode != 0:
            return None, None
        wid_str = wid.stdout.strip()
        name_r = subprocess.run(['xdotool', 'getwindowname', wid_str],
                                capture_output=True, text=True, timeout=2)
        title = name_r.stdout.strip() if name_r.returncode == 0 else ''
        app_name = 'Unknown'
        try:
            pid_r = subprocess.run(['xdotool', 'getwindowpid', wid_str],
                                   capture_output=True, text=True, timeout=2)
            if pid_r.returncode == 0:
                pid = int(pid_r.stdout.strip())
                p = psutil.Process(pid)
                proc_name = p.name().lower().replace('.exe', '')
                app_name = APP_NAMES.get(proc_name, p.name().title())
        except Exception:
            app_name = self._app_from_title(title)
        return app_name, title

    def _app_from_title(self, title):
        known = {
            'Google Chrome': 'Google Chrome', 'Mozilla Firefox': 'Firefox',
            'Microsoft Edge': 'Microsoft Edge', 'Visual Studio Code': 'VS Code',
            'Microsoft Word': 'Microsoft Word', 'Microsoft Excel': 'Microsoft Excel',
            'PowerPoint': 'PowerPoint', 'Outlook': 'Outlook',
            'Slack': 'Slack', 'Discord': 'Discord',
            'Obsidian': 'Obsidian', 'Notion': 'Notion',
        }
        for key, name in known.items():
            if key.lower() in title.lower():
                return name
        if ' - ' in title:
            return title.split(' - ')[-1].strip()[:40]
        return title[:30] if title else 'Unknown'

    def _clean_window_title(self, title, app_name):
        if not title:
            return '(untitled)'
        for sep in [' - ', ' — ', ' | ', ' · ']:
            if sep in title:
                parts = title.split(sep)
                cleaned_parts = []
                for p in parts:
                    p_clean = p.strip()
                    if p_clean.lower() not in app_name.lower() and app_name.lower() not in p_clean.lower():
                        cleaned_parts.append(p_clean)
                if cleaned_parts:
                    return sep.join(cleaned_parts)[:120]
                return parts[0].strip()[:120]
        return title[:120]

    def _get_app_category(self, app_name):
        for category, apps in APP_CATEGORIES.items():
            if app_name in apps:
                return category
        return 'Other'

    def _poll_active_window(self):
        if not CAN_TRACK_APPS:
            return

        app_name, window_title = self.get_active_window()
        if not app_name:
            return

        now = time.time()

        if app_name == self.current_app and window_title == self.current_window:
            return

        time_in_prev = (now - self.app_switch_time) * 1000 if self.app_switch_time else 0

        if self.current_app and time_in_prev > 0:
            if self.current_app not in self.app_usage:
                self.app_usage[self.current_app] = {'total_ms': 0, 'windows': {}}
            self.app_usage[self.current_app]['total_ms'] += time_in_prev

            if self.current_window:
                clean_title = self._clean_window_title(self.current_window, self.current_app)
                wins = self.app_usage[self.current_app]['windows']
                wins[clean_title] = wins.get(clean_title, 0) + time_in_prev
                if len(wins) > 50:
                    sorted_wins = sorted(wins.items(), key=lambda x: -x[1])[:30]
                    self.app_usage[self.current_app]['windows'] = dict(sorted_wins)

        is_app_switch = app_name != self.current_app

        if is_app_switch and self.current_app:
            if time_in_prev >= MIN_APP_SWITCH_TIME * 1000:
                clean = self._clean_window_title(window_title, app_name) if window_title else ''
                self.app_switches.append({
                    'time': now * 1000,
                    'from_app': self.current_app or '',
                    'to_app': app_name,
                    'window_title': clean,
                    'from_duration': round(time_in_prev),
                })
                if len(self.app_switches) > 500:
                    self.app_switches = self.app_switches[-500:]
                self._log('system', f'📱 Switched to {app_name}' + (f': {clean}' if clean else ''))

        elif not is_app_switch and window_title != self.current_window:
            clean = self._clean_window_title(window_title, app_name) if window_title else ''
            if time_in_prev >= MIN_APP_SWITCH_TIME * 1000 and clean:
                self._log('system', f'📄 {app_name} → {clean}')

        self.current_app = app_name
        self.current_window = window_title
        self.app_switch_time = now

    # ============ KEY CATEGORIZATION ============

    def categorize_key(self, key):
        try:
            if hasattr(key, 'char') and key.char:
                if key.char.isalpha(): return 'letters'
                elif key.char.isdigit(): return 'numbers'
                else: return 'special'
        except Exception:
            pass
        key_str = str(key).lower().replace('key.', '')
        if key_str == 'space': return 'space'
        elif key_str in ('enter', 'return'): return 'enter'
        elif key_str == 'backspace': return 'backspace'
        elif key_str in ('shift', 'shift_r', 'shift_l', 'ctrl', 'ctrl_r', 'ctrl_l',
                         'alt', 'alt_r', 'alt_l', 'alt_gr', 'cmd', 'cmd_r', 'cmd_l', 'meta'):
            return 'modifiers'
        elif key_str.startswith('f') and key_str[1:].isdigit(): return 'function'
        elif key_str in ('up', 'down', 'left', 'right', 'home', 'end',
                         'page_up', 'page_down', 'insert', 'delete'):
            return 'navigation'
        return 'other'

    # ============ INPUT CALLBACKS ============

    def on_key_press(self, key):
        with self.lock:
            now = time.time()
            self.keystrokes += 1
            self.last_activity = now
            self.recent_keys.append(now)
            hour = datetime.now().hour
            self.hourly_keys[hour] += 1
            cat = self.categorize_key(key)
            self.key_categories[cat] = self.key_categories.get(cat, 0) + 1
            if self.current_typing_session:
                if now - self.current_typing_session['last_key'] > TYPING_SESSION_GAP:
                    self._finalize_typing_session()
                    self.current_typing_session = {'start': now, 'end': now, 'key_count': 1, 'last_key': now}
                else:
                    self.current_typing_session['end'] = now
                    self.current_typing_session['key_count'] += 1
                    self.current_typing_session['last_key'] = now
            else:
                self.current_typing_session = {'start': now, 'end': now, 'key_count': 1, 'last_key': now}
            self._check_idle_resume(now)

    def on_click(self, x, y, button, pressed):
        if not pressed:
            return
        with self.lock:
            now = time.time()
            self.clicks += 1
            self.last_activity = now
            self.recent_clicks.append(now)
            hour = datetime.now().hour
            self.hourly_clicks[hour] += 1
            if button == mouse.Button.left: self.left_clicks += 1
            elif button == mouse.Button.right: self.right_clicks += 1
            elif button == mouse.Button.middle: self.middle_clicks += 1
            self._check_idle_resume(now)

    def on_move(self, x, y):
        now = time.time()
        if now - self.last_move_time < 0.05:
            return
        with self.lock:
            self.last_move_time = now
            self.mouse_moves += 1
            self.last_activity = now
            if self.last_mouse_pos is not None:
                dx = x - self.last_mouse_pos[0]
                dy = y - self.last_mouse_pos[1]
                dist = math.sqrt(dx * dx + dy * dy)
                self.mouse_distance_px += dist
                hour = datetime.now().hour
                self.hourly_mouse_dist[hour] += dist
            self.last_mouse_pos = (x, y)
            self._check_idle_resume(now)

    def on_scroll(self, x, y, dx, dy):
        with self.lock:
            now = time.time()
            abs_dy = abs(dy)
            self.scrolls += abs_dy
            self.last_activity = now
            self.recent_scrolls.append(now)
            if dy > 0: self.scroll_up += abs_dy
            else: self.scroll_down += abs_dy
            scroll_px = abs_dy * SCROLL_PX_PER_STEP
            self.scroll_distance_px += scroll_px
            hour = datetime.now().hour
            self.hourly_scrolls[hour] += abs_dy
            self.hourly_scroll_dist[hour] += scroll_px
            self._check_idle_resume(now)

    # ============ STATE MANAGEMENT ============

    def _check_idle_resume(self, now):
        if not self.is_active:
            idle_duration_s = now - self.idle_start if self.idle_start else 0
            if idle_duration_s > IDLE_THRESHOLD:
                self.idle_periods.append({
                    'start': self.idle_start * 1000, 'end': now * 1000,
                    'duration': idle_duration_s * 1000
                })
                if idle_duration_s > AWAY_THRESHOLD:
                    self._log('break', f'☕ Away for {self._fmt_dur(idle_duration_s * 1000)} ({self._fmt_time(self.idle_start)} → {self._fmt_time(now)})')
                else:
                    self._log('idle', f'💤 Idle for {self._fmt_dur(idle_duration_s * 1000)} ({self._fmt_time(self.idle_start)} → {self._fmt_time(now)})')
            self.is_active = True
            self.idle_start = None
            self._log('active', '🟢 Activity resumed')

    def _finalize_typing_session(self):
        s = self.current_typing_session
        if s and s['key_count'] >= 5:
            duration = max(0.001, s['end'] - s['start'])
            kpm = round((s['key_count'] / duration) * 60)
            self.typing_sessions.append({
                'start': s['start'] * 1000, 'end': s['end'] * 1000,
                'duration': duration * 1000, 'key_count': s['key_count'], 'kpm': kpm,
                'app': self.current_app or '',
            })
            if len(self.typing_sessions) > 500:
                self.typing_sessions = self.typing_sessions[-500:]
            self._log('typing', f'⌨️ Typing burst: {s["key_count"]} keys in {self._fmt_dur(duration * 1000)} ({kpm} KPM)'
                      + (f' in {self.current_app}' if self.current_app else ''))
        self.current_typing_session = None

    def tick(self):
        with self.lock:
            now = time.time()
            elapsed_ms = (now - self.last_tick) * 1000
            self.last_tick = now
            hour = datetime.now().hour

            if elapsed_ms > MAX_TICK_GAP * 1000:
                sleep_start = now - (elapsed_ms / 1000)
                self.sleep_periods.append({
                    'start': sleep_start * 1000, 'end': now * 1000,
                    'duration': elapsed_ms
                })
                self._log('system', f'💻 PC was sleeping/off for {self._fmt_dur(elapsed_ms)} — time EXCLUDED')
                self.last_activity = now
                self.is_active = True
                self.idle_start = None
                if self.current_typing_session:
                    self._finalize_typing_session()
                self.recent_keys.clear()
                self.recent_clicks.clear()
                self.recent_scrolls.clear()
                return

            time_since_activity = now - self.last_activity

            if self.current_typing_session and now - self.current_typing_session['last_key'] > TYPING_SESSION_GAP:
                self._finalize_typing_session()

            if time_since_activity < IDLE_THRESHOLD:
                self.active_time_ms += elapsed_ms
                self.hourly_active[hour] += elapsed_ms
            else:
                self.idle_time_ms += elapsed_ms
                self.hourly_idle[hour] += elapsed_ms
                if self.is_active:
                    self.is_active = False
                    self.idle_start = self.last_activity
                    self._log('idle', f'💤 Went idle — no input for {IDLE_THRESHOLD}s')

            cutoff = now - 60
            self.recent_keys = [t for t in self.recent_keys if t > cutoff]
            self.recent_clicks = [t for t in self.recent_clicks if t > cutoff]
            self.recent_scrolls = [t for t in self.recent_scrolls if t > cutoff]

            kpm = len(self.recent_keys)
            cpm = len(self.recent_clicks)
            spm = len(self.recent_scrolls)
            if kpm > self.peak_kpm: self.peak_kpm = kpm
            if cpm > self.peak_cpm: self.peak_cpm = cpm
            if spm > self.peak_spm: self.peak_spm = spm

        self.app_poll_counter += 1
        if self.app_poll_counter >= APP_POLL_INTERVAL:
            self.app_poll_counter = 0
            self._poll_active_window()

    # ============ API DATA ============

    def _get_top_apps(self, limit=20):
        result = {}
        for app, data in self.app_usage.items():
            result[app] = {
                'total_ms': data['total_ms'],
                'windows': dict(sorted(data['windows'].items(), key=lambda x: -x[1])[:10]),
                'category': self._get_app_category(app),
            }
        if self.current_app and self.app_switch_time:
            pending = (time.time() - self.app_switch_time) * 1000
            if self.current_app not in result:
                result[self.current_app] = {'total_ms': 0, 'windows': {}, 'category': self._get_app_category(self.current_app)}
            result[self.current_app]['total_ms'] += pending
            if self.current_window:
                clean = self._clean_window_title(self.current_window, self.current_app)
                w = result[self.current_app]['windows']
                w[clean] = w.get(clean, 0) + pending

        sorted_apps = sorted(result.items(), key=lambda x: -x[1]['total_ms'])[:limit]
        return [{
            'app': app,
            'total_ms': round(data['total_ms']),
            'category': data.get('category', 'Other'),
            'windows': [{'title': t, 'ms': round(ms)} for t, ms in
                        sorted(data['windows'].items(), key=lambda x: -x[1])[:8]]
        } for app, data in sorted_apps]

    def _get_category_breakdown(self):
        cats = {}
        top_apps = self._get_top_apps(50)
        for app_data in top_apps:
            cat = app_data['category']
            cats[cat] = cats.get(cat, 0) + app_data['total_ms']
        return dict(sorted(cats.items(), key=lambda x: -x[1]))

    def _build_browser_subcats_from_app_usage(self, app_usage_dict):
        """Build browser sub-category breakdown from a raw app_usage dict (for historical data)."""
        result = {}
        for app_name, data in app_usage_dict.items():
            clean_app = APP_NAMES.get(app_name.lower().replace('.exe', ''), app_name)
            if clean_app not in BROWSER_APPS and app_name not in BROWSER_APPS:
                continue
            for title, ms in data.get('windows', {}).items():
                sub_cat, icon, productivity = classify_browser_window(title)
                if sub_cat not in result:
                    result[sub_cat] = {'ms': 0, 'icon': icon, 'productivity': productivity}
                result[sub_cat]['ms'] += ms
        for v in result.values():
            v['ms'] = round(v['ms'])
        return dict(sorted(result.items(), key=lambda x: -x[1]['ms']))

    def _get_browser_subcategory_breakdown(self):
        """
        For all browser apps, break down time spent by browser sub-category
        (Email, Video, Social, Dev, etc.) based on window titles.
        Returns a dict: { sub_cat_name: { ms, icon, productivity } }
        """
        result = {}
        for app_name, data in self.app_usage.items():
            if app_name not in BROWSER_APPS:
                continue
            for title, ms in data['windows'].items():
                sub_cat, icon, productivity = classify_browser_window(title)
                if sub_cat not in result:
                    result[sub_cat] = {'ms': 0, 'icon': icon, 'productivity': productivity}
                result[sub_cat]['ms'] += ms
        # Include current window if it's a browser
        if self.current_app in BROWSER_APPS and self.current_window and self.app_switch_time:
            pending = (time.time() - self.app_switch_time) * 1000
            sub_cat, icon, productivity = classify_browser_window(self.current_window)
            if sub_cat not in result:
                result[sub_cat] = {'ms': 0, 'icon': icon, 'productivity': productivity}
            result[sub_cat]['ms'] += pending
        # Round and sort
        for v in result.values():
            v['ms'] = round(v['ms'])
        return dict(sorted(result.items(), key=lambda x: -x[1]['ms']))

    def _get_project_summary(self):
        """Summarize project tags with durations."""
        summary = {}
        for tag in self.project_tags:
            proj = tag['project']
            if proj not in summary:
                summary[proj] = {'total_ms': 0, 'icon': tag.get('icon', '🏷️'), 'sessions': 0}
            summary[proj]['total_ms'] += tag['duration_ms']
            summary[proj]['sessions'] += 1

        # Add current active project
        if self.current_project and self.current_project_start:
            pending = (time.time() - self.current_project_start) * 1000
            if self.current_project not in summary:
                summary[self.current_project] = {'total_ms': 0, 'icon': self.current_project_icon or '🏷️', 'sessions': 0}
            summary[self.current_project]['total_ms'] += pending
            summary[self.current_project]['sessions'] += 1

        return dict(sorted(summary.items(), key=lambda x: -x[1]['total_ms']))

    def get_stats(self):
        with self.lock:
            now = time.time()
            mouse_miles = self.mouse_distance_px / PIXELS_PER_MILE
            scroll_miles = self.scroll_distance_px / PIXELS_PER_MILE
            mouse_feet = self.mouse_distance_px / PIXELS_PER_FOOT
            scroll_feet = self.scroll_distance_px / PIXELS_PER_FOOT
            total = self.active_time_ms + self.idle_time_ms
            active_pct = (self.active_time_ms / total * 100) if total > 0 else 0
            status = 'active'
            idle_duration_s = 0
            if not self.is_active:
                idle_duration_s = (now - self.idle_start) if self.idle_start else 0
                status = 'away' if idle_duration_s > AWAY_THRESHOLD else 'idle'
            total_sleep_ms = sum(p['duration'] for p in self.sleep_periods)

            return {
                'status': status,
                'session_start': self.session_start * 1000,
                'session_duration': (now - self.session_start) * 1000,
                'active_time_ms': self.active_time_ms,
                'idle_time_ms': self.idle_time_ms,
                'active_percent': round(active_pct, 1),

                'keystrokes': self.keystrokes,
                'clicks': self.clicks,
                'left_clicks': self.left_clicks,
                'right_clicks': self.right_clicks,
                'middle_clicks': self.middle_clicks,
                'scrolls': self.scrolls,
                'scroll_up': self.scroll_up,
                'scroll_down': self.scroll_down,
                'mouse_moves': self.mouse_moves,
                'total_interactions': self.keystrokes + self.clicks + self.scrolls,

                'kpm': len(self.recent_keys),
                'cpm': len(self.recent_clicks),
                'spm': len(self.recent_scrolls),
                'peak_kpm': self.peak_kpm,
                'peak_cpm': self.peak_cpm,
                'peak_spm': self.peak_spm,

                'mouse_distance_px': round(self.mouse_distance_px),
                'mouse_distance_miles': round(mouse_miles, 6),
                'mouse_distance_feet': round(mouse_feet, 1),
                'scroll_distance_px': round(self.scroll_distance_px),
                'scroll_distance_miles': round(scroll_miles, 6),
                'scroll_distance_feet': round(scroll_feet, 1),

                'key_categories': dict(self.key_categories),

                'hourly_keys': list(self.hourly_keys),
                'hourly_clicks': list(self.hourly_clicks),
                'hourly_scrolls': list(self.hourly_scrolls),
                'hourly_active': list(self.hourly_active),
                'hourly_idle': list(self.hourly_idle),
                'hourly_mouse_dist': [round(d, 1) for d in self.hourly_mouse_dist],
                'hourly_scroll_dist': [round(d, 1) for d in self.hourly_scroll_dist],

                'typing_sessions': self.typing_sessions[-50:],
                'idle_periods': self.idle_periods[-50:],
                'sleep_periods': self.sleep_periods[-50:],
                'activity_log': self.activity_log[-150:],
                'idle_annotations': self.idle_annotations[-50:],

                'total_sleep_ms': total_sleep_ms,
                'monitor_dpi': MONITOR_DPI,
                'idle_threshold': IDLE_THRESHOLD,
                'away_threshold': AWAY_THRESHOLD,
                'timestamp': now * 1000,

                'can_track_apps': CAN_TRACK_APPS,
                'current_app': self.current_app,
                'current_window': self._clean_window_title(self.current_window, self.current_app) if self.current_window and self.current_app else '',
                'current_browser_subcat': (lambda: classify_browser_window(self.current_window) if self.current_app in BROWSER_APPS and self.current_window else None)(),
                'top_apps': self._get_top_apps(20),
                'app_categories': self._get_category_breakdown(),
                'browser_subcategories': self._get_browser_subcategory_breakdown(),
                'app_switches': self.app_switches[-100:],

                'current_project': self.current_project,
                'current_project_icon': self.current_project_icon,
                'project_tags': self.project_tags[-200:],
                'project_summary': self._get_project_summary(),
            }

    def get_history(self):
        history = {}
        # 1. Get Today's live data
        today = datetime.now().strftime('%Y-%m-%d')
        with self.lock:
            history[today] = {
                'active_time_ms': self.active_time_ms,
                'idle_time_ms': self.idle_time_ms,
                'keystrokes': self.keystrokes,
                'clicks': self.clicks,
                'scrolls': self.scrolls,
                'mouse_distance_px': round(self.mouse_distance_px),
                'scroll_distance_px': round(self.scroll_distance_px),
                'hourly_active': list(self.hourly_active),
                'peak_kpm': self.peak_kpm,
                'typing_sessions': len(self.typing_sessions),
                'top_apps': self._get_top_apps(10),
                'idle_annotations': self.idle_annotations[-20:],
                'project_summary': self._get_project_summary(),
                'project_tags': self.project_tags[-50:],
                'app_categories': self._get_category_breakdown(),
                'browser_subcategories': self._get_browser_subcategory_breakdown(),
            }

        # 2. Get all historical files
        # We scan the directory for ALL activity_*.json files to ensure infinite scrollback
        for filepath in self.data_dir.glob('activity_*.json'):
            date = filepath.stem.replace('activity_', '')
            if date == today:
                continue # Already added live data

            try:
                with open(filepath) as f:
                    data = json.load(f)
                
                # Reconstruct top apps summary
                saved_apps = data.get('app_usage', {})
                top_apps = sorted(
                    [{'app': k, 'total_ms': v.get('total_ms', 0)} for k, v in saved_apps.items()],
                    key=lambda x: -x['total_ms']
                )[:10]

                # Reconstruct app categories
                app_categories = {}
                for app_name, app_data in saved_apps.items():
                    cat = self._get_app_category(app_name)
                    app_categories[cat] = app_categories.get(cat, 0) + app_data.get('total_ms', 0)
                app_categories = dict(sorted(app_categories.items(), key=lambda x: -x[1]))

                # Reconstruct browser sub-categories
                browser_subcategories = self._build_browser_subcats_from_app_usage(saved_apps)
                
                # Reconstruct project summary
                proj_summary = {}
                for tag in data.get('project_tags', []):
                    p = tag.get('project', 'Other')
                    if p not in proj_summary:
                        proj_summary[p] = {'total_ms': 0, 'icon': tag.get('icon', '🏷️'), 'sessions': 0}
                    proj_summary[p]['total_ms'] += tag.get('duration_ms', 0)
                    proj_summary[p]['sessions'] += 1

                history[date] = {
                    'active_time_ms': data.get('active_time_ms', 0),
                    'idle_time_ms': data.get('idle_time_ms', 0),
                    'keystrokes': data.get('keystrokes', 0),
                    'clicks': data.get('clicks', 0),
                    'scrolls': data.get('scrolls', 0),
                    'mouse_distance_px': data.get('mouse_distance_px', 0),
                    'scroll_distance_px': data.get('scroll_distance_px', 0),
                    'hourly_active': data.get('hourly_active', [0] * 24),
                    'peak_kpm': data.get('peak_kpm', 0),
                    'typing_sessions': data.get('typing_sessions_count', len(data.get('typing_sessions', []))),
                    'top_apps': top_apps,
                    'idle_annotations': data.get('idle_annotations', []),
                    'project_summary': proj_summary,
                    'project_tags': data.get('project_tags', []),
                    'app_categories': app_categories,
                    'browser_subcategories': browser_subcategories,
                }
            except Exception:
                pass
        return history

    def get_available_dates(self):
        """Return a list of all dates that have saved data files."""
        dates = []
        for f in sorted(self.data_dir.glob('activity_*.json'), reverse=True):
            date_str = f.stem.replace('activity_', '')
            # Validate format
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
                dates.append(date_str)
            except ValueError:
                pass
        return {'dates': dates, 'total': len(dates)}

    def get_day_data(self, date_str):
        """Return full detailed data for a specific date."""
        today = datetime.now().strftime('%Y-%m-%d')

        # If requesting today, return live stats
        if date_str == today:
            return self.get_stats()

        filepath = self.data_dir / f"activity_{date_str}.json"
        if not filepath.exists():
            return {'error': f'No data for {date_str}'}

        try:
            with open(filepath) as f:
                data = json.load(f)

            # Build top_apps from app_usage
            saved_apps = data.get('app_usage', {})
            top_apps = []
            for app_name, app_data in sorted(saved_apps.items(), key=lambda x: -x[1].get('total_ms', 0))[:20]:
                windows = sorted(
                    [{'title': t, 'ms': round(ms)} for t, ms in app_data.get('windows', {}).items()],
                    key=lambda x: -x['ms']
                )[:8]
                cat = self._get_app_category(app_name)
                top_apps.append({
                    'app': app_name,
                    'total_ms': round(app_data.get('total_ms', 0)),
                    'category': cat,
                    'windows': windows,
                })

            # Build category breakdown
            app_categories = {}
            for app_data in top_apps:
                cat = app_data['category']
                app_categories[cat] = app_categories.get(cat, 0) + app_data['total_ms']
            app_categories = dict(sorted(app_categories.items(), key=lambda x: -x[1]))

            # Build project summary
            proj_summary = {}
            for tag in data.get('project_tags', []):
                p = tag.get('project', 'Other')
                if p not in proj_summary:
                    proj_summary[p] = {'total_ms': 0, 'icon': tag.get('icon', '🏷️'), 'sessions': 0}
                proj_summary[p]['total_ms'] += tag.get('duration_ms', 0)
                proj_summary[p]['sessions'] += 1

            # Distance calculations
            mouse_px = data.get('mouse_distance_px', 0)
            scroll_px = data.get('scroll_distance_px', 0)
            mouse_miles = mouse_px / PIXELS_PER_MILE
            scroll_miles = scroll_px / PIXELS_PER_MILE
            mouse_feet = mouse_px / PIXELS_PER_FOOT
            scroll_feet = scroll_px / PIXELS_PER_FOOT

            active_ms = data.get('active_time_ms', 0)
            idle_ms = data.get('idle_time_ms', 0)
            total = active_ms + idle_ms
            active_pct = (active_ms / total * 100) if total > 0 else 0

            return {
                'date': date_str,
                'is_historical': True,
                'status': 'historical',
                'session_start': data.get('session_start', 0) * 1000 if data.get('session_start') else 0,
                'session_duration': 0,
                'active_time_ms': active_ms,
                'idle_time_ms': idle_ms,
                'active_percent': round(active_pct, 1),
                'keystrokes': data.get('keystrokes', 0),
                'clicks': data.get('clicks', 0),
                'left_clicks': data.get('left_clicks', 0),
                'right_clicks': data.get('right_clicks', 0),
                'middle_clicks': data.get('middle_clicks', 0),
                'scrolls': data.get('scrolls', 0),
                'scroll_up': data.get('scroll_up', 0),
                'scroll_down': data.get('scroll_down', 0),
                'mouse_moves': data.get('mouse_moves', 0),
                'total_interactions': data.get('keystrokes', 0) + data.get('clicks', 0) + data.get('scrolls', 0),
                'kpm': 0, 'cpm': 0, 'spm': 0,
                'peak_kpm': data.get('peak_kpm', 0),
                'peak_cpm': data.get('peak_cpm', 0),
                'peak_spm': data.get('peak_spm', 0),
                'mouse_distance_px': round(mouse_px),
                'mouse_distance_miles': round(mouse_miles, 6),
                'mouse_distance_feet': round(mouse_feet, 1),
                'scroll_distance_px': round(scroll_px),
                'scroll_distance_miles': round(scroll_miles, 6),
                'scroll_distance_feet': round(scroll_feet, 1),
                'key_categories': data.get('key_categories', {}),
                'hourly_keys': data.get('hourly_keys', [0]*24),
                'hourly_clicks': data.get('hourly_clicks', [0]*24),
                'hourly_scrolls': data.get('hourly_scrolls', [0]*24),
                'hourly_active': data.get('hourly_active', [0]*24),
                'hourly_idle': data.get('hourly_idle', [0]*24),
                'hourly_mouse_dist': data.get('hourly_mouse_dist', [0]*24),
                'hourly_scroll_dist': data.get('hourly_scroll_dist', [0]*24),
                'typing_sessions': data.get('typing_sessions', [])[-50:],
                'idle_periods': data.get('idle_periods', [])[-50:],
                'sleep_periods': data.get('sleep_periods', [])[-50:],
                'activity_log': data.get('activity_log', [])[-150:],
                'idle_annotations': data.get('idle_annotations', [])[-50:],
                'total_sleep_ms': sum(p.get('duration', 0) for p in data.get('sleep_periods', [])),
                'monitor_dpi': MONITOR_DPI,
                'idle_threshold': IDLE_THRESHOLD,
                'away_threshold': AWAY_THRESHOLD,
                'timestamp': 0,
                'can_track_apps': True,
                'current_app': None,
                'current_window': '',
                'current_browser_subcat': None,
                'top_apps': top_apps,
                'app_categories': app_categories,
                'browser_subcategories': self._build_browser_subcats_from_app_usage(saved_apps),
                'app_switches': data.get('app_switches', [])[-100:],
                'current_project': data.get('current_project'),
                'current_project_icon': data.get('current_project_icon'),
                'project_tags': data.get('project_tags', [])[-200:],
                'project_summary': proj_summary,
            }
        except Exception as e:
            return {'error': f'Failed to load data: {str(e)}'}

    # ============ PERSISTENCE ============

    def save_data(self):
        today = datetime.now().strftime('%Y-%m-%d')
        filepath = self.data_dir / f"activity_{today}.json"
        with self.lock:
            # Finalize current project time for saving
            project_tags_to_save = list(self.project_tags)

            data = {
                'date': today,
                'saved_at': datetime.now().isoformat(),
                'saved_at_epoch': time.time(),
                'keystrokes': self.keystrokes,
                'clicks': self.clicks,
                'left_clicks': self.left_clicks,
                'right_clicks': self.right_clicks,
                'middle_clicks': self.middle_clicks,
                'scrolls': self.scrolls,
                'scroll_up': self.scroll_up,
                'scroll_down': self.scroll_down,
                'scroll_distance_px': self.scroll_distance_px,
                'mouse_distance_px': self.mouse_distance_px,
                'mouse_moves': self.mouse_moves,
                'active_time_ms': self.active_time_ms,
                'idle_time_ms': self.idle_time_ms,
                'peak_kpm': self.peak_kpm,
                'peak_cpm': self.peak_cpm,
                'peak_spm': self.peak_spm,
                'key_categories': dict(self.key_categories),
                'hourly_keys': list(self.hourly_keys),
                'hourly_clicks': list(self.hourly_clicks),
                'hourly_scrolls': list(self.hourly_scrolls),
                'hourly_active': list(self.hourly_active),
                'hourly_idle': list(self.hourly_idle),
                'hourly_mouse_dist': list(self.hourly_mouse_dist),
                'hourly_scroll_dist': list(self.hourly_scroll_dist),
                'typing_sessions': self.typing_sessions[-200:],
                'typing_sessions_count': len(self.typing_sessions),
                'idle_periods': self.idle_periods[-100:],
                'sleep_periods': self.sleep_periods[-100:],
                'activity_log': self.activity_log[-200:],
                'idle_annotations': self.idle_annotations[-200:],
                'session_start': self.session_start,
                'app_usage': self.app_usage,
                'app_switches': self.app_switches[-200:],
                'current_app': self.current_app,
                'project_tags': project_tags_to_save[-500:],
                'current_project': self.current_project,
                'current_project_icon': self.current_project_icon,
                'current_project_start': self.current_project_start,
            }
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"  [ERROR] Save failed: {e}")

    def load_data(self):
        today = datetime.now().strftime('%Y-%m-%d')
        filepath = self.data_dir / f"activity_{today}.json"
        if not filepath.exists():
            return
        try:
            with open(filepath) as f:
                data = json.load(f)
            if data.get('date') != today:
                return
            self.keystrokes = data.get('keystrokes', 0)
            self.clicks = data.get('clicks', 0)
            self.left_clicks = data.get('left_clicks', 0)
            self.right_clicks = data.get('right_clicks', 0)
            self.middle_clicks = data.get('middle_clicks', 0)
            self.scrolls = data.get('scrolls', 0)
            self.scroll_up = data.get('scroll_up', 0)
            self.scroll_down = data.get('scroll_down', 0)
            self.scroll_distance_px = data.get('scroll_distance_px', 0)
            self.mouse_distance_px = data.get('mouse_distance_px', 0)
            self.mouse_moves = data.get('mouse_moves', 0)
            self.active_time_ms = data.get('active_time_ms', 0)
            self.idle_time_ms = data.get('idle_time_ms', 0)
            self.peak_kpm = data.get('peak_kpm', 0)
            self.peak_cpm = data.get('peak_cpm', 0)
            self.peak_spm = data.get('peak_spm', 0)
            self.key_categories = data.get('key_categories', self.key_categories)
            self.hourly_keys = data.get('hourly_keys', self.hourly_keys)
            self.hourly_clicks = data.get('hourly_clicks', self.hourly_clicks)
            self.hourly_scrolls = data.get('hourly_scrolls', self.hourly_scrolls)
            self.hourly_active = data.get('hourly_active', self.hourly_active)
            self.hourly_idle = data.get('hourly_idle', self.hourly_idle)
            self.hourly_mouse_dist = data.get('hourly_mouse_dist', self.hourly_mouse_dist)
            self.hourly_scroll_dist = data.get('hourly_scroll_dist', self.hourly_scroll_dist)
            self.typing_sessions = data.get('typing_sessions', [])
            self.idle_periods = data.get('idle_periods', [])
            self.sleep_periods = data.get('sleep_periods', [])
            self.activity_log = data.get('activity_log', [])
            self.idle_annotations = data.get('idle_annotations', [])
            self.app_usage = data.get('app_usage', {})
            self.app_switches = data.get('app_switches', [])
            self.current_app = data.get('current_app', None)
            self.project_tags = data.get('project_tags', [])
            self.current_project = data.get('current_project', None)
            self.current_project_icon = data.get('current_project_icon', None)
            self.current_project_start = data.get('current_project_start', None)
            if self.current_project_start:
                self.current_project_start = time.time()  # Reset to now since we're resuming

            saved_epoch = data.get('saved_at_epoch', 0)
            if saved_epoch > 0:
                gap_seconds = time.time() - saved_epoch
                if gap_seconds > MAX_TICK_GAP:
                    gap_ms = gap_seconds * 1000
                    self.sleep_periods.append({
                        'start': saved_epoch * 1000, 'end': time.time() * 1000,
                        'duration': gap_ms
                    })
                    self._log('system', f'💻 PC was off/sleeping for {self._fmt_dur(gap_ms)} since last save — time EXCLUDED')

            app_count = len(self.app_usage)
            proj_count = len(self.project_tags)
            print(f"  ✅ Loaded today's data: {self.keystrokes} keys, {self.clicks} clicks, {self.scrolls} scrolls, {app_count} apps, {len(self.idle_annotations)} annotations, {proj_count} project tags")
        except Exception as e:
            print(f"  ⚠️  Failed to load data: {e}")

    def clear_today(self):
        with self.lock:
            today = datetime.now().strftime('%Y-%m-%d')
            filepath = self.data_dir / f"activity_{today}.json"
            if filepath.exists():
                filepath.unlink()
            self.__init__()

    # ============ HELPERS ============

    def _log(self, type_, message):
        self.activity_log.append({'time': time.time() * 1000, 'type': type_, 'message': message})
        if len(self.activity_log) > 1000:
            self.activity_log = self.activity_log[-1000:]
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"  [{timestamp}] {message}")

    @staticmethod
    def _fmt_dur(ms):
        s = int(ms / 1000)
        h, s = divmod(s, 3600)
        m, s = divmod(s, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    @staticmethod
    def _fmt_time(ts):
        return datetime.fromtimestamp(ts).strftime('%H:%M:%S')


# ===================== HTTP SERVER =====================

monitor = None


class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.path = '/index.html'
            return SimpleHTTPRequestHandler.do_GET(self)
        elif self.path == '/api/stats':
            self._send_json(monitor.get_stats())
        elif self.path == '/api/history':
            self._send_json(monitor.get_history())
        elif self.path == '/api/available_dates':
            self._send_json(monitor.get_available_dates())
        elif self.path.startswith('/api/day/'):
            date_str = self.path.split('/api/day/')[1].split('?')[0]
            self._send_json(monitor.get_day_data(date_str))
        elif self.path == '/api/clear':
            monitor.clear_today()
            self._send_json({'status': 'cleared'})
        else:
            return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        if self.path == '/api/annotate_idle':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode('utf-8'))
                monitor.annotate_idle(data)
                self._send_json({'status': 'ok'})
            except Exception as e:
                self._send_json({'status': 'error', 'message': str(e)})
        elif self.path == '/api/tag_project':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode('utf-8'))
                monitor.tag_project(data)
                self._send_json({'status': 'ok'})
            except Exception as e:
                self._send_json({'status': 'error', 'message': str(e)})
        else:
            self.send_error(404)

    def _send_json(self, data):
        body = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def shutdown_handler(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    print(f"\n\n  🛑 Received {sig_name} — saving data...")
    if monitor:
        with monitor.lock:
            if monitor.current_typing_session:
                monitor._finalize_typing_session()
            # Finalize current project
            if monitor.current_project and monitor.current_project_start:
                now = time.time()
                duration_ms = (now - monitor.current_project_start) * 1000
                if duration_ms > 1000:
                    monitor.project_tags.append({
                        'project': monitor.current_project,
                        'icon': monitor.current_project_icon or '🏷️',
                        'start': monitor.current_project_start * 1000,
                        'end': now * 1000,
                        'duration_ms': duration_ms,
                        'notes': '',
                    })
        monitor._log('system', f'🛑 Monitor stopped (signal: {sig_name})')
        monitor.save_data()
    print("  💾 Data saved. Goodbye! 👋\n")
    sys.exit(0)


def main():
    global monitor

    print()
    print("=" * 62)
    print("  🖥️  PC ACTIVITY MONITOR — Full System-Wide Tracking")
    print("=" * 62)
    print()
    print(f"  📊 Dashboard     : http://localhost:{PORT}")
    print(f"  💾 Data directory : {DATA_DIR.absolute()}")
    print(f"  ⏱️  Idle threshold : {IDLE_THRESHOLD}s")
    print(f"  🚶 Away threshold : {AWAY_THRESHOLD}s")
    print(f"  💻 Sleep detect   : >{MAX_TICK_GAP}s tick gap")
    print(f"  🖥️  Monitor DPI   : {MONITOR_DPI}")
    print(f"  📱 App tracking   : {'✅ ENABLED' if CAN_TRACK_APPS else '❌ DISABLED'}")
    print(f"  🏷️  Project tags   : ✅ ENABLED")
    print(f"  📝 Idle prompts   : ✅ ENABLED")
    print(f"  📅 History days   : {HISTORY_DAYS}")
    if not CAN_TRACK_APPS:
        if PLATFORM == 'Windows':
            print(f"     ↳ Install: pip install pywin32 psutil")
        elif PLATFORM == 'Linux':
            print(f"     ↳ Install: sudo apt install xdotool && pip install psutil")
    print()
    print("  Tracking: ⌨️ Every keypress | 🖱️ Every click & move")
    print("            🔄 Every scroll  | 📏 Distance in miles")
    if CAN_TRACK_APPS:
        print("            📱 Active window | 📄 File/tab name")
    print("            🏷️ Project tagging | 📝 Idle return prompts")
    print()
    print("  Press Ctrl+C to stop")
    print()
    print("-" * 62)

    monitor = ActivityMonitor()
    monitor._log('system', '🖥️ System-wide PC monitor started — tracking ALL input'
                 + (' + app tracking' if CAN_TRACK_APPS else '')
                 + ' + project tags + idle prompts')

    signal.signal(signal.SIGTERM, shutdown_handler)
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, shutdown_handler)

    kb_listener = keyboard.Listener(on_press=monitor.on_key_press)
    kb_listener.daemon = True
    kb_listener.start()
    print("  ✅ Keyboard listener started")

    ms_listener = mouse.Listener(on_click=monitor.on_click, on_move=monitor.on_move, on_scroll=monitor.on_scroll)
    ms_listener.daemon = True
    ms_listener.start()
    print("  ✅ Mouse listener started")

    if CAN_TRACK_APPS:
        print(f"  ✅ App tracking enabled ({PLATFORM})")

    try:
        server = HTTPServer(('0.0.0.0', PORT), DashboardHandler)
    except OSError as e:
        if 'Address already in use' in str(e) or 'Only one usage' in str(e):
            print(f"\n  ❌ Port {PORT} is already in use!\n")
            sys.exit(1)
        raise

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"  ✅ Dashboard on http://localhost:{PORT}")
    print()
    print("=" * 62)
    print(f"  🎯 Open http://localhost:{PORT} in your browser!")
    print("=" * 62)
    print()

    last_status_time = time.time()
    try:
        save_counter = 0
        while True:
            time.sleep(1)
            monitor.tick()
            save_counter += 1
            if save_counter >= SAVE_INTERVAL:
                monitor.save_data()
                save_counter = 0
            now = time.time()
            if now - last_status_time >= 300:
                last_status_time = now
                with monitor.lock:
                    mouse_mi = monitor.mouse_distance_px / PIXELS_PER_MILE
                    print(f"\n  --- 📊 STATUS ({datetime.now().strftime('%H:%M')}) ---")
                    print(f"  ⌨️ {monitor.keystrokes} keys | 🖱️ {monitor.clicks} clicks | 🔄 {monitor.scrolls} scrolls")
                    print(f"  🏃 Mouse: {mouse_mi:.4f} mi | App: {monitor.current_app or 'N/A'}")
                    print(f"  📱 {len(monitor.app_usage)} apps | 🏷️ Project: {monitor.current_project or 'None'}")
                    print(f"  📝 {len(monitor.idle_annotations)} annotations | 🏷️ {len(monitor.project_tags)} tags")
                    print()
    except KeyboardInterrupt:
        print("\n\n  🛑 Shutting down...")
        with monitor.lock:
            if monitor.current_typing_session:
                monitor._finalize_typing_session()
            if monitor.current_project and monitor.current_project_start:
                now = time.time()
                duration_ms = (now - monitor.current_project_start) * 1000
                if duration_ms > 1000:
                    monitor.project_tags.append({
                        'project': monitor.current_project,
                        'icon': monitor.current_project_icon or '🏷️',
                        'start': monitor.current_project_start * 1000,
                        'end': now * 1000,
                        'duration_ms': duration_ms,
                        'notes': '',
                    })
        monitor._log('system', '🛑 Monitor stopped by user')
        monitor.save_data()
        server.shutdown()
        with monitor.lock:
            mouse_mi = monitor.mouse_distance_px / PIXELS_PER_MILE
            print()
            print("  📊 Final Session Stats:")
            print(f"     ⌨️  Keystrokes  : {monitor.keystrokes:,}")
            print(f"     🖱️  Clicks      : {monitor.clicks:,}")
            print(f"     🔄 Scrolls     : {monitor.scrolls:,}")
            print(f"     🏃 Mouse dist  : {mouse_mi:.4f} miles")
            print(f"     📱 Apps tracked : {len(monitor.app_usage)}")
            print(f"     🏷️  Project tags : {len(monitor.project_tags)}")
            print(f"     📝 Annotations : {len(monitor.idle_annotations)}")
            print(f"     💾 Data saved to: {DATA_DIR.absolute()}")
        print("\n  Goodbye! 👋\n")


if __name__ == '__main__':
    main()
