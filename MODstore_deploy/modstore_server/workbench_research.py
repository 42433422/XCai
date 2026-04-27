"""工作台：联网搜索 + GitHub 公开元数据/README，生成规划用 context_pack（受控出站）。"""

from __future__ import annotations

import os
import re
from html import unescape
from urllib.parse import quote_plus, urlparse, parse_qs, unquote
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

# 每用户每日调用上限（内存计数，进程重启清零）
_RESEARCH_DAILY_CAP = 40
_research_daily: Dict[int, Tuple[date, int]] = {}

_GH_URL_RE = re.compile(
    r"https?://github\.com/([a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38})/([a-zA-Z0-9._-]+)",
    re.IGNORECASE,
)

# 非仓库路径的常见第一段（避免把 /features/apps 当成 owner）
_SKIP_FIRST_SEG = frozenset(
    {
        "topics",
        "apps",
        "features",
        "sponsors",
        "settings",
        "organizations",
        "explore",
        "marketplace",
        "login",
        "signup",
        "security",
        "team",
        "enterprise",
        "readme",
    }
)


def _today_research_count(user_id: int) -> Tuple[bool, int]:
    """返回 (allowed, current_count_after_increment)."""
    d = date.today()
    prev = _research_daily.get(user_id)
    if not prev or prev[0] != d:
        _research_daily[user_id] = (d, 1)
        return True, 1
    n = prev[1] + 1
    if prev[1] >= _RESEARCH_DAILY_CAP:
        return False, prev[1]
    _research_daily[user_id] = (d, n)
    return True, n


def _extract_github_pairs(text: str, limit: int = 24) -> List[Tuple[str, str]]:
    seen: Set[Tuple[str, str]] = set()
    out: List[Tuple[str, str]] = []
    for m in _GH_URL_RE.finditer(text or ""):
        owner, repo = m.group(1).lower(), m.group(2).lower()
        if owner in _SKIP_FIRST_SEG or repo.endswith(".git"):
            repo = repo[:-4] if repo.endswith(".git") else repo
        if not owner or not repo:
            continue
        key = (owner, repo)
        if key in seen:
            continue
        seen.add(key)
        out.append((m.group(1), m.group(2)))  # 保留原始大小写供 API
        if len(out) >= limit:
            break
    return out


def _tavily_key() -> str:
    return (os.environ.get("MODSTORE_TAVILY_API_KEY") or os.environ.get("TAVILY_API_KEY") or "").strip()


def _github_token() -> str:
    return (os.environ.get("GITHUB_TOKEN") or os.environ.get("MODSTORE_GITHUB_TOKEN") or "").strip()


def _format_web_result_item(
    title: str,
    url: str,
    content: str,
    per_content_cap: int = 420,
) -> str:
    t = (title or "").strip() or "（无标题）"
    u = (url or "").strip()
    c = _truncate((content or "").strip(), per_content_cap)
    lines = [f"### {t}"]
    if u:
        lines.append(f"URL: {u}")
    if c:
        lines.append(f"摘要: {c}")
    return "\n".join(lines)


