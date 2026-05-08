import streamlit as st
import pandas as pd
import random
import requests
from io import BytesIO


st.set_page_config(page_title="羽毛球对战表生成器", page_icon="🏸", layout="wide")

st.markdown("""
<style>
.main-title {font-size:42px;font-weight:bold;color:#155E3B;}
.sub-title {font-size:18px;color:#555;}
.group-card {
    background-color:#F3FFF6;
    padding:18px;
    border-radius:16px;
    border:1px solid #BFE8C8;
    margin-bottom:15px;
}
.match-card {
    background-color:white;
    padding:14px;
    border-radius:14px;
    border:1px solid #DDD;
    margin-bottom:10px;
}
.vs {font-weight:bold;color:#E67E22;}
</style>
""", unsafe_allow_html=True)


def load_names(uploaded_file, excel_url):
    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file, header=None)
    elif excel_url:
        response = requests.get(excel_url, timeout=20)
        response.raise_for_status()
        df = pd.read_excel(BytesIO(response.content), header=None)
    else:
        return []

    names = df.iloc[:, 0].dropna().astype(str).tolist()
    names = [name.strip() for name in names if name.strip()]
    return names


def create_group_matches(group):
    matches = []
    for i in range(len(group)):
        for j in range(i + 1, len(group)):
            matches.append((group[i], group[j]))
    return matches


def next_power_of_two(n):
    power = 1
    while power < n:
        power *= 2
    return power


def get_round_name(size):
    if size == 2:
        return "决赛"
    elif size == 4:
        return "半决赛"
    elif size == 8:
        return "1/4决赛"
    elif size == 16:
        return "1/8决赛"
    else:
        return f"{size}强赛"


def create_knockout_matches(groups):
    players = []

    for index in range(len(groups)):
        group_name = chr(ord("A") + index)
        players.append(f"{group_name}组第1")
        players.append(f"{group_name}组第2")

    random.shuffle(players)

    size = next_power_of_two(len(players))

    while len(players) < size:
        players.append("轮空")

    all_knockout_matches = []
    current_players = players[:]
    current_size = size

    while current_size >= 2:
        round_name = get_round_name(current_size)
        next_round_players = []

        for i in range(0, len(current_players), 2):
            player1 = current_players[i]
            player2 = current_players[i + 1]
            match_no = i // 2 + 1
            winner_name = f"{round_name}第{match_no}场胜者"

            all_knockout_matches.append({
                "阶段": round_name,
                "场次": match_no,
                "选手1": player1,
                "选手2": player2,
                "晋级": winner_name,
            })

            next_round_players.append(winner_name)

        current_players = next_round_players
        current_size = current_size // 2

    return all_knockout_matches


def create_excel_file(groups, group_matches, knockout_matches):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        group_rows = []

        for index, group in enumerate(groups):
            group_name = chr(ord("A") + index)
            group_rows.append({
                "小组": f"{group_name}组",
                "成员": "、".join(group),
            })

        pd.DataFrame(group_rows).to_excel(writer, sheet_name="小组分配", index=False)
        pd.DataFrame(group_matches).to_excel(writer, sheet_name="小组赛对战表", index=False)
        pd.DataFrame(knockout_matches).to_excel(writer, sheet_name="淘汰赛对战表", index=False)

    output.seek(0)
    return output


st.markdown('<div class="main-title">🏸 羽毛球男单随机对战表生成器</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">上传 Excel 或输入 Excel 链接，自动生成完整对战表</div>', unsafe_allow_html=True)

st.write("")

source_type = st.radio("选择名单来源", ["上传 Excel", "Excel 下载链接"])

uploaded_file = None
excel_url = ""

if source_type == "上传 Excel":
    uploaded_file = st.file_uploader("📄 上传 Excel 文件（第一列是姓名）", type=["xlsx", "xls"])
else:
    excel_url = st.text_input("🔗 输入 Excel 下载链接")

group_size = st.number_input("每组人数", min_value=2, max_value=10, value=4)

if st.button("🎲 随机生成完整对战表"):
    try:
        names = load_names(uploaded_file, excel_url)

        if len(names) < 2:
            st.error("至少需要 2 个姓名")
        else:
            st.success(f"成功读取 {len(names)} 个姓名")

            random_names = names[:]
            random.shuffle(random_names)

            groups = []
            for i in range(0, len(random_names), group_size):
                groups.append(random_names[i:i + group_size])

            group_matches = []

            st.subheader("👥 随机分组结果")
            cols = st.columns(3)

            for index, group in enumerate(groups):
                group_name = chr(ord("A") + index)

                with cols[index % 3]:
                    st.markdown(
                        f"""
                        <div class="group-card">
                            <h3>{group_name}组</h3>
                            <p>{"、".join(group)}</p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                matches = create_group_matches(group)

                for match_index, match in enumerate(matches, start=1):
                    group_matches.append({
                        "小组": f"{group_name}组",
                        "场次": match_index,
                        "选手1": match[0],
                        "选手2": match[1],
                    })

            st.subheader("📅 小组赛对战表")
            st.dataframe(group_matches, use_container_width=True)

            knockout_matches = create_knockout_matches(groups)

            st.subheader("🏆 淘汰赛卡片展示")
            knockout_df = pd.DataFrame(knockout_matches)
            stages = knockout_df["阶段"].unique()

            for stage in stages:
                st.markdown(f"### {stage}")
                stage_matches = knockout_df[knockout_df["阶段"] == stage]
                cols = st.columns(2)

                for index, row in enumerate(stage_matches.to_dict("records")):
                    with cols[index % 2]:
                        st.markdown(
                            f"""
                            <div class="match-card">
                                <b>第 {row["场次"]} 场</b><br>
                                {row["选手1"]} <span class="vs">VS</span> {row["选手2"]}<br>
                                <small>晋级：{row["晋级"]}</small>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

            st.subheader("📋 淘汰赛表格")
            st.dataframe(knockout_matches, use_container_width=True)

            excel_file = create_excel_file(groups, group_matches, knockout_matches)

            st.download_button(
                label="⬇️ 下载 Excel 对战表",
                data=excel_file,
                file_name="羽毛球男单随机对战表.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"生成失败：{e}")