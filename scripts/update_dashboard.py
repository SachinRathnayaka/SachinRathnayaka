"""Refresh public project links and use a locally generated streak card."""
import html
import json
import os
from pathlib import Path
import re
from datetime import date, timedelta
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
OWNER = 'SachinRathnayaka'


def generate_stats(headers):
    if not os.environ.get('GITHUB_TOKEN'):
        return
    query = 'query { user(login: "SachinRathnayaka") { contributionsCollection { contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } } } } }'
    request = Request('https://api.github.com/graphql', data=json.dumps({'query': query}).encode(),
                      headers={**headers, 'Content-Type': 'application/json'})
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result.get('errors'):
        raise ValueError('GitHub contribution query failed')
    calendar = result['data']['user']['contributionsCollection']['contributionCalendar']
    days = {day['date']: day['contributionCount'] for week in calendar['weeks'] for day in week['contributionDays']}
    longest = running = 0
    for day in sorted(days):
        running = running + 1 if days[day] else 0
        longest = max(longest, running)
    current = 0
    day = date.today()
    if not days.get(day.isoformat()):
        day -= timedelta(days=1)
    while days.get(day.isoformat(), 0):
        current += 1
        day -= timedelta(days=1)
    values = (calendar['totalContributions'], current, longest)
    render_stats(values)


def render_stats(values):
    labels = ('Contributions', 'Current streak', 'Longest streak')
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="660" height="210" viewBox="0 0 660 210" role="img" aria-label="GitHub contribution streak statistics">',
           '<rect x="1" y="1" width="658" height="208" rx="14" fill="#0d1117" stroke="#30363d"/>',
           '<path d="M220 42V172M440 42V172" stroke="#30363d"/>',
           '<circle cx="330" cy="95" r="50" fill="none" stroke="#79c0ff" stroke-width="4"/>',
           '<rect x="309" y="34" width="42" height="30" fill="#0d1117"/>',
           '<path d="M330 31C335 42 345 43 340 54C338 59 333 62 329 61C319 60 315 52 320 45C320 50 323 51 324 48C327 44 326 39 330 31Z" fill="#ff7b72"/>',
           '<text x="110" y="58" text-anchor="middle" fill="#8b949e" font-family="sans-serif" font-size="20">✦</text>',
           '<path d="M544 43h12v12c0 9-12 9-12 0ZM544 46h-6v6c0 6 6 6 6 6M556 46h6v6c0 6-6 6-6 6M550 62v7M543 70h14" fill="none" stroke="#79c0ff" stroke-width="2"/>',
           '<text x="330" y="191" text-anchor="middle" fill="#8b949e" font-family="sans-serif" font-size="12">Past-year contributions and streaks · refreshed daily</text>']
    for x, value, label in zip((110, 330, 550), values, labels):
        svg.append(f'<text x="{x}" y="108" text-anchor="middle" fill="#79c0ff" font-family="sans-serif" font-size="32">{value}</text>')
        label_y = 163 if x == 330 else 143
        svg.append(f'<text x="{x}" y="{label_y}" text-anchor="middle" fill="#c9d1d9" font-family="sans-serif" font-size="14">{label}</text>')
    svg.append('</svg>')
    (ROOT / 'profile').mkdir(exist_ok=True)
    (ROOT / 'profile/streak.svg').write_text('\n'.join(svg), encoding='utf-8')


def replace_section(content, name, body):
    start, end = f'<!-- {name}:START -->', f'<!-- {name}:END -->'
    if content.count(start) != 1 or content.count(end) != 1:
        raise ValueError(f'Missing or duplicated dashboard markers: {name}')
    return re.sub(re.escape(start) + r'.*?' + re.escape(end),
                  lambda _: f'{start}\n{body}\n{end}', content, flags=re.S)


def main():
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'profile-dashboard',
               'X-GitHub-Api-Version': '2022-11-28'}
    if os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    try:
        generate_stats(headers)
    except Exception:
        print('::warning::Contribution refresh unavailable; keeping the previous card. Projects will still update.')
    repositories = []
    for page in range(1, 11):
        request = Request(f'https://api.github.com/users/{OWNER}/repos?type=owner&sort=pushed&per_page=100&page={page}', headers=headers)
        with urlopen(request, timeout=30) as response:
            batch = json.load(response)
        repositories.extend(batch)
        if len(batch) < 100:
            break
    projects = [r for r in repositories if not r['fork'] and not r['archived']
                and not r['private'] and r['name'].lower() != OWNER.lower()]
    projects.sort(key=lambda r: r['pushed_at'], reverse=True)
    lines = []
    for repository in projects[:12]:
        name = html.escape(repository['name'])
        description = html.escape(' '.join((repository['description'] or 'Explore the project and its documentation.').split()))
        lines.append(f"- <a href=\"{repository['html_url']}\"><strong>{name}</strong></a> — {description}")
    body = '\n'.join(lines) or 'Projects will appear here when public repositories are available.'
    readme = ROOT / 'README.md'
    content = replace_section(readme.read_text(encoding='utf-8'), 'PROJECTS', body)
    if (ROOT / 'profile/streak.svg').is_file():
        content = replace_section(content, 'STREAK', '<img src="./profile/streak.svg" height="165" alt="GitHub contribution streak"/>')
    readme.write_text(content, encoding='utf-8')
    print(f'Updated dashboard: {min(len(projects), 12)} public projects.')


if __name__ == '__main__':
    main()
