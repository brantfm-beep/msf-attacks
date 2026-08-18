#!/usr/bin/env python3
"""Refresh the static MSF Attack Planner data from Marvel Church.

This script is used both locally by the project owner and by GitHub Actions.
It writes only validated JSON files into ../data so the public GitHub Pages
site never needs to scrape Marvel Church from a user's browser.
"""
from __future__ import annotations

import html as html_lib
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TEAM_LANDING_URL = "https://www.marvel.church/team-breakdowns-landing-page/"
MODES = {
    "Cosmic Crucible": "https://www.marvel.church/cosmic-crucible-counters/",
    "Alliance War": "https://www.marvel.church/defense-team-counters/",
}
RATING_SCORE = {"▲▲▲":50,"▲▲":40,"▲":30,"⊜":20,"▼":10,"▼▼":5,"▼▼▼":0,"":15}
STOP_PHRASES = {
    "burn attack","burn attacks","then","stage","room","no","with",
    "all other skirmishers","striker","skirmisher","raider","fortifier",
}

@dataclass
class Counter:
    display: str
    rating: str = ""
    notes: str = ""
    tokens: Set[str] = field(default_factory=set)
    @property
    def score(self): return RATING_SCORE.get(self.rating, 15)

@dataclass
class Defense:
    group: str
    variant: str
    counters: List[Counter] = field(default_factory=list)

def clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(s or "").replace("\xa0"," ")).strip()

def extract_rating(text: str) -> str:
    m = re.findall(r"▲{1,3}|▼{1,3}|⊜", text)
    return max(m,key=len) if m else ""

def strip_rating(text: str) -> str:
    return clean_text(re.sub(r"(?:▲{1,3}|▼{1,3}|⊜)","",text))

def attacker_tokens(text: str) -> Set[str]:
    t=strip_rating(text)
    t=re.sub(r"\((?:no|without|instead of)\s+[^)]*\)","",t,flags=re.I)
    t=re.sub(r"^\s*\d+\s+burn attacks?\s*(?:and\s+then)?\s*:\s*","",t,flags=re.I)
    t=re.sub(r"\s+[–—-]\s+\d+\s*$","",t)
    t=re.split(r"\s+[–—]\s+(?=use\b|start\b|make\b|target\b)",t,maxsplit=1,flags=re.I)[0]
    parts=re.split(r"\s*\+\s*|\s*/\s*",t)
    out=set()
    for p in parts:
        p=clean_text(p.strip(" ,.;:-"))
        p=re.sub(r"\s*\([^)]*(?:striker|skirmisher|raider|fortifier)[^)]*\)\s*$","",p,flags=re.I)
        if not p or len(p)<2: continue
        low=p.casefold()
        if any(low==s or low.startswith(s+" ") for s in STOP_PHRASES): continue
        p=re.split(r"\s*\((?:you|they|this|make|needs?|if)\b",p,maxsplit=1,flags=re.I)[0].strip()
        if p: out.add(p.casefold())
    return out

def leaf_li_entries(ul, prefix=""):
    entries=[]
    for li in ul.find_all("li", recursive=False):
        nested=li.find("ul", recursive=False)
        bits=[]
        for child in li.contents:
            if getattr(child,"name",None)=="ul": continue
            bits.append(child.get_text(" ",strip=True) if hasattr(child,"get_text") else str(child))
        direct=clean_text(" ".join(bits))
        if nested:
            entries.extend(leaf_li_entries(nested, clean_text(" ".join(x for x in (prefix,direct) if x))))
        elif direct:
            entries.append(clean_text(" ".join(x for x in (prefix,direct) if x)))
    return entries

