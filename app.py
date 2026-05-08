import streamlit as st
import pandas as pd
import random
import math
import requests
from io import BytesIO
from typing import List, Optional, Tuple


# ── Config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="羽毛球对战表生成器", page_icon="🏸", layout="wide")


# ── CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.main-title {font-size:42px;font-weight:bold;color:#155E3B;}
.sub-title {font-size:18px;color:#555;}
.group-card {
    background-color:#F3FFF6; padding:18px; border-radius:16px;
    border:1px solid #BFE8C8; margin-bottom:15px;
}

/* ===== LED Scoreboard Theme ===== */
.sb-card {
    background:linear-gradient(180deg,#161b22,#0d1117);
    border:1px solid #30363d;
    border-radius:12px;
    padding:16px 18px 14px;
    margin-bottom:14px;
    box-shadow:0 4px 16px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04);
}
.sb-title {
    font-size:10px; color:#666; text-transform:uppercase;
    letter-spacing:1.5px; margin-bottom:8px;
}
.sb-player { font-size:15px; font-weight:700; text-align:center; color:#ffffff; text-shadow:0 0 4px rgba(255,255,255,0.12); }
.sb-player.win { color:#4ade80; }
.sb-score {
    font-family:'Courier New',monospace; font-size:44px; font-weight:800;
    text-align:center; line-height:1.1; font-variant-numeric:tabular-nums;
    color:#ff6b35; text-shadow:0 0 12px rgba(255,107,53,.25);
}
.sb-score.win { color:#4ade80; text-shadow:0 0 14px rgba(74,222,128,.35); }
.sb-status {
    text-align:center; padding:4px 0 0; font-size:12px; font-weight:600;
    letter-spacing:0.5px;
}
.sb-btn { border-radius:50% !important; width:32px !important; height:32px !important;
          padding:0 !important; line-height:1 !important; font-size:16px !important;
          min-width:unset !important; }

/* Bracket tree */
.bracket-wrap { display:flex; flex-direction:row; overflow-x:auto; padding:12px 0; gap:0; }
.b-round-col { display:flex; flex-direction:column; min-width:170px; flex-shrink:0; }
.b-conn-col { display:flex; flex-direction:column; width:28px; flex-shrink:0; }
.b-match-wrap { display:flex; align-items:center; padding:2px 6px; box-sizing:border-box; }
.b-match-card {
    width:100%; padding:10px 12px; border-radius:10px; border:1px solid #ddd;
    background:white; font-size:13px; box-shadow:0 1px 4px rgba(0,0,0,0.05);
}
.b-match-card.bye { background:#fff8e6; border-color:#f0c040; }
.b-player { font-weight:600; font-size:13px; }
.b-vs { text-align:center; font-size:10px; color:#E67E22; font-weight:700; line-height:1.5; }
.b-conn-item { position:relative; }
.b-line-h { position:absolute; height:2px; background:#bbb; }
.b-line-v { position:absolute; width:2px; background:#bbb; }

@media print {
    .main-title,.sub-title,.stButton,.stDownloadButton,.stRadio,.stNumberInput,
    .stFileUploader,.stTextInput,hr,#生成结果 { display:none !important; }
}
</style>
""", unsafe_allow_html=True)


# ── Constants ────────────────────────────────────────────────────────────
MATCH_CARD_HEIGHT = 64
MATCH_GAP = 12
UNIT_HEIGHT = MATCH_CARD_HEIGHT + MATCH_GAP


# ── Helpers ──────────────────────────────────────────────────────────────

def _get_group_name(index: int) -> str:
    """A, B, ..., Z, AA, AB..."""
    name = ""
    i = index
    while True:
        name = chr(ord("A") + i % 26) + name
        i = i // 26 - 1
        if i < 0:
            break
    return name


def load_names(
    uploaded_file: Optional[BytesIO], excel_url: str, text_input: str
) -> List[str]:
    if text_input.strip():
        return [line.strip() for line in text_input.strip().split("\n") if line.strip()]
    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file, header=None)
    elif excel_url:
        response = requests.get(excel_url, timeout=20)
        response.raise_for_status()
        df = pd.read_excel(BytesIO(response.content), header=None)
    else:
        return []
    names = df.iloc[:, 0].dropna().astype(str).tolist()
    return [name.strip() for name in names if name.strip()]


def create_group_matches(group: List[str]) -> List[Tuple[str, str]]:
    return [(group[i], group[j]) for i in range(len(group)) for j in range(i + 1, len(group))]


def create_round_robin_schedule(players: List[str]) -> List[List[Tuple[str, str]]]:
    """Circle-method schedule: 1 match per player per round."""
    n = len(players)
    if n < 2:
        return []
    working = list(players)
    if n % 2 == 1:
        working.append(None)
        n += 1
    fixed, rotating = working[0], working[1:]
    n_rot = n - 1
    schedule = []
    for rnd in range(n_rot):
        matches = []
        p1, p2 = fixed, rotating[rnd % n_rot]
        if p1 is not None and p2 is not None:
            matches.append((p1, p2))
        for i in range(1, n // 2):
            a = rotating[(rnd + i) % n_rot]
            b = rotating[(rnd + n_rot - i) % n_rot]
            if a is not None and b is not None:
                matches.append((a, b))
        schedule.append(matches)
    return schedule


def distribute_evenly(items: List[str], target_size: int) -> List[List[str]]:
    n = len(items)
    if n <= target_size:
        return [items]
    ng = math.ceil(n / target_size)
    while ng > 1:
        base, rem = n // ng, n % ng
        sizes = [base + 1] * rem + [base] * (ng - rem)
        if min(sizes) >= 2:
            break
        ng -= 1
    sizes = [n // ng + (1 if i < n % ng else 0) for i in range(ng)]
    groups, start = [], 0
    for s in sizes:
        groups.append(items[start:start + s])
        start += s
    return groups


def next_power_of_two(n: int) -> int:
    p = 1
    while p < n: p *= 2
    return p


def get_round_name(size: int) -> str:
    return {2: "决赛", 4: "半决赛", 8: "1/4决赛",
            16: "1/8决赛", 32: "1/16决赛", 64: "1/32决赛"}.get(size, f"{size}强赛")


# ── Stamina ──────────────────────────────────────────────────────────────

def analyze_stamina(groups: List[List[str]], knockout_matches: List[dict]) -> List[dict]:
    ko_rounds = len({m["阶段"] for m in knockout_matches})
    results = []
    for idx, group in enumerate(groups):
        gname = _get_group_name(idx)
        per = len(group) - 1
        total = per + ko_rounds
        if total <= 4: rating, color, icon = "轻松", "#27ae60", "🟢"
        elif total <= 6: rating, color, icon = "适中", "#2980b9", "🔵"
        elif total <= 8: rating, color, icon = "较累", "#e67e22", "🟠"
        else: rating, color, icon = "很累", "#e74c3c", "🔴"
        results.append({"小组": f"{gname}组", "人数": len(group),
                        "小组赛场次/人": per, "淘汰赛轮数": ko_rounds,
                        "冠军总场次": total, "体力评级": rating, "_color": color, "_icon": icon})
    return results


# ── Knockout ─────────────────────────────────────────────────────────────

def create_knockout_matches(groups: List[List[str]], seed: int) -> List[dict]:
    rng = random.Random(seed)
    winners, runners_up = [], []
    for idx, group in enumerate(groups):
        gname = _get_group_name(idx)
        if len(group) >= 1:
            winners.append((f"{gname}组第1", idx))
        if len(group) >= 2:
            runners_up.append((f"{gname}组第2", idx))
    rng.shuffle(winners)
    rng.shuffle(runners_up)

    n = min(len(winners), len(runners_up))
    used, pairs = [False] * n, []
    for w_name, w_gidx in winners[:n]:
        best = None
        for ri, (ru_name, ru_gidx) in enumerate(runners_up[:n]):
            if not used[ri] and ru_gidx != w_gidx:
                best = ri
                break
        if best is None:
            for ri in range(n):
                if not used[ri]:
                    best = ri
                    break
        if best is not None:
            pairs.append((w_name, runners_up[best][0]))
            used[best] = True

    players = [p for pair in pairs for p in pair]
    size = next_power_of_two(len(players))
    while len(players) < size:
        players.append("轮空")

    all_ko, cur, cur_sz = [], players[:], size
    while cur_sz >= 2:
        rn = get_round_name(cur_sz)
        nxt = []
        for i in range(0, len(cur), 2):
            p1, p2 = cur[i], cur[i + 1]
            mn = i // 2 + 1
            wn = f"{rn}第{mn}场胜者"
            all_ko.append({"阶段": rn, "场次": mn, "选手1": p1, "选手2": p2, "晋级": wn})
            nxt.append(wn)
        cur, cur_sz = nxt, cur_sz // 2
    return all_ko


def render_bracket_html(knockout_matches: List[dict]) -> str:
    rounds = {}
    for m in knockout_matches:
        rounds.setdefault(m["阶段"], []).append(m)
    rnames = list(rounds.keys())
    if not rnames:
        return ""
    html = ['<div class="bracket-wrap">']
    for ri, rn in enumerate(rnames):
        item_h = UNIT_HEIGHT * (2 ** ri)
        html.append(f'<div class="b-round-col">')
        for m in rounds[rn]:
            p1, p2 = m["选手1"], m["选手2"]
            bye = "轮空" in p1 or "轮空" in p2
            css = "b-match-card" + (" bye" if bye else "")
            html.append(f'<div class="b-match-wrap" style="height:{item_h}px;">')
            html.append(f'<div class="{css}"><div class="b-player">{p1}</div>'
                        f'<div class="b-vs">VS</div><div class="b-player">{p2}</div></div>')
            html.append("</div>")
        html.append("</div>")
        if ri < len(rnames) - 1:
            pair_h = 2 * UNIT_HEIGHT * (2 ** ri)
            html.append(f'<div class="b-conn-col">')
            for _ in range(len(rounds[rnames[ri + 1]])):
                html.append(f'<div class="b-conn-item" style="height:{pair_h}px;">')
                html.append(f'<div class="b-line-h" style="left:0;top:calc(25% - 1px);width:50%;"></div>')
                html.append(f'<div class="b-line-h" style="left:0;top:calc(75% - 1px);width:50%;"></div>')
                html.append(f'<div class="b-line-v" style="left:calc(50% - 1px);top:25%;height:50%;"></div>')
                html.append(f'<div class="b-line-h" style="left:50%;top:calc(50% - 1px);width:50%;"></div>')
                html.append("</div>")
            html.append("</div>")
    html.append("</div>")
    return "\n".join(html)


# ── Score state management ──────────────────────────────────────────────

def resolve_name(raw: str) -> str:
    wm = st.session_state.get("winner_map", {})
    return wm.get(raw, raw)


def init_ko_scores(knockout_matches: List[dict]) -> None:
    fp = f"{len(knockout_matches)}_{knockout_matches[0]['阶段']}_{knockout_matches[0]['场次']}" if knockout_matches else "empty"
    if st.session_state.get("_needs_ko_init"):
        fp += "_force"
        st.session_state._needs_ko_init = False
    need = "ko_scores" not in st.session_state or st.session_state.get("_ko_hash") != fp
    if need:
        st.session_state.ko_scores = {}
        st.session_state.winner_map = {}
        for m in knockout_matches:
            k = f"{m['阶段']}_{m['场次']}"
            st.session_state.ko_scores[k] = {"p1": 0, "p2": 0, "done": False, "winner": None}
        st.session_state._ko_hash = fp


def init_group_scores(groups: List[List[str]], schedules: dict) -> None:
    """Initialize group match scores; preserve existing if structure matches."""
    fp = f"{len(groups)}_{sum(len(s) for s in schedules.values())}"
    force = st.session_state.get("_needs_ko_init", False)
    need = ("group_scores" not in st.session_state or
            st.session_state.get("_gs_hash") != fp or
            force)
    if need:
        st.session_state.group_scores = {}
        for idx, group in enumerate(groups):
            gname = _get_group_name(idx)
            schedule = schedules[gname]
            for ri, rnd in enumerate(schedule, 1):
                for mi, (a, b) in enumerate(rnd, 1):
                    k = f"{gname}_{ri}_{mi}"
                    st.session_state.group_scores[k] = {
                        "p1": 0, "p2": 0, "done": False, "winner": None,
                        "p1_name": a, "p2_name": b,
                    }
        st.session_state._gs_hash = fp


def calc_group_standings(gname: str, players: List[str]) -> List[dict]:
    """Return ranked list of players in a group."""
    stats = {p: {"wins": 0, "losses": 0, "pf": 0, "pa": 0} for p in players}
    for k, s in st.session_state.group_scores.items():
        if k.startswith(gname) and s["done"]:
            a, b = s["p1_name"], s["p2_name"]
            if a in stats and b in stats:
                winner = s["winner"]
                stats[winner]["wins"] += 1
                loser = b if winner == a else a
                stats[loser]["losses"] += 1
                stats[a]["pf"] += s["p1"]
                stats[a]["pa"] += s["p2"]
                stats[b]["pf"] += s["p2"]
                stats[b]["pa"] += s["p1"]
    ranked = sorted(stats.items(), key=lambda x: (x[1]["wins"], x[1]["pf"] - x[1]["pa"]), reverse=True)
    return [{"rank": i + 1, "name": r[0], **r[1], "diff": r[1]["pf"] - r[1]["pa"]}
            for i, r in enumerate(ranked)]


def is_group_complete(gname: str) -> bool:
    """Check if all matches in a group are done."""
    return all(
        s["done"] for k, s in st.session_state.group_scores.items()
        if k.startswith(gname)
    )


def sync_group_winners(groups: List[List[str]]) -> None:
    """Push group 1st/2nd into winner_map once a group finishes."""
    for idx, group in enumerate(groups):
        gname = _get_group_name(idx)
        key1, key2 = f"{gname}组第1", f"{gname}组第2"
        if key1 in st.session_state.winner_map and key2 in st.session_state.winner_map:
            continue  # already synced
        if is_group_complete(gname) and len(group) >= 2:
            standings = calc_group_standings(gname, group)
            if len(standings) >= 1:
                st.session_state.winner_map[key1] = standings[0]["name"]
            if len(standings) >= 2:
                st.session_state.winner_map[key2] = standings[1]["name"]


# ── Excel export ─────────────────────────────────────────────────────────

def create_excel_file(groups: List[List[str]], group_match_rows: List[dict],
                       knockout_matches: List[dict]) -> BytesIO:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        group_rows = [{"小组": f"{_get_group_name(i)}组", "成员": "、".join(g)}
                       for i, g in enumerate(groups)]
        pd.DataFrame(group_rows).to_excel(writer, sheet_name="小组分配", index=False)
        pdf = pd.DataFrame(group_match_rows)
        if not pdf.empty:
            # Enrich with scores
            rows = []
            for _, r in pdf.iterrows():
                rr = r.to_dict()
                k = f"{rr['小组'][0]}_{rr['轮次']}_{rr['场次']}"
                if k in st.session_state.get("group_scores", {}):
                    s = st.session_state.group_scores[k]
                    rr["比分"] = f"{s['p1']}:{s['p2']}"
                    rr["胜者"] = s["winner"] or ""
                rows.append(rr)
            pd.DataFrame(rows).to_excel(writer, sheet_name="小组赛对战表", index=False)
        else:
            pd.DataFrame().to_excel(writer, sheet_name="小组赛对战表", index=False)

        ko_rows = []
        for m in knockout_matches:
            r = dict(m)
            r["选手1"] = resolve_name(m["选手1"])
            r["选手2"] = resolve_name(m["选手2"])
            r["晋级"] = resolve_name(m["晋级"])
            k = f"{m['阶段']}_{m['场次']}"
            if k in st.session_state.get("ko_scores", {}):
                s = st.session_state.ko_scores[k]
                r["比分"] = f"{s['p1']}:{s['p2']}"
                r["胜者"] = s["winner"] or ""
            ko_rows.append(r)
        pd.DataFrame(ko_rows).to_excel(writer, sheet_name="淘汰赛对战表", index=False)
    output.seek(0)
    return output


# =====================================================================
#  UI
# =====================================================================

st.markdown('<div class="main-title">羽毛球男单随机对战表生成器</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">上传名单，一键生成小组赛 + 淘汰赛完整对战表 · 支持实时记分</div>', unsafe_allow_html=True)
st.write("")

# ── Sidebar ──
with st.sidebar:
    st.markdown("### 参数设置")
    source_type = st.radio("名单来源", ["上传 Excel", "Excel 下载链接", "直接输入姓名"])
    uploaded_file = None
    excel_url = ""
    text_names = ""
    if source_type == "上传 Excel":
        uploaded_file = st.file_uploader("上传 Excel（第一列为姓名）", type=["xlsx", "xls"])
    elif source_type == "Excel 下载链接":
        excel_url = st.text_input("Excel 下载链接")
    else:
        text_names = st.text_area("每行一个姓名", height=200,
                                  placeholder="张三\n李四\n王五\n赵六")
    group_size = st.number_input("目标每组人数", min_value=2, max_value=10, value=4,
                                 help="系统会根据总人数尽量平均分配")
    user_seed = st.number_input("随机种子（0=完全随机）", min_value=0, max_value=999999,
                                value=0, help="设数字种子可复现")
    generate = st.button("生成完整对战表", type="primary", use_container_width=True)

# ── Generation ──
if "_loaded_names" not in st.session_state:
    st.session_state._loaded_names = None

if generate:
    with st.spinner("正在生成对战表…"):
        try:
            raw = load_names(uploaded_file, excel_url, text_names)
            if len(raw) < 2:
                st.error("至少需要 2 个姓名")
                st.stop()
            deduped = list(dict.fromkeys(raw))
            if len(deduped) < len(raw):
                st.warning(f"发现 {len(raw) - len(deduped)} 个重复姓名，已自动去重")
            st.session_state._loaded_names = deduped
            st.session_state._loaded_group_size = group_size
            st.session_state._run_key = random.randint(0, 999999)
            st.session_state._generated = True
            st.session_state._needs_ko_init = True
        except Exception as e:
            st.error(f"生成失败：{e}")
            st.stop()

if st.session_state.get("_do_reshuffle"):
    st.session_state._run_key = random.randint(0, 999999)
    st.session_state._do_reshuffle = False
    st.session_state._needs_ko_init = True

# ── Build results ──
if st.session_state.get("_generated") and st.session_state._loaded_names:
    names = st.session_state._loaded_names
    group_size = st.session_state._loaded_group_size
    effective_seed = user_seed if user_seed > 0 else st.session_state._run_key

    rng = random.Random(effective_seed)
    shuffled = list(names)
    rng.shuffle(shuffled)

    groups = distribute_evenly(shuffled, group_size)

    if len(groups) > 1:
        sizes = [len(g) for g in groups]
        st.info(f"共 {len(groups)} 组：{', '.join(str(s) for s in sizes)} 人/组")

    # Group schedules
    group_match_rows = []
    group_schedules: dict = {}
    for idx, group in enumerate(groups):
        gname = _get_group_name(idx)
        schedule = create_round_robin_schedule(group)
        group_schedules[gname] = schedule
        for ri, rnd in enumerate(schedule, 1):
            for mi, (a, b) in enumerate(rnd, 1):
                group_match_rows.append({
                    "小组": f"{gname}组", "轮次": ri, "场次": mi,
                    "选手1": a, "选手2": b,
                })

    # Init scores
    init_group_scores(groups, group_schedules)

    # Knockout
    knockout_matches = create_knockout_matches(groups, effective_seed)
    init_ko_scores(knockout_matches)

    # Sync group winners → knockout
    sync_group_winners(groups)

    # ── Display ──
    st.subheader(f"共 {len(names)} 名选手，{len(groups)} 个小组")

    # ── Group cards ──
    st.subheader("分组结果")
    cols = st.columns(3)
    for idx, group in enumerate(groups):
        gname = _get_group_name(idx)
        with cols[idx % 3]:
            st.markdown(
                f'<div class="group-card"><h3>{gname}组（{len(group)}人）</h3>'
                f'<p>{"、".join(group)}</p></div>',
                unsafe_allow_html=True,
            )

    # ── Stamina ──
    st.subheader("体力分析")
    sd = analyze_stamina(groups, knockout_matches)
    sc = st.columns(len(sd))
    for i, s in enumerate(sd):
        with sc[i]:
            st.markdown(
                f"<div style='text-align:center;padding:12px;border-radius:12px;"
                f"background:{s['_color']}15;border:1px solid {s['_color']}40;'>"
                f"<div style='font-size:13px;color:#666;'>{s['小组']}</div>"
                f"<div style='font-size:28px;font-weight:bold;color:{s['_color']};'>{s['_icon']} {s['体力评级']}</div>"
                f"<div style='font-size:13px;color:#555;margin-top:4px;'>"
                f"{s['人数']}人 · 小组{s['小组赛场次/人']}场/人 · 淘汰赛{s['淘汰赛轮数']}轮"
                f"<br>冠军最多 <strong>{s['冠军总场次']}场</strong></div></div>",
                unsafe_allow_html=True,
            )

    # =====================================================================
    #  GROUP STAGE SCOREBOARD
    # =====================================================================
    st.subheader("小组赛计分板")
    st.caption("每轮每位选手打一场，记录比分后自动计算排名，小组前两名晋级淘汰赛")

    for idx, group in enumerate(groups):
        gname = _get_group_name(idx)
        schedule = group_schedules[gname]
        completed = is_group_complete(gname)
        standings = calc_group_standings(gname, group) if completed else []

        with st.expander(f"{gname}组（{'✅ 已完赛' if completed else '⚡ 进行中'}）", expanded=True):
            # Round-robin matches
            for ri, rnd in enumerate(schedule, 1):
                st.markdown(f"**第{ri}轮**")
                for mi, (a, b) in enumerate(rnd, 1):
                    k = f"{gname}_{ri}_{mi}"
                    s = st.session_state.group_scores[k]

                    # Card
                    st.markdown(f'<div class="sb-card">', unsafe_allow_html=True)
                    st.markdown(f'<div class="sb-title">第{mi}场</div>', unsafe_allow_html=True)

                    c1, c2 = st.columns([1, 1])

                    # Player 1
                    with c1:
                        w1 = s["done"] and s["winner"] == a
                        st.markdown(f'<div class="sb-player {"win" if w1 else ""}">{a}</div>',
                                    unsafe_allow_html=True)
                        sub = st.columns([1, 2, 1])
                        with sub[0]:
                            bm1 = st.button("−", key=f"gm_{k}_1")
                        with sub[1]:
                            st.markdown(f'<div class="sb-score {"win" if w1 else ""}">{s["p1"]}</div>',
                                        unsafe_allow_html=True)
                        with sub[2]:
                            bp1 = st.button("+", key=f"gp_{k}_1")

                    # Player 2
                    with c2:
                        w2 = s["done"] and s["winner"] == b
                        st.markdown(f'<div class="sb-player {"win" if w2 else ""}">{b}</div>',
                                    unsafe_allow_html=True)
                        sub = st.columns([1, 2, 1])
                        with sub[0]:
                            bm2 = st.button("−", key=f"gm_{k}_2")
                        with sub[1]:
                            st.markdown(f'<div class="sb-score {"win" if w2 else ""}">{s["p2"]}</div>',
                                        unsafe_allow_html=True)
                        with sub[2]:
                            bp2 = st.button("+", key=f"gp_{k}_2")

                    # Process clicks
                    if bp1: s["p1"] = min(99, s["p1"] + 1)
                    if bm1: s["p1"] = max(0, s["p1"] - 1)
                    if bp2: s["p2"] = min(99, s["p2"] + 1)
                    if bm2: s["p2"] = max(0, s["p2"] - 1)

                    # Win check
                    if not s["done"] and (s["p1"] >= 21 or s["p2"] >= 21):
                        if s["p1"] >= 21 and s["p1"] - s["p2"] >= 2:
                            s["done"] = True; s["winner"] = a
                        elif s["p2"] >= 21 and s["p2"] - s["p1"] >= 2:
                            s["done"] = True; s["winner"] = b

                    # Status
                    if s["done"]:
                        st.markdown(f'<div class="sb-status" style="color:#4ade80;">'
                                    f'🏆 {s["winner"]} 胜</div>', unsafe_allow_html=True)
                    else:
                        diff = s["p1"] - s["p2"]
                        txt = f"{a} 领先 {diff} 分" if diff > 0 else (f"{b} 领先 {-diff} 分" if diff < 0 else "平分")
                        st.markdown(f'<div class="sb-status" style="color:#90CAF9;">⚡ {txt}</div>',
                                    unsafe_allow_html=True)

                    st.markdown("</div>", unsafe_allow_html=True)

            # Standings
            if completed:
                st.markdown("#### 排名")
                standings = calc_group_standings(gname, group)
                medals = ["🥇", "🥈", "🥉"]
                rank_html = '<table style="width:100%;border-collapse:collapse;">'
                rank_html += "<tr style='color:#888;font-size:12px;'>"
                rank_html += "<th style='padding:4px 8px;text-align:left;'>#</th>"
                rank_html += "<th style='padding:4px 8px;text-align:left;'>选手</th>"
                rank_html += "<th style='padding:4px 8px;text-align:center;'>胜</th>"
                rank_html += "<th style='padding:4px 8px;text-align:center;'>负</th>"
                rank_html += "<th style='padding:4px 8px;text-align:center;'>得分</th>"
                rank_html += "<th style='padding:4px 8px;text-align:center;'>失分</th>"
                rank_html += "<th style='padding:4px 8px;text-align:center;'>净胜</th></tr>"
                for ps in standings:
                    m = medals[ps["rank"] - 1] if ps["rank"] <= 3 else ""
                    highlight = "color:#4ade80;font-weight:700;" if ps["rank"] <= 2 else ""
                    rank_html += (
                        f"<tr style='{highlight}border-top:1px solid #222;'>"
                        f"<td style='padding:6px 8px;'>{m} {ps['rank']}</td>"
                        f"<td style='padding:6px 8px;'>{ps['name']}</td>"
                        f"<td style='padding:6px 8px;text-align:center;'>{ps['wins']}</td>"
                        f"<td style='padding:6px 8px;text-align:center;'>{ps['losses']}</td>"
                        f"<td style='padding:6px 8px;text-align:center;'>{ps['pf']}</td>"
                        f"<td style='padding:6px 8px;text-align:center;'>{ps['pa']}</td>"
                        f"<td style='padding:6px 8px;text-align:center;'>{ps['diff']:+d}</td></tr>"
                    )
                rank_html += "</table>"
                st.markdown(rank_html, unsafe_allow_html=True)

                # Show qualifiers
                if len(standings) >= 1:
                    st.markdown(
                        f"<div style='padding:8px 12px;border-radius:8px;"
                        f"background:#1b5e20;color:#81C784;margin-top:8px;'>"
                        f"🏆 晋级淘汰赛：<strong>{standings[0]['name']}</strong>"
                        f"{'、<strong>' + standings[1]['name'] + '</strong>' if len(standings) >= 2 else ''}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
            else:
                # Show partial standings
                partial = calc_group_standings(gname, group)
                if any(p["wins"] > 0 or p["losses"] > 0 for p in partial):
                    st.markdown("#### 当前排名")
                    parts = " | ".join(
                        f"{p['rank']}. {p['name']} ({p['wins']}胜{p['losses']}败)"
                        for p in partial
                    )
                    st.markdown(f"<div style='color:#888;font-size:13px;'>{parts}</div>",
                                unsafe_allow_html=True)

    # Re-sync winners (in case group matches changed)
    sync_group_winners(groups)

    # =====================================================================
    #  KNOCKOUT STAGE SCOREBOARD
    # =====================================================================
    st.subheader("淘汰赛计分板")
    st.caption("先到21分且领先2分者获胜，自动晋级下一轮")

    ko_rounds: dict = {}
    for m in knockout_matches:
        ko_rounds.setdefault(m["阶段"], []).append(m)

    round_order = ["1/16决赛", "1/8决赛", "1/4决赛", "半决赛", "决赛"]
    for rn in round_order:
        if rn not in ko_rounds:
            continue
        st.markdown(f"### 🏸 {rn}")
        for m in ko_rounds[rn]:
            key = f"{m['阶段']}_{m['场次']}"
            score = st.session_state.ko_scores[key]
            p1 = resolve_name(m["选手1"])
            p2 = resolve_name(m["选手2"])

            st.markdown(f'<div class="sb-card">', unsafe_allow_html=True)
            st.markdown(f'<div class="sb-title">第{m["场次"]}场</div>', unsafe_allow_html=True)

            c1, c2 = st.columns([1, 1])

            with c1:
                w1 = score["done"] and score["winner"] == p1
                st.markdown(f'<div class="sb-player {"win" if w1 else ""}">{p1}</div>',
                            unsafe_allow_html=True)
                sub = st.columns([1, 2, 1])
                with sub[0]:
                    bm1 = st.button("−", key=f"km_{key}_1")
                with sub[1]:
                    st.markdown(f'<div class="sb-score {"win" if w1 else ""}">{score["p1"]}</div>',
                                unsafe_allow_html=True)
                with sub[2]:
                    bp1 = st.button("+", key=f"kp_{key}_1")

            with c2:
                w2 = score["done"] and score["winner"] == p2
                st.markdown(f'<div class="sb-player {"win" if w2 else ""}">{p2}</div>',
                            unsafe_allow_html=True)
                sub = st.columns([1, 2, 1])
                with sub[0]:
                    bm2 = st.button("−", key=f"km_{key}_2")
                with sub[1]:
                    st.markdown(f'<div class="sb-score {"win" if w2 else ""}">{score["p2"]}</div>',
                                unsafe_allow_html=True)
                with sub[2]:
                    bp2 = st.button("+", key=f"kp_{key}_2")

            # Process clicks
            if bp1: score["p1"] = min(99, score["p1"] + 1)
            if bm1: score["p1"] = max(0, score["p1"] - 1)
            if bp2: score["p2"] = min(99, score["p2"] + 1)
            if bm2: score["p2"] = max(0, score["p2"] - 1)

            # Win check
            if not score["done"]:
                if score["p1"] >= 21 and score["p1"] - score["p2"] >= 2:
                    score["done"] = True; score["winner"] = p1
                    st.session_state.winner_map[m["晋级"]] = p1
                elif score["p2"] >= 21 and score["p2"] - score["p1"] >= 2:
                    score["done"] = True; score["winner"] = p2
                    st.session_state.winner_map[m["晋级"]] = p2

            # Status
            if score["done"]:
                st.markdown(f'<div class="sb-status" style="color:#4ade80;">'
                            f'🏆 {score["winner"]} 晋级</div>', unsafe_allow_html=True)
            else:
                diff = score["p1"] - score["p2"]
                if diff > 0:
                    txt = f"{p1} 领先 {diff} 分"
                elif diff < 0:
                    txt = f"{p2} 领先 {-diff} 分"
                else:
                    txt = "平分"
                st.markdown(f'<div class="sb-status" style="color:#90CAF9;">⚡ {txt}</div>',
                            unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

    # ── Bracket overview ──
    with st.expander("查看晋级路线图"):
        bh = render_bracket_html(knockout_matches)
        for old, new in st.session_state.get("winner_map", {}).items():
            bh = bh.replace(old, f"<strong>{new}</strong>")
        st.markdown(bh, unsafe_allow_html=True)

    # ── Tables ──
    with st.expander("查看所有比赛表格"):
        tab_grp, tab_ko = st.tabs(["小组赛", "淘汰赛"])
        with tab_grp:
            rows = []
            for _, r in pd.DataFrame(group_match_rows).iterrows():
                rr = dict(r)
                k = f"{rr['小组'][0]}_{rr['轮次']}_{rr['场次']}"
                if k in st.session_state.get("group_scores", {}):
                    s = st.session_state.group_scores[k]
                    rr["比分"] = f"{s['p1']}:{s['p2']}"
                    rr["胜者"] = s["winner"] or ""
                rows.append(rr)
            st.dataframe(rows, use_container_width=True, height=min(400, 35 * len(rows) + 38) if rows else 200)

        with tab_ko:
            rows = []
            for m in knockout_matches:
                r = dict(m)
                r["选手1"] = resolve_name(m["选手1"])
                r["选手2"] = resolve_name(m["选手2"])
                r["晋级"] = resolve_name(m["晋级"])
                k = f"{m['阶段']}_{m['场次']}"
                if k in st.session_state.ko_scores:
                    s = st.session_state.ko_scores[k]
                    r["比分"] = f"{s['p1']}:{s['p2']}"
                    r["状态"] = ("✅ " + s["winner"]) if s["done"] else "⚡进行中"
                rows.append(r)
            st.dataframe(rows, use_container_width=True, height=min(400, 35 * len(rows) + 38) if rows else 200)

    # ── Export & reshuffle ──
    col1, col2 = st.columns([1, 1])
    with col1:
        excel_file = create_excel_file(groups, group_match_rows, knockout_matches)
        st.download_button(
            label="下载 Excel 对战表",
            data=excel_file,
            file_name="羽毛球男单随机对战表.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with col2:
        if st.button("重新洗牌（同名单）", use_container_width=True):
            st.session_state._do_reshuffle = True
            st.rerun()
