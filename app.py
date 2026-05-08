import streamlit as st
import pandas as pd
import random
import math
import requests
from io import BytesIO
from typing import List, Optional, Tuple


# ── Config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="羽毛球对战表生成器", page_icon="🏸", layout="wide")

# ── Constants ────────────────────────────────────────────────────────────
MATCH_CARD_HEIGHT = 64
MATCH_GAP = 12
UNIT_HEIGHT = MATCH_CARD_HEIGHT + MATCH_GAP


# ── CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.main-title {font-size:42px;font-weight:bold;color:#155E3B;}
.sub-title {font-size:18px;color:#555;}
.group-card {
    background-color:#F3FFF6; padding:18px; border-radius:16px;
    border:1px solid #BFE8C8; margin-bottom:15px;
}
.match-card {
    background-color:white; padding:14px; border-radius:14px;
    border:1px solid #DDD; margin-bottom:10px;
}
.vs {font-weight:bold;color:#E67E22;}

/* Bracket tree */
.bracket-wrap { display:flex; flex-direction:row; overflow-x:auto; padding:12px 0; gap:0; }
.b-round-col { display:flex; flex-direction:column; min-width:170px; flex-shrink:0; }
.b-conn-col { display:flex; flex-direction:column; width:28px; flex-shrink:0; }
.b-match-wrap {
    display:flex; align-items:center; padding:2px 6px; box-sizing:border-box;
}
.b-match-card {
    width:100%; padding:10px 12px; border-radius:10px; border:1px solid #ddd;
    background:white; font-size:13px; box-shadow:0 1px 4px rgba(0,0,0,0.05);
    transition:box-shadow .15s;
}
.b-match-card:hover { box-shadow:0 2px 8px rgba(0,0,0,0.1); }
.b-match-card.bye {
    background:#fff8e6; border-color:#f0c040;
}
.b-player { font-weight:600; font-size:13px; }
.b-vs { text-align:center; font-size:10px; color:#E67E22; font-weight:700; line-height:1.5; }
.b-conn-item { position:relative; }
.b-line-h { position:absolute; height:2px; background:#bbb; }
.b-line-v { position:absolute; width:2px; background:#bbb; }

@media print {
    .main-title, .sub-title, .stButton, .stDownloadButton, .stRadio, .stNumberInput,
    .stFileUploader, .stTextInput, hr, #生成结果 { display:none !important; }
}

/* Scoreboard */
.sc-title { font-size:12px; color:#999; letter-spacing:1px; margin-bottom:6px; }
.sc-name { font-size:16px; font-weight:700; text-align:center; }
.sc-name.win { color:#4CAF50 !important; }
.sc-name.lose { color:#666 !important; }
.sc-score { font-size:42px; font-weight:800; text-align:center; line-height:1.2; font-variant-numeric:tabular-nums; }
.sc-vs { text-align:center; color:#555; font-weight:600; font-size:14px; }
.sc-winner-badge {
    text-align:center; padding:6px; border-radius:8px; font-weight:700; font-size:14px;
}
.status-live { color:#f39c12; }
.status-done { color:#4CAF50; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ──────────────────────────────────────────────────────────────

def _get_group_name(index: int) -> str:
    """Convert 0-based index to Excel-style column letters: A, B, ..., Z, AA, AB..."""
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
    """Load player names from any available source."""
    if text_input.strip():
        names = [line.strip() for line in text_input.strip().split("\n") if line.strip()]
        return names

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
    """Round-robin within a group (all combinations)."""
    return [(group[i], group[j]) for i in range(len(group)) for j in range(i + 1, len(group))]


def create_round_robin_schedule(players: List[str]) -> List[List[Tuple[str, str]]]:
    """Fair round-robin schedule using the circle method.

    Each player plays at most once per round, ensuring rest between matches.
    Returns list of rounds, each round is a list of (p1, p2) matches.
    """
    n = len(players)
    if n < 2:
        return []

    working = list(players)
    if n % 2 == 1:
        working.append(None)  # None = bye/rest round for the paired player
        n += 1

    fixed = working[0]
    rotating = working[1:]
    n_rotating = n - 1

    schedule = []
    for rnd in range(n_rotating):
        matches = []
        # Fixed vs rotating[rnd]
        p1, p2 = fixed, rotating[rnd % n_rotating]
        if p1 is not None and p2 is not None:
            matches.append((p1, p2))
        # Remaining pairs
        for i in range(1, n // 2):
            a = rotating[(rnd + i) % n_rotating]
            b = rotating[(rnd + n_rotating - i) % n_rotating]
            if a is not None and b is not None:
                matches.append((a, b))
        schedule.append(matches)

    return schedule


def analyze_stamina(
    groups: List[List[str]], knockout_matches: List[dict]
) -> List[dict]:
    """Assess physical demand: group matches + possible knockout rounds."""
    ko_rounds = len({m["阶段"] for m in knockout_matches})
    results = []
    for idx, group in enumerate(groups):
        gname = _get_group_name(idx)
        per_player = len(group) - 1
        total = per_player + ko_rounds

        if total <= 4:
            rating, color, icon = "轻松", "#27ae60", "🟢"
        elif total <= 6:
            rating, color, icon = "适中", "#2980b9", "🔵"
        elif total <= 8:
            rating, color, icon = "较累", "#e67e22", "🟠"
        else:
            rating, color, icon = "很累", "#e74c3c", "🔴"

        results.append({
            "小组": f"{gname}组", "人数": len(group),
            "小组赛场次/人": per_player,
            "淘汰赛轮数": ko_rounds,
            "冠军总场次": total,
            "体力评级": rating,
            "_color": color,
            "_icon": icon,
        })
    return results


def next_power_of_two(n: int) -> int:
    power = 1
    while power < n:
        power *= 2
    return power


def get_round_name(size: int) -> str:
    return {
        2: "决赛", 4: "半决赛", 8: "1/4决赛",
        16: "1/8决赛", 32: "1/16决赛", 64: "1/32决赛",
    }.get(size, f"{size}强赛")


def distribute_evenly(items: List[str], target_size: int) -> List[List[str]]:
    """Distribute items into groups as evenly as possible.

    Each group gets at most `target_size` items, and no group has fewer than 2.
    """
    n = len(items)
    if n <= target_size:
        return [items]

    num_groups = math.ceil(n / target_size)

    # Reduce group count if the smallest group would be 1 person
    while num_groups > 1:
        base = n // num_groups
        rem = n % num_groups
        sizes = [base + 1] * rem + [base] * (num_groups - rem)
        if min(sizes) >= 2:
            break
        num_groups -= 1

    # Build evenly-sized groups
    sizes = [n // num_groups + (1 if i < n % num_groups else 0) for i in range(num_groups)]
    groups: List[List[str]] = []
    start = 0
    for s in sizes:
        groups.append(items[start:start + s])
        start += s
    return groups


def create_knockout_matches(groups: List[List[str]], seed: int) -> List[dict]:
    """
    Knockout bracket with proper separation:
      - Group winners (第1) vs runners-up (第2) from different groups
      - Seeded random for reproducibility
    """
    rng = random.Random(seed)

    # Collect winners and runners-up with their group index
    winners: List[Tuple[str, int]] = []
    runners_up: List[Tuple[str, int]] = []

    for idx, group in enumerate(groups):
        gname = _get_group_name(idx)
        if len(group) >= 1:
            winners.append((f"{gname}组第1", idx))
        if len(group) >= 2:
            runners_up.append((f"{gname}组第2", idx))

    # Shuffle each tier independently
    rng.shuffle(winners)
    rng.shuffle(runners_up)

    # Pair winners vs runners-up, avoid same-group in first round
    n = min(len(winners), len(runners_up))
    used = [False] * n
    pairs: List[Tuple[str, str]] = []

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

    # Standard bracket: pair adjacent (W1 vs RU1, W2 vs RU2, ...)
    players: List[str] = []
    for w, ru in pairs:
        players.append(w)
        players.append(ru)

    size = next_power_of_two(len(players))

    # Pad with byes
    while len(players) < size:
        players.append("轮空")

    all_knockout_matches: List[dict] = []
    current_players = players[:]
    current_size = size

    while current_size >= 2:
        round_name = get_round_name(current_size)
        next_round: List[str] = []

        for i in range(0, len(current_players), 2):
            p1 = current_players[i]
            p2 = current_players[i + 1]
            match_no = i // 2 + 1
            winner_name = f"{round_name}第{match_no}场胜者"

            all_knockout_matches.append({
                "阶段": round_name,
                "场次": match_no,
                "选手1": p1,
                "选手2": p2,
                "晋级": winner_name,
            })
            next_round.append(winner_name)

        current_players = next_round
        current_size //= 2

    return all_knockout_matches


def resolve_name(raw: str) -> str:
    """Resolve a template name to actual player via winner_map."""
    wm = st.session_state.get("winner_map", {})
    return wm.get(raw, raw)


def init_ko_scores(knockout_matches: List[dict]) -> None:
    """Initialize or reinitialize knockout score state."""
    # Build a fingerprint: structure + effective_seed so reshuffles reset scores
    fp = f"{len(knockout_matches)}_{knockout_matches[0]['阶段']}_{knockout_matches[0]['场次']}" if knockout_matches else "empty"
    if st.session_state.get("_needs_ko_init"):
        fp += "_force"  # force reinit
        st.session_state._needs_ko_init = False

    need_init = ("ko_scores" not in st.session_state or
                 st.session_state.get("_ko_data_hash") != fp)

    if need_init:
        st.session_state.ko_scores = {}
        st.session_state.winner_map = {}
        for m in knockout_matches:
            key = f"{m['阶段']}_{m['场次']}"
            st.session_state.ko_scores[key] = {
                "p1": 0, "p2": 0,
                "done": False, "winner": None,
            }
        st.session_state._ko_data_hash = fp


def render_bracket_html(knockout_matches: List[dict]) -> str:
    """Render a visual bracket tree with connector lines."""
    rounds: dict = {}
    for m in knockout_matches:
        rounds.setdefault(m["阶段"], []).append(m)

    round_names = list(rounds.keys())
    if not round_names:
        return ""

    html = ['<div class="bracket-wrap">']

    for ri, rname in enumerate(round_names):
        matches = rounds[rname]
        item_h = UNIT_HEIGHT * (2 ** ri)

        # ── Round column ──
        html.append(f'<div class="b-round-col">')
        for m in matches:
            p1, p2 = m["选手1"], m["选手2"]
            is_bye = "轮空" in p1 or "轮空" in p2
            css = "b-match-card" + (" bye" if is_bye else "")
            html.append(f'<div class="b-match-wrap" style="height:{item_h}px;">')
            html.append(f'<div class="{css}"><div class="b-player">{p1}</div>'
                        f'<div class="b-vs">VS</div>'
                        f'<div class="b-player">{p2}</div></div>')
            html.append("</div>")
        html.append("</div>")

        # ── Connector column (between rounds) ──
        if ri < len(round_names) - 1:
            conn_h = UNIT_HEIGHT * (2 ** ri)  # same as current round item height
            pair_h = 2 * conn_h
            html.append(f'<div class="b-conn-col">')
            for _ in range(len(rounds[round_names[ri + 1]])):
                html.append(f'<div class="b-conn-item" style="height:{pair_h}px;">')
                # top arm (25% position → connects to match 2i)
                html.append(f'<div class="b-line-h" style="left:0;top:calc(25% - 1px);width:50%;"></div>')
                # bottom arm (75% position → connects to match 2i+1)
                html.append(f'<div class="b-line-h" style="left:0;top:calc(75% - 1px);width:50%;"></div>')
                # vertical connection between top and bottom
                html.append(f'<div class="b-line-v" style="left:calc(50% - 1px);top:25%;height:50%;"></div>')
                # horizontal line to next round
                html.append(f'<div class="b-line-h" style="left:50%;top:calc(50% - 1px);width:50%;"></div>')
                html.append("</div>")
            html.append("</div>")

    html.append("</div>")
    return "\n".join(html)


# ── Excel export ─────────────────────────────────────────────────────────

def create_excel_file(
    groups: List[List[str]],
    group_matches: List[dict],
    knockout_matches: List[dict],
) -> BytesIO:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        group_rows = [
            {"小组": f"{_get_group_name(i)}组", "成员": "、".join(g)}
            for i, g in enumerate(groups)
        ]
        pd.DataFrame(group_rows).to_excel(writer, sheet_name="小组分配", index=False)
        pd.DataFrame(group_matches).to_excel(writer, sheet_name="小组赛对战表", index=False)
        pd.DataFrame(knockout_matches).to_excel(writer, sheet_name="淘汰赛对战表", index=False)
    output.seek(0)
    return output


# ── UI ───────────────────────────────────────────────────────────────────

st.markdown('<div class="main-title">羽毛球男单随机对战表生成器</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">上传名单，一键生成小组赛 + 淘汰赛完整对战表</div>', unsafe_allow_html=True)
st.write("")

# ── Sidebar inputs ──
with st.sidebar:
    st.markdown("### 参数设置")

    source_type = st.radio("名单来源", ["上传 Excel", "Excel 下载链接", "直接输入姓名"])

    uploaded_file = None
    excel_url = ""
    text_names = ""

    if source_type == "上传 Excel":
        uploaded_file = st.file_uploader("上传 Excel 文件（第一列为姓名）", type=["xlsx", "xls"])
    elif source_type == "Excel 下载链接":
        excel_url = st.text_input("Excel 下载链接")
    else:
        text_names = st.text_area("输入姓名（每行一个）", height=200,
                                  placeholder="张三\n李四\n王五\n赵六")

    group_size = st.number_input("目标每组人数", min_value=2, max_value=10, value=4,
                                 help="系统会根据总人数尽量平均分配")
    user_seed = st.number_input("随机种子（0=完全随机）", min_value=0, max_value=999999,
                                value=0, help="设一个数字种子可复现相同结果")

    generate = st.button("生成完整对战表", type="primary", use_container_width=True)

# ── Generation ──
if "_loaded_names" not in st.session_state:
    st.session_state._loaded_names = None

if generate:
    with st.spinner("正在生成对战表..."):
        try:
            raw_names = load_names(uploaded_file, excel_url, text_names)
            if len(raw_names) < 2:
                st.error("至少需要 2 个姓名")
                st.stop()

            # Deduplicate while preserving order
            deduped = list(dict.fromkeys(raw_names))
            if len(deduped) < len(raw_names):
                st.warning(f"发现 {len(raw_names) - len(deduped)} 个重复姓名，已自动去重")

            st.session_state._loaded_names = deduped
            st.session_state._loaded_group_size = group_size
            # For true random (seed=0), use a run-specific random key
            st.session_state._run_key = random.randint(0, 999999)
            st.session_state._generated = True
            st.session_state._needs_ko_init = True

        except Exception as e:
            st.error(f"生成失败：{e}")
            st.stop()

# ── Re-shuffle trigger ──
if st.session_state.get("_do_reshuffle"):
    st.session_state._run_key = random.randint(0, 999999)
    st.session_state._do_reshuffle = False

# ── Build results from loaded data ──
if st.session_state.get("_generated") and st.session_state._loaded_names:
    names = st.session_state._loaded_names
    group_size = st.session_state._loaded_group_size
    effective_seed = user_seed if user_seed > 0 else st.session_state._run_key

    rng = random.Random(effective_seed)
    shuffled = list(names)  # copy, don't mutate session state
    rng.shuffle(shuffled)

    # Split groups (as evenly as possible)
    groups = distribute_evenly(shuffled, group_size)

    if len(groups) > 1:
        sizes = [len(g) for g in groups]
        st.info(f"共 {len(groups)} 组：各组人数 {', '.join(str(s) for s in sizes)}")

    # Group matches (round-robin schedule, 1 match per player per round)
    group_match_rows = []
    group_schedules: dict = {}
    for idx, group in enumerate(groups):
        gname = _get_group_name(idx)
        schedule = create_round_robin_schedule(group)
        group_schedules[gname] = schedule
        for rnd_idx, round_matches in enumerate(schedule, 1):
            for mi, (a, b) in enumerate(round_matches, 1):
                group_match_rows.append({
                    "小组": f"{gname}组", "轮次": rnd_idx, "场次": mi,
                    "选手1": a, "选手2": b,
                })

    # Knockout matches
    knockout_matches = create_knockout_matches(groups, effective_seed)
    init_ko_scores(knockout_matches)

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

    # ── Stamina analysis ──
    st.subheader("体力分析")
    stamina_data = analyze_stamina(groups, knockout_matches)
    scols = st.columns(len(stamina_data))
    for i, s in enumerate(stamina_data):
        with scols[i]:
            st.markdown(
                f"<div style='text-align:center;padding:12px;border-radius:12px;"
                f"background:{s['_color']}15;border:1px solid {s['_color']}40;'>"
                f"<div style='font-size:13px;color:#666;'>{s['小组']}</div>"
                f"<div style='font-size:28px;font-weight:bold;color:{s['_color']};'>{s['_icon']} {s['体力评级']}</div>"
                f"<div style='font-size:13px;color:#555;margin-top:4px;'>"
                f"{s['人数']}人 · 小组{s['小组赛场次/人']}场/人 · 淘汰赛{s['淘汰赛轮数']}轮"
                f"<br>冠军最多 <strong>{s['冠军总场次']}场</strong></div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # ── Group match schedule (round-by-round) ──
    st.subheader("小组赛赛程（轮次制）")
    st.caption("每轮每位选手只打一场，确保轮间有休息")
    for idx, group in enumerate(groups):
        gname = _get_group_name(idx)
        schedule = group_schedules[gname]
        with st.expander(f"{gname}组 — 共{len(schedule)}轮"):
            for rnd_idx, round_matches in enumerate(schedule, 1):
                matches_str = "　｜　".join(f"{a} vs {b}" for a, b in round_matches)
                st.markdown(f"**第{rnd_idx}轮**　{matches_str}")

    # ── Group match table ──
    with st.expander("查看完整小组赛表格"):
        height = min(400, 35 * len(group_match_rows) + 38) if group_match_rows else 200
        st.dataframe(group_match_rows, use_container_width=True, height=height)

    # ── Interactive knockout scoreboard ──
    st.subheader("淘汰赛计分板")
    st.caption("点击「+」「−」记录比分，先到21分且领先2分者获胜自动晋级")

    # Group matches by round
    ko_rounds: dict = {}
    for m in knockout_matches:
        ko_rounds.setdefault(m["阶段"], []).append(m)

    round_order = ["1/16决赛", "1/8决赛", "1/4决赛", "半决赛", "决赛"]
    round_names = [r for r in round_order if r in ko_rounds]

    for rname in round_names:
        st.markdown(f"### 🏸 {rname}")
        matches = ko_rounds[rname]

        for m in matches:
            key = f"{m['阶段']}_{m['场次']}"
            score = st.session_state.ko_scores[key]

            p1 = resolve_name(m["选手1"])
            p2 = resolve_name(m["选手2"])

            # Card
            st.markdown(
                f"<div style='background:linear-gradient(135deg,#1a1a2e,#16213e);"
                f"border-radius:16px;padding:16px 20px 4px;margin-bottom:16px;"
                f"border:1px solid #333366;'>",
                unsafe_allow_html=True,
            )

            # Title row
            st.markdown(
                f"<div class='sc-title'>第{m['场次']}场　"
                f"{'🏆 ' + score['winner'] if score['done'] else '⚡ 进行中'}</div>",
                unsafe_allow_html=True,
            )

            # Main row: two players side by side
            c1, c2 = st.columns([1, 1])

            # ── Player 1 ──
            with c1:
                done_p1 = score["done"] and score["winner"] == p1
                st.markdown(
                    f"<div class='sc-name' style='color:white'>{p1}</div>",
                    unsafe_allow_html=True,
                )
                sub = st.columns([1, 2, 1])
                with sub[0]:
                    btn_m1 = st.button("−", key=f"m1_{key}")
                with sub[1]:
                    st.markdown(
                        f"<div class='sc-score' "
                        f"style='color:{'#4CAF50' if done_p1 else '#FFD700'}'"
                        f">{score['p1']}</div>",
                        unsafe_allow_html=True,
                    )
                with sub[2]:
                    btn_p1 = st.button("+", key=f"p1_{key}")

            # ── Player 2 ──
            with c2:
                done_p2 = score["done"] and score["winner"] == p2
                st.markdown(
                    f"<div class='sc-name' style='color:white'>{p2}</div>",
                    unsafe_allow_html=True,
                )
                sub = st.columns([1, 2, 1])
                with sub[0]:
                    btn_m2 = st.button("−", key=f"m2_{key}")
                with sub[1]:
                    st.markdown(
                        f"<div class='sc-score' "
                        f"style='color:{'#4CAF50' if done_p2 else '#FFD700'}'"
                        f">{score['p2']}</div>",
                        unsafe_allow_html=True,
                    )
                with sub[2]:
                    btn_p2 = st.button("+", key=f"p2_{key}")

            # Process score changes
            if btn_p1:
                score["p1"] = min(99, score["p1"] + 1)
            if btn_m1:
                score["p1"] = max(0, score["p1"] - 1)
            if btn_p2:
                score["p2"] = min(99, score["p2"] + 1)
            if btn_m2:
                score["p2"] = max(0, score["p2"] - 1)

            # Check win (first to 21, lead by 2)
            if not score["done"]:
                if score["p1"] >= 21 and score["p1"] - score["p2"] >= 2:
                    score["done"] = True
                    score["winner"] = p1
                    st.session_state.winner_map[m["晋级"]] = p1
                elif score["p2"] >= 21 and score["p2"] - score["p1"] >= 2:
                    score["done"] = True
                    score["winner"] = p2
                    st.session_state.winner_map[m["晋级"]] = p2

            # Status
            if score["done"]:
                st.markdown(
                    f"<div class='sc-winner-badge' style='background:#1b5e20;color:#81C784;'>"
                    f"🏆 {score['winner']} 获胜晋级</div>",
                    unsafe_allow_html=True,
                )
            else:
                p1_lead = score["p1"] - score["p2"]
                if p1_lead > 0:
                    status_text = f"{p1} 领先 {p1_lead} 分"
                elif p1_lead < 0:
                    status_text = f"{p2} 领先 {-p1_lead} 分"
                else:
                    status_text = "平分"
                st.markdown(
                    f"<div class='sc-winner-badge' style='background:#1a3a5c;color:#90CAF9;'>"
                    f"⚡ {status_text}</div>",
                    unsafe_allow_html=True,
                )

            # Close card
            st.markdown("</div>", unsafe_allow_html=True)

    # ── Bracket status overview ──
    with st.expander("查看晋级路线图"):
        bracket_html = render_bracket_html(knockout_matches)
        for old, new in st.session_state.get("winner_map", {}).items():
            bracket_html = bracket_html.replace(old, f"<strong>{new}</strong>")
        st.markdown(bracket_html, unsafe_allow_html=True)

    # ── Knockout table ──
    with st.expander("查看淘汰赛表格"):
        table_rows = []
        for m in knockout_matches:
            row = dict(m)
            row["选手1"] = resolve_name(m["选手1"])
            row["选手2"] = resolve_name(m["选手2"])
            row["晋级"] = resolve_name(m["晋级"])
            # Add scores if available
            key = f"{m['阶段']}_{m['场次']}"
            if key in st.session_state.ko_scores:
                s = st.session_state.ko_scores[key]
                row["比分"] = f"{s['p1']}:{s['p2']}"
                row["状态"] = ("✅ " + s["winner"]) if s["done"] else "⚡进行中"
            table_rows.append(row)
        height = min(400, 35 * len(table_rows) + 38) if table_rows else 200
        st.dataframe(table_rows, use_container_width=True, height=height)

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