def parse_crucible(html_text):
    soup=BeautifulSoup(html_text,"html.parser")
    start=soup.find("h2",id="season-counters") or next((h for h in soup.find_all("h2") if clean_text(h.get_text()).casefold()=="season counters"),None)
    if not start: raise ValueError("Could not find Cosmic Crucible Season Counters section.")
    season="Unknown Season"; prev=start.find_previous("h2")
    while prev:
        txt=clean_text(prev.get_text(" ",strip=True)); m=re.search(r"\bSeason\s+\d+\b",txt,re.I)
        if m: season=m.group(0); break
        prev=prev.find_previous("h2")
    merged={}; current_group=""; current_variant=""; node=start.find_next_sibling()
    while node:
        name=getattr(node,"name",None)
        if name=="h2": break
        if name=="h3": current_group=clean_text(node.get_text(" ",strip=True)).rstrip(":"); current_variant=""
        elif name=="h4": current_variant=clean_text(node.get_text(" ",strip=True)).rstrip(":")
        elif name=="ul" and current_group:
            variant=current_variant or current_group
            d=merged.setdefault((current_group,variant),Defense(current_group,variant))
            for raw in leaf_li_entries(node):
                rating=extract_rating(raw); display=strip_rating(raw)
                d.counters.append(Counter(display,rating,"",attacker_tokens(display)))
        node=node.find_next_sibling()
    defs=[d for d in merged.values() if d.counters]
    if not defs: raise ValueError("No Crucible counters parsed.")
    return season, defs

def war_strategy_map_after(ul):
    notes={}; node=ul.find_next_sibling()
    while node:
        name=getattr(node,"name",None)
        if name in ("h2","h3"): break
        if name=="p":
            txt=clean_text(node.get_text(" ",strip=True)); strong=node.find("strong")
            if strong:
                n=clean_text(strong.get_text(" ",strip=True))
                if re.fullmatch(r"\d+",n):
                    rest=re.sub(rf"^\s*{re.escape(n)}\s*[–—-]\s*","",txt).strip()
                    if rest: notes[n]=rest
        node=node.find_next_sibling()
    return notes

def parse_war(html_text):
    soup=BeautifulSoup(html_text,"html.parser")
    season="Current War Season"
    sh=next((h for h in soup.find_all("h3") if clean_text(h.get_text(" ",strip=True)).casefold().startswith("war season")),None)
    if sh:
        season=re.sub(r"^War Season\s*[–—:-]\s*","",clean_text(sh.get_text(" ",strip=True)),flags=re.I) or season
    defs=[]
    skip={"intro","explanation","conclusion"}
    for h in soup.find_all(["h2","h3"]):
        title=clean_text(h.get_text(" ",strip=True)).rstrip(":"); low=title.casefold()
        if not title or low in skip or low.startswith("war season"): continue
        node=h.find_next_sibling(); ul=None
        while node:
            name=getattr(node,"name",None)
            if name in ("h2","h3"): break
            if name=="ul": ul=node; break
            node=node.find_next_sibling()
        if ul is None: continue
        entries=leaf_li_entries(ul)
        if not entries or not any(extract_rating(x) for x in entries): continue
        strategy=war_strategy_map_after(ul); counters=[]
        for raw in entries:
            rating=extract_rating(raw); display=strip_rating(raw); ref=""
            m=re.search(r"\s+[–—-]\s*(\d+)\s*$",display)
            if m: ref=m.group(1); display=clean_text(display[:m.start()])
            counters.append(Counter(display,rating,strategy.get(ref,""),attacker_tokens(display)))
        if counters: defs.append(Defense(title,title,counters))
    unique={}
    for d in defs: unique.setdefault(d.variant.casefold(),d)
    defs=list(unique.values())
    if not defs: raise ValueError("No War counters parsed.")
    return season, defs

def fetch_urllib(url: str) -> str:
    req=urllib.request.Request(url,headers={
        "User-Agent":"Mozilla/5.0 AppleWebKit/537.36 Chrome/151 Safari/537.36",
        "Accept":"text/html,application/xhtml+xml",
    })
    with urllib.request.urlopen(req,timeout=35) as r:
        return r.read().decode("utf-8",errors="replace")

