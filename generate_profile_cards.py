#!/usr/bin/env python3
"""Build animated, self-contained SVG profile cards from public GitHub data."""
from __future__ import annotations
import html, json, os, re, urllib.request
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

LOGIN = os.environ.get("GITHUB_USERNAME", "thorsenbuilds")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = Path(os.environ.get("PROFILE_CARDS_DIR", "assets/profile-cards"))
GREEN, LIME, MINT, BLUE = "#54f34b", "#b7ff63", "#b4ffd3", "#6468ff"
BG, PANEL, LINE, MUTED, TEXT = "#050907", "#080d0b", "#244b2b", "#78a77d", "#d8ffe0"

def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)

def github_data() -> dict:
    query = """
    query($login:String!) { user(login:$login) {
      name login bio location websiteUrl followers { totalCount }
      repositories(first:100, ownerAffiliations:OWNER, privacy:PUBLIC, orderBy:{field:PUSHED_AT,direction:DESC}) {
        totalCount nodes { name url description stargazerCount forkCount pushedAt isFork isPrivate primaryLanguage { name color }
          languages(first:10, orderBy:SIZE) { totalSize edges { size node { name color } } } }
      }
    } }
    """
    payload=json.dumps({"query":query,"variables":{"login":LOGIN}}).encode()
    request=urllib.request.Request("https://api.github.com/graphql",data=payload,headers={"Authorization":f"Bearer {TOKEN}","Content-Type":"application/json","User-Agent":"thorsen-profile-card-renderer"})
    with urllib.request.urlopen(request,timeout=30) as response: result=json.load(response)
    if result.get("errors"): raise RuntimeError("GitHub GraphQL errors: "+json.dumps(result["errors"]))
    user=result.get("data",{}).get("user")
    if not user: raise RuntimeError(f"GitHub user {LOGIN!r} was not found")
    user["repositories"]["nodes"]=[r for r in user["repositories"]["nodes"] if r and not r.get("isPrivate",False)]
    return user

class ContributionCalendarParser(HTMLParser):
    """Read only GitHub's anonymous public contribution calendar."""
    def __init__(self):
        super().__init__(); self.days=[]; self.heading=[]; self.in_heading=False
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag=="h2" and values.get("id")=="js-contribution-activity-description": self.in_heading=True
        if tag=="td" and values.get("data-date"): self.days.append({"date":values["data-date"],"level":int(values.get("data-level") or 0)})
    def handle_data(self,data):
        if self.in_heading: self.heading.append(data)
    def handle_endtag(self,tag):
        if tag=="h2" and self.in_heading: self.in_heading=False

def public_calendar(login):
    url=f"https://github.com/users/{quote(login,safe='')}/contributions?to={date.today().isoformat()}"
    request=urllib.request.Request(url,headers={"User-Agent":"thorsen-profile-card-renderer","Accept":"text/html","Accept-Language":"en-US,en;q=0.9"})
    with urllib.request.urlopen(request,timeout=30) as response: page=response.read().decode("utf-8",errors="replace")
    parser=ContributionCalendarParser(); parser.feed(page)
    match=re.search(r"([\d,]+)\s+contributions\s+in\s+(\d{4})"," ".join(parser.heading),re.I)
    if not match or not parser.days: raise RuntimeError("Could not parse the public GitHub contribution calendar")
    grouped={}
    for item in parser.days:
        day=date.fromisoformat(item["date"]); week=(day-timedelta(days=day.weekday())).isoformat()
        grouped.setdefault(week,[]).append({"date":item["date"],"weekday":day.weekday(),"level":item["level"]})
    return {"totalContributions":int(match.group(1).replace(",","")),"year":int(match.group(2)),"weeks":[{"contributionDays":sorted(days,key=lambda d:d["weekday"])} for _,days in sorted(grouped.items())]}

