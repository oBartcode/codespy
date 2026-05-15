from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import httpx
import asyncio
from collections import Counter
from datetime import datetime, timezone
import re
import os

app = FastAPI(title="CodeSpy API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

LANGUAGE_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#2b7489",
    "Java": "#b07219", "C++": "#f34b7d", "C": "#555555", "Go": "#00ADD8",
    "Rust": "#dea584", "Ruby": "#701516", "PHP": "#4F5D95", "Swift": "#ffac45",
    "Kotlin": "#F18E33", "Shell": "#89e051", "HTML": "#e34c26", "CSS": "#563d7c",
    "Vue": "#41b883", "React": "#61dafb", "Dart": "#00B4AB", "R": "#198CE7",
}

async def gh(client: httpx.AsyncClient, url: str):
    r = await client.get(url, headers={**HEADERS, "Accept": "application/vnd.github+json"})
    if r.status_code == 404:
        raise HTTPException(404, "Repositório não encontrado")
    if r.status_code == 403:
        raise HTTPException(403, "Rate limit atingido. Configure GITHUB_TOKEN.")
    r.raise_for_status()
    return r.json()

@app.get("/api/analyze/{owner}/{repo}")
async def analyze_repo(owner: str, repo: str):
    async with httpx.AsyncClient(timeout=30) as client:
        # Busca paralela dos dados principais
        repo_data, languages, contributors, commits_raw = await asyncio.gather(
            gh(client, f"https://api.github.com/repos/{owner}/{repo}"),
            gh(client, f"https://api.github.com/repos/{owner}/{repo}/languages"),
            gh(client, f"https://api.github.com/repos/{owner}/{repo}/contributors?per_page=10"),
            gh(client, f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=100"),
        )

        # Busca issues e releases em paralelo
        try:
            issues_raw, releases = await asyncio.gather(
                gh(client, f"https://api.github.com/repos/{owner}/{repo}/issues?state=all&per_page=100"),
                gh(client, f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=5"),
            )
        except:
            issues_raw, releases = [], []

    # Processa linguagens
    total_bytes = sum(languages.values()) or 1
    langs = [
        {
            "name": lang,
            "bytes": b,
            "percent": round(b / total_bytes * 100, 1),
            "color": LANGUAGE_COLORS.get(lang, "#8b949e"),
        }
        for lang, b in sorted(languages.items(), key=lambda x: -x[1])
    ]

    # Atividade de commits por mês (últimos 12 meses)
    month_counts = Counter()
    for c in commits_raw:
        try:
            date_str = c["commit"]["author"]["date"]
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            key = dt.strftime("%Y-%m")
            month_counts[key] += 1
        except:
            pass

    now = datetime.now(timezone.utc)
    activity = []
    for i in range(11, -1, -1):
        from dateutil.relativedelta import relativedelta
        month = (now - relativedelta(months=i)).strftime("%Y-%m")
        activity.append({"month": month, "commits": month_counts.get(month, 0)})

    # Issues por label
    open_issues = [i for i in issues_raw if i.get("state") == "open" and "pull_request" not in i]
    closed_issues = [i for i in issues_raw if i.get("state") == "closed" and "pull_request" not in i]

    label_counts = Counter()
    for issue in issues_raw:
        for label in issue.get("labels", []):
            label_counts[label["name"]] += 1

    top_labels = [{"name": k, "count": v} for k, v in label_counts.most_common(8)]

    # Score de saúde do repo
    score = calculate_health_score(repo_data, commits_raw, open_issues, closed_issues, langs)

    # Horário de commits (quando o dev programa?)
    hour_counts = Counter()
    for c in commits_raw:
        try:
            date_str = c["commit"]["author"]["date"]
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            hour_counts[dt.hour] += 1
        except:
            pass

    commit_hours = [{"hour": h, "count": hour_counts.get(h, 0)} for h in range(24)]

    # Contribuidores top
    top_contributors = [
        {
            "login": c["login"],
            "avatar": c["avatar_url"],
            "contributions": c["contributions"],
            "url": c["html_url"],
        }
        for c in (contributors if isinstance(contributors, list) else [])[:8]
    ]

    created = datetime.fromisoformat(repo_data["created_at"].replace("Z", "+00:00"))
    updated = datetime.fromisoformat(repo_data["updated_at"].replace("Z", "+00:00"))
    age_days = (datetime.now(timezone.utc) - created).days

    return {
        "repo": {
            "name": repo_data["name"],
            "full_name": repo_data["full_name"],
            "description": repo_data.get("description", ""),
            "url": repo_data["html_url"],
            "stars": repo_data["stargazers_count"],
            "forks": repo_data["forks_count"],
            "watchers": repo_data["watchers_count"],
            "open_issues": repo_data["open_issues_count"],
            "size": repo_data["size"],
            "default_branch": repo_data["default_branch"],
            "license": repo_data.get("license", {}).get("spdx_id", "None") if repo_data.get("license") else "None",
            "topics": repo_data.get("topics", []),
            "created_at": repo_data["created_at"],
            "updated_at": repo_data["updated_at"],
            "age_days": age_days,
            "owner_avatar": repo_data["owner"]["avatar_url"],
        },
        "languages": langs,
        "activity": activity,
        "commit_hours": commit_hours,
        "contributors": top_contributors,
        "issues": {
            "open": len(open_issues),
            "closed": len(closed_issues),
            "labels": top_labels,
        },
        "releases": [
            {"name": r.get("name") or r["tag_name"], "tag": r["tag_name"], "date": r["published_at"]}
            for r in (releases if isinstance(releases, list) else [])
        ],
        "health": score,
    }


def calculate_health_score(repo, commits, open_issues, closed_issues, langs):
    score = 0
    breakdown = []

    # Atividade recente (30 pts)
    recent_commits = len(commits)
    pts = min(30, recent_commits // 3)
    score += pts
    breakdown.append({"label": "Atividade", "pts": pts, "max": 30, "detail": f"{recent_commits} commits recentes"})

    # Documentação (20 pts)
    has_desc = bool(repo.get("description"))
    has_license = bool(repo.get("license"))
    has_topics = len(repo.get("topics", [])) > 0
    doc_pts = (10 if has_desc else 0) + (7 if has_license else 0) + (3 if has_topics else 0)
    score += doc_pts
    breakdown.append({"label": "Documentação", "pts": doc_pts, "max": 20, "detail": "README, licença e tópicos"})

    # Popularidade (20 pts)
    stars = repo.get("stargazers_count", 0)
    pop_pts = min(20, int(stars ** 0.5))
    score += pop_pts
    breakdown.append({"label": "Popularidade", "pts": pop_pts, "max": 20, "detail": f"{stars} estrelas"})

    # Manutenção de issues (20 pts)
    total_issues = len(open_issues) + len(closed_issues)
    if total_issues > 0:
        resolution_rate = len(closed_issues) / total_issues
        iss_pts = int(resolution_rate * 20)
    else:
        iss_pts = 10
    score += iss_pts
    breakdown.append({"label": "Issues", "pts": iss_pts, "max": 20, "detail": f"{len(closed_issues)} resolvidas"})

    # Diversidade de linguagens (10 pts)
    lang_pts = min(10, len(langs) * 2)
    score += lang_pts
    breakdown.append({"label": "Tech Stack", "pts": lang_pts, "max": 10, "detail": f"{len(langs)} linguagens"})

    grade = "S" if score >= 85 else "A" if score >= 70 else "B" if score >= 55 else "C" if score >= 40 else "D"

    return {"score": score, "grade": grade, "breakdown": breakdown}


@app.get("/api/user/{username}")
async def get_user(username: str):
    async with httpx.AsyncClient(timeout=15) as client:
        user = await gh(client, f"https://api.github.com/users/{username}")
        repos = await gh(client, f"https://api.github.com/users/{username}/repos?sort=stars&per_page=6")

    return {
        "login": user["login"],
        "name": user.get("name", user["login"]),
        "avatar": user["avatar_url"],
        "bio": user.get("bio", ""),
        "followers": user["followers"],
        "public_repos": user["public_repos"],
        "top_repos": [
            {"name": r["name"], "stars": r["stargazers_count"], "language": r.get("language", ""), "description": r.get("description", "")}
            for r in repos
        ]
    }


# Serve frontend em produção
if os.path.exists("../frontend/dist"):
    app.mount("/", StaticFiles(directory="../frontend/dist", html=True), name="static")
elif os.path.exists("../frontend/index.html"):
    @app.get("/")
    def serve_frontend():
        return FileResponse("../frontend/index.html")
