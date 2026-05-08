import streamlit as st
import pandas as pd
import random
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
    """Round-robin within a group."""
    return [(group[i], group[j]) for i in range(len(group)) for j in range(i + 1, len(group))]


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

    group_size = st.number_input("每组人数", min_value=2, max_value=10, value=4)
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

    # Split groups
    groups = [shuffled[i:i + group_size] for i in range(0, len(shuffled), group_size)]

    if len(groups) > 1:
        sizes = [len(g) for g in groups]
        if max(sizes) != min(sizes):
            st.info(f"各组人数：{', '.join(str(s) for s in sizes)}（末组少人属正常）")

    # Group matches
    group_match_rows = []
    for idx, group in enumerate(groups):
        gname = _get_group_name(idx)
        for mi, (a, b) in enumerate(create_group_matches(group), start=1):
            group_match_rows.append({
                "小组": f"{gname}组", "场次": mi, "选手1": a, "选手2": b,
            })

    # Knockout matches
    knockout_matches = create_knockout_matches(groups, effective_seed)

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

    # ── Group match table ──
    st.subheader("小组赛对战表")
    height = min(400, 35 * len(group_match_rows) + 38) if group_match_rows else 200
    st.dataframe(group_match_rows, use_container_width=True, height=height)

    # ── Knockout bracket ──
    st.subheader("淘汰赛对阵图")
    bracket_html = render_bracket_html(knockout_matches)
    st.markdown(bracket_html, unsafe_allow_html=True)

    # ── Knockout table ──
    with st.expander("查看淘汰赛表格"):
        height = min(400, 35 * len(knockout_matches) + 38) if knockout_matches else 200
        st.dataframe(knockout_matches, use_container_width=True, height=height)

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