def defs(height):
    return f'''<defs>
<linearGradient id="frame" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#60ff48"/><stop offset=".48" stop-color="#185d2b"/><stop offset="1" stop-color="#142c37"/></linearGradient>
<linearGradient id="glass" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#09130c"/><stop offset=".55" stop-color="#060b09"/><stop offset="1" stop-color="#080c13"/></linearGradient>
<radialGradient id="haloA"><stop stop-color="#61ff36" stop-opacity=".42"/><stop offset="1" stop-color="#49ff24" stop-opacity="0"/></radialGradient>
<radialGradient id="haloB"><stop stop-color="#45c9a1" stop-opacity=".26"/><stop offset="1" stop-color="#45c9a1" stop-opacity="0"/></radialGradient>
<linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#7dff42" stop-opacity="0"/><stop offset=".48" stop-color="#a6ff6a" stop-opacity=".64"/><stop offset="1" stop-color="#7dff42" stop-opacity="0"/></linearGradient>
<linearGradient id="ring" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#7bff52"/><stop offset=".55" stop-color="#3bc882"/><stop offset="1" stop-color="{BLUE}"/></linearGradient>
<filter id="blur"><feGaussianBlur stdDeviation="24"/></filter><filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<style>text{{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}} .label{{fill:{MUTED};font-size:12px;letter-spacing:1.1px}} .small{{fill:{MUTED};font-size:11px}} .value{{fill:{TEXT};font-size:16px;font-weight:600}} .accent{{fill:{GREEN}}} .bright{{fill:{LIME}}}
.glow-drift{{animation:drift 8s ease-in-out infinite alternate}} .scan{{animation:scan {max(5,height/100):.1f}s linear infinite}} .pulse{{animation:pulse 2.4s ease-in-out infinite}} .rise{{opacity:0;animation:rise .7s ease-out forwards}} .dash{{stroke-dasharray:650;stroke-dashoffset:650;animation:draw 2.1s ease-out forwards}} .ring-pulse{{transform-box:fill-box;transform-origin:center;animation:ring 4s ease-in-out infinite}}
@keyframes drift{{from{{transform:translate(-24px,-4px);opacity:.72}}to{{transform:translate(22px,8px);opacity:1}}}} @keyframes scan{{from{{transform:translateY(-20px)}}to{{transform:translateY({height+20}px)}}}} @keyframes pulse{{0%,100%{{opacity:.5}}50%{{opacity:1}}}} @keyframes rise{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}} @keyframes draw{{to{{stroke-dashoffset:0}}}} @keyframes ring{{0%,100%{{transform:scale(.96);opacity:.82}}50%{{transform:scale(1.04);opacity:1}}}}
@media(prefers-reduced-motion:reduce){{.glow-drift,.scan,.pulse,.rise,.dash,.ring-pulse{{animation:none!important;opacity:1;transform:none;stroke-dashoffset:0}}}}</style></defs>'''

def shell(width,height,aria,content,inset=26):
    inner=(f'<rect x="{inset}" y="{inset}" width="{width-inset*2}" height="{height-inset*2}" rx="15" fill="{PANEL}" fill-opacity=".68" stroke="#285432" stroke-opacity=".82" stroke-width="1.25"/>' if inset>0 else "")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(aria)}">{defs(height)}