_browser = None
_playwright = None
def fetch(url: str, selector: Optional[str]=None) -> str:
    try:
        return fetch_urllib(url)
    except Exception as direct_error:
        global _browser, _playwright
        try:
            if _browser is None:
                from playwright.sync_api import sync_playwright
                _playwright=sync_playwright().start()
                _browser=_playwright.chromium.launch(headless=True)
            page=_browser.new_page(viewport={"width":1280,"height":900})
            try:
                page.goto(url,wait_until="domcontentloaded",timeout=60000)
                if selector: page.wait_for_selector(selector,timeout=30000)
                return page.content()
            finally:
                page.close()
        except Exception as browser_error:
            raise RuntimeError(f"Direct HTTPS failed: {direct_error}; Chromium failed: {browser_error}")

def parse_team_directory(html_text):
    soup=BeautifulSoup(html_text,"html.parser")
    table=soup.find("table",id="tablepress-4")
    if not table: raise ValueError("Could not find Team Breakdowns list.")
    teams={}
    for a in table.find_all("a",href=True):
        name=clean_text(a.get_text(" ",strip=True)); href=a.get("href","").strip()
        if name and href.startswith("https://www.marvel.church/"): teams[name]=href
    if len(teams)<20: raise ValueError(f"Only found {len(teams)} teams.")
    return dict(sorted(teams.items(),key=lambda x:x[0].casefold()))

def parse_team_members(html_text):
    soup=BeautifulSoup(html_text,"html.parser")
    heading=soup.find(id="team-members") or next((h for h in soup.find_all(["h2","h3"]) if clean_text(h.get_text()).casefold()=="team members"),None)
    if not heading: raise ValueError("Could not find Team Members section.")
    candidates=[]
    for el in heading.find_all_next(["a","h2","h3"]):
        if el is heading: continue
        if getattr(el,"name",None) in ("h2","h3"): break
        txt=clean_text(el.get_text(" ",strip=True)); href=el.get("href","")
        if not txt or not href.startswith("https://www.marvel.church/"): continue
        if txt.casefold() in {"marvel church","discord","search new team"}: continue
        if txt not in candidates: candidates.append(txt)
    if len(candidates)<3:
        raise ValueError(f"Only found {len(candidates)} team members; need at least 3 to use as a partial roster.")
    return candidates[:5]

def fetch_json(url):
    req=urllib.request.Request(url,headers={
        "User-Agent":"Mozilla/5.0 AppleWebKit/537.36 Chrome/151 Safari/537.36",
        "Accept":"application/json,text/plain,*/*",
    })
    with urllib.request.urlopen(req,timeout=35) as r:
        return json.loads(r.read().decode("utf-8",errors="replace"))

def refresh_characters():
    cats=fetch_json("https://www.marvel.church/wp-json/wp/v2/categories?slug=msf-characters&per_page=100")
    if not isinstance(cats,list) or not cats: raise RuntimeError("MSF Characters category not found.")
    cat_id=int(cats[0]["id"]); found=[]; page=1
    while page<=50:
        try:
            posts=fetch_json(f"https://www.marvel.church/wp-json/wp/v2/posts?categories={cat_id}&per_page=100&page={page}&_fields=title,link")
        except urllib.error.HTTPError as e:
            if e.code==400 and page>1: break
            raise
        if not isinstance(posts,list) or not posts: break
        for post in posts:
            title=clean_text(re.sub(r"<[^>]+>","",str((post.get("title") or {}).get("rendered",""))))
            if title: found.append(title)
        if len(posts)<100: break
        page+=1
    found=sorted(set(found),key=str.casefold)
    if len(found)<100: raise RuntimeError(f"Only found {len(found)} characters.")
    return found

def serialize_mode(mode, season, defenses, generated):
    return {
        "mode":mode,
        "season":season,
        "source":f"Marvel Church scheduled refresh ({generated})",
        "defenses":[{
            "group":d.group,"variant":d.variant,
            "counters":[{
                "display":c.display,"rating":c.rating,"notes":c.notes,
                "tokens":sorted(c.tokens),"score":c.score
            } for c in d.counters]
        } for d in defenses]
    }

