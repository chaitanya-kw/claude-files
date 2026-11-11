#!/usr/bin/env python3
"""Print what the user asked Claude Code each day in a date range, from session transcripts.

Usage:
  extract_sessions.py START END            # user prompts per day (dates YYYY-MM-DD, inclusive, local time)
  extract_sessions.py START END --session ID_PREFIX
                                           # also print Claude's text replies for one session,
                                           # to see what was actually done
"""
import glob, json, os, sys, collections
from datetime import datetime, date, timedelta

ROOT = os.path.expanduser('~/.claude/projects')
HOME_PREFIX = os.path.expanduser('~').replace('/', '-') + '-'
SKIP_PREFIXES = ('<task-notification', '<local-command', '<system-reminder', '[Request interrupted')

def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ' '.join(x.get('text', '') for x in content if isinstance(x, dict) and x.get('type') == 'text')
    return ''

def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    start = date.fromisoformat(sys.argv[1]); end = date.fromisoformat(sys.argv[2])
    session = sys.argv[sys.argv.index('--session') + 1] if '--session' in sys.argv else None
    cutoff = datetime.combine(start - timedelta(days=1), datetime.min.time()).timestamp()
    days = collections.defaultdict(list)
    for f in glob.glob(os.path.join(ROOT, '*', '*.jsonl')):
        if os.path.getmtime(f) < cutoff:
            continue
        sid = os.path.basename(f)[:8]
        if session and not sid.startswith(session[:8]):
            continue
        proj = os.path.basename(os.path.dirname(f)).replace(HOME_PREFIX, '').replace('-', '/')
        for line in open(f, errors='ignore'):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get('isMeta') or d.get('isSidechain') or not d.get('timestamp'):
                continue
            role = d.get('type')
            if role not in ('user', 'assistant') or (role == 'assistant' and not session):
                continue
            t = ' '.join(text_of(d.get('message', {}).get('content')).split())
            if not t or t.startswith(SKIP_PREFIXES):
                continue
            if t.startswith('<command-name>'):
                t = t.split('</command-name>')[0].replace('<command-name>', 'COMMAND ')
                if t.strip() in ('COMMAND /clear', 'COMMAND /exit', 'COMMAND /config'):
                    continue
            ts = datetime.fromisoformat(d['timestamp'].replace('Z', '+00:00')).astimezone()
            if not (start <= ts.date() <= end):
                continue
            limit = 600 if role == 'assistant' else 300
            days[ts.date()].append((ts.strftime('%H:%M'), proj, sid, 'CLAUDE' if role == 'assistant' else 'USER', t[:limit]))
    for day in sorted(days):
        print(f'===== {day} ({day.strftime("%a")})')
        for row in sorted(days[day]):
            print(*row)

if __name__ == '__main__':
    main()