<rect width="{width}" height="{height}" rx="20" fill="{BG}"/><ellipse class="glow-drift" cx="{width*.28:.0f}" cy="0" rx="{width*.3:.0f}" ry="{height*.9:.0f}" fill="url(#haloA)" filter="url(#blur)"/><ellipse class="glow-drift" cx="{width*.78:.0f}" cy="{height*.78:.0f}" rx="{width*.26:.0f}" ry="{height*.64:.0f}" fill="url(#haloB)" filter="url(#blur)"/>
<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="19" fill="url(#glass)" stroke="url(#frame)" stroke-opacity=".88" stroke-width="1.5"/>{inner}{content}</svg>'''

def chrome(width,command,y=29):
    return f'<circle cx="34" cy="{y}" r="5" fill="#ff6969"/><circle cx="52" cy="{y}" r="5" fill="#ffc857"/><circle cx="70" cy="{y}" r="5" fill="{GREEN}"/><text x="{width/2:.0f}" y="{y+4}" text-anchor="middle" class="small">{esc(command)}</text>'

def ascii_portrait(rows=27,cols=57):
    shades=" .,:;irsXA253hMHGS#9B&@"; lines=[]
    for y in range(rows):
        line=[]
        for x in range(cols):
            nx,ny=(x-(cols-1)/2)/(cols*.5),y/(rows-1)
            if ny<.60: hood=(nx/(.28+ny*.18))**2+((ny-.30)/.39)**2<1
            else: hood=abs(nx)<.28+(ny-.60)*.95 and ny<.98
            face=(nx/.27)**2+((ny-.39)/.29)**2<1
            if not hood: ch=" "
            else:
                texture=((x*13+y*7+x*y)%13)/13
                if face and .30<ny<.38 and .07<abs(nx)<.22: ch="#" if abs(nx)>.12 else "%"
                elif face and .39<=ny<.58: ch=" .:-=+*#%"[(int(abs(nx)*38)+y*3)%9]
                elif face: ch=" .,:;irsXA"[min(9,int((texture+.2)*8))]
                else:
                    edge=abs(nx)/(.29+ny*.8); shade=max(0,min(len(shades)-1,int((.94-edge*.50+texture*.20)*(len(shades)-1)))); ch=shades[shade]
            line.append(ch)
        lines.append("".join(line).rstrip())
    return lines

def profile_card(user,repos,calendar):
    width,height=1180,610; login=user["login"]; languages={}
    for repo in repos:
        lang=(repo.get("primaryLanguage") or {}).get("name")
        if lang: languages[lang]=languages.get(lang,0)+1
    language=max(languages,key=languages.get) if languages else "Python"
    active=sum(day["level"]>0 for week in calendar["weeks"] for day in week["contributionDays"])
    stars=sum(r.get("stargazerCount",0) for r in repos)
    body=[chrome(width,"thorsenbuilds@github:~$ ./profile-scan --live",31),
      '<rect x="25" y="57" width="526" height="524" rx="17" fill="#030604" fill-opacity=".78" stroke="#32733a" stroke-width="1.5"/><rect x="563" y="57" width="592" height="524" rx="17" fill="#030604" fill-opacity=".66" stroke="#32733a" stroke-width="1.5"/>',
      '<text x="49" y="86" class="label bright" font-size="13" font-weight="700">VISUAL.MAP</text><text x="589" y="86" class="label bright" font-size="13" font-weight="700">SYSTEM.INFO</text><text x="1128" y="86" text-anchor="end" class="small pulse">● LIVE</text>']
    for i,line in enumerate(ascii_portrait()): body.append(f'<text x="55" y="{119+i*17}" class="bright rise" font-size="14" letter-spacing=".4" opacity="{.70+(i%4)*.07:.2f}" style="animation-delay:{min(i*35,700)}ms" xml:space="preserve">{esc(line)}</text>')
    body.append('<rect class="scan" x="27" y="57" width="524" height="18" fill="url(#sweep)" opacity=".45"/>')
    fields=[("Subject",user.get("name") or login),("Handle","@"+login),("Role","Python developer / applied AI"),("Status","Building  |  Learning  |  Shipping"),("Languages",", ".join([language]+[k for k in languages if k!=language][:2])),("Repositories",str(len(repos))),("Contributions",f'{calendar["totalContributions"]} public'),("Stars",str(stars)),("Followers",str(user.get("followers",{}).get("totalCount",0))),("Active Days",str(active)),("Contact","github.com/"+login)]
    for i,(label,value) in enumerate(fields):
        y=126+i*39; body.append(f'<g class="rise" style="animation-delay:{150+i*90}ms"><text x="591" y="{y}" class="bright" font-size="14" font-weight="700">{esc(label)}</text><text x="805" y="{y}" class="small" text-anchor="end">{"·"*25}</text><text x="825" y="{y}" class="value" font-size="14">{esc(value[:40])}</text><path d="M589 {y+11}H1128" stroke="#193821" stroke-width=".7"/></g>')
    return shell(width,height,"Green terminal profile scan with animated ASCII hooded portrait","".join(body),inset=0)

def render_toolbox(repos):
    width,height=860,190; counts={}
    for repo in repos:
        for edge in (repo.get("languages") or {}).get("edges",[]):
            lang=(edge.get("node") or {}).get("name")
            if lang: counts[lang]=counts.get(lang,0)+int(edge.get("size",0))
    ranked=sorted(counts.items(),key=lambda item:(-item[1],item[0]))[:5]; total=max(sum(counts.values()),1)
    body=[chrome(width,"thorsenbuilds@github:~$ ls skills/",25),'<text x="52" y="73" class="bright" font-size="13" font-weight="700">thorsenbuilds@github:~$</text><text x="274" y="73" class="value">ls skills/</text><path d="M52 88H808" stroke="#1b3221"/>']
    for i,(lang,size) in enumerate(ranked):
        x=52+i*151; pct=round(size*100/total); body.append(f'<g class="rise" style="animation-delay:{i*110}ms"><rect x="{x}" y="102" width="137" height="56" rx="9" fill="url(#glass)" stroke="#356e3a"/><text x="{x+11}" y="125" class="bright" font-size="13" font-weight="700">{esc(lang[:14])}</text><text x="{x+11}" y="145" class="small">{pct}%  ·  {len(repos)} repos</text><rect x="{x+11}" y="151" width="115" height="2" rx="1" fill="#15331c"/><rect x="{x+11}" y="151" width="{max(2,115*pct/100):.1f}" height="2" rx="1" fill="{GREEN}"/></g>')
    if not ranked: body.append('<text x="52" y="128" class="value">No public language data</text>')
    body.append('<text x="808" y="177" text-anchor="end" class="small">OPEN-SOURCE TOOLBOX  /  PUBLIC REPOSITORIES</text>')
    return shell(width,height,"Animated terminal-style public language toolbox","".join(body),inset=14)

def candidate_repos(repos,login):
    filtered=[r for r in repos if r.get("name","").lower()!=login.lower()]
    return sorted(filtered,key=lambda r:(r.get("stargazerCount",0),r.get("pushedAt") or ""),reverse=True)[:2]

def render_projects(repos,login):
    width,height=860,274; items=candidate_repos(repos,login)
    body=[f'<text x="52" y="49" class="label bright">PROJECTS.LIST</text><text x="226" y="49" class="small">./projects.sh --all</text><text x="808" y="49" text-anchor="end" class="small">{len(items)} PROJECTS</text><path d="M52 60H808" stroke="#315f34"/>']
    if not items: body.append('<text x="52" y="115" class="value">No public projects to feature yet.</text>')
    for i,repo in enumerate(items):
        x=52+i*374; y=82; lang_edges=(repo.get("languages") or {}).get("edges",[]); total=(repo.get("languages") or {}).get("totalSize",0)
        lang=(repo.get("primaryLanguage") or {}).get("name") or "Open source"; size=next((e["size"] for e in lang_edges if e.get("node",{}).get("name")==lang),total)
        pct=round(size*100/total) if total else (100 if lang!="Open source" else 0)
        desc=repo.get("description") or "Open-source project"; words=desc.split(); desc_lines=[]; current=""
        for word in words:
            candidate=(current+" "+word).strip()
            if len(candidate)>34 and current: desc_lines.append(current); current=word
            else: current=candidate
            if len(desc_lines)==2: break
        if current and len(desc_lines)<2: desc_lines.append(current)
        if len(desc_lines)==2 and len(" ".join(desc_lines))<len(desc): desc_lines[-1]=desc_lines[-1][:31]+"…"
        try:
            pushed=datetime.fromisoformat((repo.get("pushedAt") or "").replace("Z","+00:00")).date(); age=max((date.today()-pushed).days,0); when=f"updated {age}d ago" if age<30 else f"updated {age//30}mo ago"
        except ValueError: when="public repository"
        body += [f'<g class="rise" style="animation-delay:{i*180}ms"><rect x="{x}" y="{y}" width="354" height="164" rx="14" fill="url(#glass)" stroke="#3a7040" stroke-width="1.3"/><rect x="{x+1}" y="{y+1}" width="352" height="31" rx="13" fill="#102515"/><path d="M{x+1} {y+30}H{x+353}" stroke="#315d37"/>',
          f'<text x="{x+16}" y="{y+21}" class="small">• {esc(login)}/{esc(repo["name"])}</text><circle cx="{x+331}" cy="{y+16}" r="3.8" class="pulse" fill="{LIME}"/>',
          f'<text x="{x+17}" y="{y+60}" class="bright" font-size="18" font-weight="700">{esc(repo["name"][:22])} <tspan class="small">_</tspan></text>',
          f'<text x="{x+17}" y="{y+83}" class="small">{esc(desc_lines[0] if desc_lines else "Open-source project")}</text><text x="{x+17}" y="{y+98}" class="small">{esc(desc_lines[1] if len(desc_lines)>1 else "")}</text>',
          f'<rect x="{x+17}" y="{y+111}" width="68" height="20" rx="10" fill="#102817" stroke="#3b8743"/><text x="{x+51}" y="{y+125}" text-anchor="middle" class="small bright">{esc(lang[:11])}</text>',
          f'<text x="{x+17}" y="{y+145}" class="small">★ {repo.get("stargazerCount",0)}  ·  {esc(when)}</text>',
          f'<circle cx="{x+302}" cy="{y+96}" r="24" fill="none" stroke="#14261c" stroke-width="5"/><circle class="ring-pulse" cx="{x+302}" cy="{y+96}" r="24" fill="none" stroke="url(#ring)" stroke-width="5" stroke-linecap="round" pathLength="100" stroke-dasharray="{pct} 100" transform="rotate(-90 {x+302} {y+96})"/><text x="{x+302}" y="{y+100}" text-anchor="middle" class="small bright" font-size="10">{pct}%</text></g>']
    return shell(width,height,"Animated GitSkins-style public project cards","".join(body),inset=12)

def render_stats(user,repos,calendar):
    width,height=860,300; stars=sum(r.get("stargazerCount",0) for r in repos); languages={}
    for repo in repos:
        lang=(repo.get("primaryLanguage") or {}).get("name")
        if lang: languages[lang]=languages.get(lang,0)+1
    top=max(languages,key=languages.get) if languages else "—"
    rows=[("Name",user.get("name") or user["login"]),("Role","Python developer"),("Stars",str(stars)),("Repos",str(len(repos))),("Followers",str(user.get("followers",{}).get("totalCount",0))),("Top Lang",top),("Activity",f'{calendar["totalContributions"]} public contributions')]
    body=[chrome(width,"thorsenbuilds@github:~$ neofetch",25),'<rect x="34" y="49" width="792" height="221" rx="11" fill="#070a09" stroke="#202725"/><rect x="34" y="49" width="792" height="29" rx="11" fill="#171a1c"/>',
      '<circle cx="51" cy="63" r="5" fill="#ff6969"/><circle cx="69" cy="63" r="5" fill="#ffc857"/><circle cx="87" cy="63" r="5" fill="#54f34b"/><text x="112" y="68" class="small">thorsenbuilds@github</text><path d="M115 75H325" stroke="#b7c0b7"/>',
      '<rect x="60" y="102" width="94" height="92" rx="9" fill="#060d08" stroke="#275d32"/>','<text x="75" y="129" class="bright" font-size="15">+-----+</text><text x="75" y="148" class="bright" font-size="15">| o o |</text><text x="75" y="167" class="bright" font-size="15">| &gt;_ |</text><text x="75" y="186" class="bright" font-size="15">+-----+</text>',
      f'<text x="192" y="107" class="bright" font-size="17" font-weight="700">{esc(user["login"])}@github</text>']
    for i,(label,value) in enumerate(rows):
        y=120+i*17; body.append(f'<g class="rise" style="animation-delay:{i*80}ms"><text x="192" y="{y}" class="bright" font-size="13" font-weight="700">{esc(label)}</text><text x="288" y="{y}" class="value" font-size="13">{esc(value[:48])}</text></g>')
    for i,color in enumerate([GREEN,MINT,LIME,BLUE,"#41bd7d","#65db91"]): body.append(f'<rect x="{192+i*27}" y="244" width="22" height="11" rx="2" fill="{color}" class="pulse" style="animation-delay:{i*130}ms"/>')
    body.append('<text x="808" y="257" text-anchor="end" class="small">PUBLIC DATA ONLY  ·  UPDATED WEEKLY</text>')
    return shell(width,height,"Animated terminal open-source profile stats","".join(body),inset=8)

def render_heatmap(calendar):
    width,height=860,230; weeks=calendar.get("weeks",[])[-53:]; colors=["#111815","#174a23","#258d36","#54d944",LIME]
    body=[f'<text x="52" y="58" class="bright" font-size="19" font-weight="700">Contribution Activity</text>',f'<text x="52" y="82" class="small">{calendar["totalContributions"]:,} contributions in the last year</text>','<text x="650" y="61" class="small">Less</text>']
    for i,color in enumerate(colors): body.append(f'<rect x="{686+i*17}" y="50" width="11" height="11" rx="2" fill="{color}"/>')
    body.append('<text x="780" y="61" class="small">More</text>')
    for wi,week in enumerate(weeks):
        for day in week["contributionDays"]:
            weekday=int(day["weekday"]); level=max(0,min(4,int(day["level"]))); x,y=52+wi*14,101+weekday*14; delay=min(1700,wi*18+weekday*20)
            body.append(f'<rect class="rise" style="animation-delay:{delay}ms" x="{x}" y="{y}" width="9" height="9" rx="1.8" fill="{colors[level]}" opacity=".95"><title>{esc(day["date"])} · public activity level {level}/4</title></rect>')
    body.append('<rect class="scan" x="34" y="95" width="792" height="1.4" fill="url(#sweep)" opacity=".35"/>')
    return shell(width,height,"Animated public GitHub contribution calendar","".join(body),inset=12)

def render_social(login):
    width,height=860,126
    body=['<rect x="34" y="25" width="792" height="76" rx="38" fill="#07100a" fill-opacity=".7" stroke="#244b2b"/>','<rect class="dash" x="35" y="26" width="790" height="74" rx="37" fill="none" stroke="url(#frame)" stroke-width="1.6"/>','<rect x="324" y="40" width="212" height="46" rx="23" fill="#08120b" stroke="url(#frame)" stroke-width="1.5" filter="url(#glow)"/>','<circle cx="350" cy="63" r="13" fill="#e4f0e7"/><g transform="translate(338 51) scale(1)" fill="#17231a"><path d="M12 .5C5.65.5.5 5.65.5 12c0 5.09 3.3 9.4 7.87 10.93.58.1.79-.25.79-.56 0-.28-.01-1.02-.02-2-3.2.7-3.88-1.54-3.88-1.54-.52-1.33-1.28-1.69-1.28-1.69-1.05-.72.08-.7.08-.7 1.16.08 1.78 1.2 1.78 1.2 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.56-.29-5.26-1.28-5.26-5.7 0-1.26.45-2.3 1.2-3.11-.12-.3-.52-1.48.11-3.08 0 0 .98-.31 3.2 1.19.93-.26 1.92-.4 2.9-.4.98 0 1.97.14 2.9.4 2.22-1.5 3.2-1.19 3.2-1.19.64 1.6.24 2.78.12 3.08.75.81 1.2 1.85 1.2 3.11 0 4.43-2.7 5.4-5.27 5.69.41.36.78 1.06.78 2.14 0 1.54-.01 2.78-.01 3.16 0 .31.21.67.8.56A11.5 11.5 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5z"/></g>',f'<text x="373" y="59" class="bright" font-size="12" font-weight="700">GitHub</text><text x="373" y="75" class="value" font-size="13">@{esc(login)}</text>','<circle cx="796" cy="63" r="4" fill="#70ff50" class="pulse"/>']
    return shell(width,height,"Animated GitHub contact pill","".join(body),inset=6)

def main():
    user=github_data(); repos=user["repositories"]["nodes"]; calendar=public_calendar(user["login"]); OUT.mkdir(parents=True,exist_ok=True)
    cards={"system-scan.svg":profile_card(user,repos,calendar),"toolbox.svg":render_toolbox(repos),"projects.svg":render_projects(repos,user["login"]),"stats.svg":render_stats(user,repos,calendar),"heatmap.svg":render_heatmap(calendar),"social.svg":render_social(user["login"])}
    for filename,svg in cards.items(): (OUT/filename).write_text(svg,encoding="utf-8"); print(f"generated {OUT/filename}")
    readme=Path("README.md"); version=os.environ.get("PROFILE_CARDS_CACHE_BUST") or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    if readme.exists():
        content,count=re.subn(r'(\./assets/profile-cards/[a-z0-9-]+\.svg)(?:\?v=[^"\s]*)?',rf'\1?v={version}',readme.read_text(encoding="utf-8"))
        if count!=len(cards): raise RuntimeError(f"Expected {len(cards)} card references, updated {count}")
        readme.write_text(content,encoding="utf-8")
    print(f"Rendered {len(cards)} animated SVGs from {len(repos)} public repositories.")

if __name__ == "__main__": main()