def atomic_json(path: Path, payload):
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    tmp.replace(path)

def main():
    DATA.mkdir(exist_ok=True)
    generated=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    print(f"Refreshing MSF planner data at {generated}")

    # Counters: validate both before replacing either.
    counter_payload={}
    for mode,url in MODES.items():
        print(f"Fetching {mode} counters...")
        html=fetch(url)
        season,defs=(parse_war(html) if mode=="Alliance War" else parse_crucible(html))
        print(f"  {season}: {len(defs)} defense configurations")
        counter_payload[mode]=serialize_mode(mode,season,defs,generated)
    atomic_json(DATA/"counter-data.json",counter_payload)

    # Team directory.
    print("Fetching team directory...")
    directory=parse_team_directory(fetch(TEAM_LANDING_URL,"#tablepress-4"))
    atomic_json(DATA/"team-directory.json",directory)
    print(f"  {len(directory)} teams")

    # Roster refresh. Preserve an old valid roster if one individual page fails.
    old={}
    try:
        old_payload=json.loads((DATA/"team-rosters.json").read_text(encoding="utf-8"))
        old=old_payload.get("teams",{}) if isinstance(old_payload,dict) else {}
    except Exception:
        pass
    rosters={}; failures=[]
    for i,(team,url) in enumerate(directory.items(),1):
        print(f"[{i}/{len(directory)}] {team}")
        try:
            members=parse_team_members(fetch(url,"#team-members"))
            rosters[team]=members
        except Exception as e:
            prev=old.get(team)
            prev_members=prev if isinstance(prev,list) else (prev.get("members") if isinstance(prev,dict) else None)
            if isinstance(prev_members,list) and 3 <= len(prev_members) <= 5:
                rosters[team]=prev_members
                failures.append(f"{team}: refresh failed; retained previous partial/complete roster ({e})")
            else:
                failures.append(f"{team}: {e}")
    if len(rosters)<max(20,int(len(directory)*0.70)):
        raise RuntimeError(f"Roster refresh validation failed: only {len(rosters)}/{len(directory)} usable rosters.")
    atomic_json(DATA/"team-rosters.json",{"_meta":{"source":"Marvel Church Team Breakdowns","generated_at":generated,"failures":failures},"teams":rosters})
    print(f"  {len(rosters)} usable rosters; {len(failures)} warnings")

    # Characters.
    print("Fetching character directory...")
    characters=refresh_characters()
    # Team pages are a second authoritative source of real character names.
    # Union them into the character directory so defense dropdowns remain useful
    # even if the WordPress character category is temporarily incomplete.
    roster_characters=set()
    for members in rosters.values():
        for member in members:
            member=clean_text(str(member))
            if member:
                roster_characters.add(member)
    merged={}
    for name in list(characters)+sorted(roster_characters,key=str.casefold):
        merged.setdefault(name.casefold(),name)
    characters=sorted(merged.values(),key=str.casefold)
    atomic_json(DATA/"characters.json",{"characters":characters,"source":"Marvel Church character directory + Team Breakdown rosters","generated_at":generated})
    print(f"  {len(characters)} characters")

    status={
        "generated_at":generated,
        "display":f"Marvel Church data updated: {generated.replace('T',' ').replace('Z',' UTC')}",
        "counter_source":"Marvel Church",
        "team_source":"Marvel Church Team Breakdowns",
        "rosters_refreshed":len(rosters),
        "roster_warnings":len(failures),
        "characters_refreshed":True,
        "character_count":len(characters),
    }
    atomic_json(DATA/"data-status.json",status)
    if failures:
        atomic_json(DATA/"refresh-warnings.json",{"generated_at":generated,"warnings":failures})
    elif (DATA/"refresh-warnings.json").exists():
        (DATA/"refresh-warnings.json").unlink()
    print("Refresh complete.")

if __name__=="__main__":
    try:
        main()
    finally:
        if _browser is not None: _browser.close()
        if _playwright is not None: _playwright.stop()