async def _tavily_search(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    key = _tavily_key()
    if not key:
        return []
    body = {
        "api_key": key,
        "query": query[:500],
        "search_depth": "basic",
        "include_answer": False,
        "max_results": max(1, min(max_results, 15)),
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post("https://api.tavily.com/search", json=body)
        r.raise_for_status()
        data = r.json()
    results = data.get("results")
    return results if isinstance(results, list) else []


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _ddg_result_url(raw: str) -> str:
    url = unescape(raw or "").strip()
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        q = parse_qs(parsed.query)
        uddg = q.get("uddg", [""])[0]
        if uddg:
            return unquote(uddg)
    return url


async def _duckduckgo_html_search(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Free best-effort fallback. Uses DuckDuckGo HTML result snippets only."""
    url = f"https://duckduckgo.com/html/?q={quote_plus(query[:500])}"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MODstore-Workbench/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    }
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        html = r.text or ""

    blocks = re.findall(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>[\s\S]*?(?:<a[^>]+class="result__snippet"[^>]*>(.*?)</a>|<div[^>]+class="result__snippet"[^>]*>(.*?)</div>)',
        html,
        flags=re.IGNORECASE,
    )
    out: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for href, title_html, snippet_a, snippet_div in blocks:
        result_url = _ddg_result_url(href)
        if not result_url or result_url in seen:
            continue
        seen.add(result_url)
        title = _strip_html(title_html)
        content = _strip_html(snippet_a or snippet_div)
        if not title and not content:
            continue
        out.append({"title": title or result_url, "url": result_url, "content": content})
        if len(out) >= max_results:
            break
    return out


async def _github_repo_meta(owner: str, repo: str, token: str) -> Dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "MODstore-Workbench/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"https://api.github.com/repos/{owner}/{repo}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url, headers=headers)
        if r.status_code != 200:
            return {}
        try:
            data = r.json()
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}


async def _github_readme_raw(owner: str, repo: str, token: str) -> str:
    headers = {
        "Accept": "application/vnd.github.raw",
        "User-Agent": "MODstore-Workbench/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"https://api.github.com/repos/{owner}/{repo}/readme"
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url, headers=headers)
        if r.status_code in (404, 409):
            return ""
        if r.status_code != 200:
            return ""
        raw = r.text or ""
        return raw.strip()


def _truncate(s: str, max_len: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


async def build_research_context(
    *,
    brief: str,
    intent: str,
    max_repos: int,
    max_chars: int,
    max_web: int,
    user_id: int,
) -> Dict[str, Any]:
    warnings: List[str] = []
    sources: List[Dict[str, str]] = []

    brief = (brief or "").strip()
    if len(brief) < 3:
        return {
            "ok": False,
            "context_pack": "",
            "sources": [],
            "warnings": [],
            "error": "brief 过短",
        }

    allowed, _ = _today_research_count(user_id)
    if not allowed:
        return {
            "ok": False,
            "context_pack": "",
            "sources": [],
            "warnings": ["今日联网收集次数已达上限，请明日再试。"],
            "error": "rate_limited",
        }

    intent_hint = {
        "workflow": "工作流 自动化 集成",
        "mod": "后端模块 API",
        "employee": "AI 员工 Agent",
    }.get(intent, "")
    # 通用检索：不强制 site:github.com；GitHub 仓库从结果 URL 与正文中解析
    search_query = f"{brief[:400]} {intent_hint}".strip()

    tavily_results: List[Dict[str, Any]] = []
    pairs_ordered: List[Tuple[str, str]] = []
    if not _tavily_key():
        warnings.append("未配置 MODSTORE_TAVILY_API_KEY（或 TAVILY_API_KEY），已改用免费搜索兜底。")
    else:
        try:
            tavily_results = await _tavily_search(search_query, max_results=12)
        except Exception as e:
            warnings.append(f"搜索服务暂时不可用：{e!s}"[:200])

    if not tavily_results:
        try:
            ddg_results = await _duckduckgo_html_search(search_query, max_results=12)
            if ddg_results:
                tavily_results = ddg_results
                warnings.append("已使用免费搜索兜底结果。")
        except Exception as e:
            warnings.append(f"免费搜索兜底不可用：{e!s}"[:200])

    if tavily_results:
        blob: List[str] = []
        for it in tavily_results:
            if not isinstance(it, dict):
                continue
            blob.append(str(it.get("url") or ""))
            blob.append(str(it.get("title") or ""))
            blob.append(str(it.get("content") or ""))
        text = "\n".join(blob) + "\n" + brief
        found = _extract_github_pairs(text, limit=16)
        for pr in found:
            if pr not in pairs_ordered:
                pairs_ordered.append(pr)

    # 若搜索未命中，仍尝试从用户原文里抠 GitHub 链接
    if not pairs_ordered:
        pairs_ordered = _extract_github_pairs(brief, limit=8)

    max_repos = max(1, min(int(max_repos or 3), 5))
    max_web = max(1, min(int(max_web or 6), 12))
    max_chars = max(1000, min(int(max_chars or 8000), 20000))
    token = _github_token()

    # 网页摘要（仅用 Tavily 返回字段，不抓取任意第三方 URL）
    sep_web = "\n\n---\n\n"
    header_web = "## 网页检索摘要\n\n"
    web_max_total = max(500, int(max_chars * 0.5))
    web_blocks: List[str] = []
    web_run_len = len(header_web)

    if tavily_results:
        for it in tavily_results[:max_web]:
            if not isinstance(it, dict):
                continue
            title = str(it.get("title") or "").strip()
            url = str(it.get("url") or "").strip()
            content = str(it.get("content") or "").strip()
            if not url and not content and not title:
                continue
            item = _format_web_result_item(title, url, content, per_content_cap=420)
            sep = sep_web if web_blocks else ""
            if web_run_len + len(sep) + len(item) > web_max_total:
                room = web_max_total - web_run_len - len(sep)
                if room < 60:
                    warnings.append("网页摘要已达字数上限，部分结果未写入。")
                    break
                item = _truncate(item, room)
            web_blocks.append(item)
            web_run_len += len(sep) + len(item)
            sources.append(
                {
                    "url": url,
                    "title": title or url or "web",
                    "kind": "web",
                }
            )

    web_section = header_web + sep_web.join(web_blocks) if web_blocks else ""

    inter_section = "\n\n---\n\n"
    gh_head = "## GitHub 公开资料\n\n"
    gh_budget = max_chars - len(web_section) - (len(inter_section) if web_section else 0)
    gh_budget = max(0, gh_budget)

    parts: List[str] = []
    used = 0
    gh_consumed = 0
    sep_gh = "\n\n---\n\n"

    for owner, repo in pairs_ordered:
        if used >= max_repos:
            break
        url = f"https://github.com/{owner}/{repo}"
        block_lines: List[str] = [f"### {owner}/{repo}", f"URL: {url}"]
        try:
            meta = await _github_repo_meta(owner, repo, token)
            if meta:
                desc = str(meta.get("description") or "").strip()
                topics = meta.get("topics")
                if isinstance(topics, list) and topics:
                    block_lines.append("Topics: " + ", ".join(str(t) for t in topics[:12]))
                if desc:
                    block_lines.append("Description: " + _truncate(desc, 500))
            readme = await _github_readme_raw(owner, repo, token)
            if readme:
                prefix_cost = (len(gh_head) if not parts else gh_consumed + len(sep_gh)) + len(
                    "\n".join(block_lines)
                )
                readme_cap = gh_budget - prefix_cost - len("README（摘录）:\n") - 8
                readme_cap = max(0, min(4500, readme_cap))
                if readme_cap > 80:
                    block_lines.append("README（摘录）:")
                    block_lines.append(_truncate(readme, readme_cap))
            if len(block_lines) <= 2:
                warnings.append(f"无法读取 {owner}/{repo} 的元数据或 README（可能为私有或 API 受限）。")
                continue
            block = "\n".join(block_lines)
            if not parts:
                needed = len(gh_head) + len(block)
            else:
                needed = gh_consumed + len(sep_gh) + len(block)
            if needed > gh_budget:
                warnings.append("已达到总字数上限，后续仓库未写入。")
                break
            parts.append(block)
            sources.append({"url": url, "title": f"{owner}/{repo}", "kind": "github"})
            used += 1
            gh_consumed = needed
        except Exception as e:
            warnings.append(f"{owner}/{repo} 拉取失败：{e!s}"[:180])

    sections: List[str] = []
    if web_section.strip():
        sections.append(web_section.strip())
    if parts:
        sections.append(gh_head + sep_gh.join(parts))

    pack = "\n\n---\n\n".join(sections).strip() if sections else ""
    pack = _truncate(pack, max_chars)
    return {
        "ok": True,
        "context_pack": pack,
        "sources": sources,
        "warnings": warnings,
    }
