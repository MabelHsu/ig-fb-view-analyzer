import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime, time
from typing import Optional, List
from zoneinfo import ZoneInfo  # Python 3.9+

# ========= 基本設定 ========= #
st.set_page_config(page_title="IG / FB Reels 平均觀看分析", layout="centered")

st.title("IG / FB 影片平均觀看數計算")
st.markdown(
    "上傳 Meta IG 或 FB 報表（CSV），選擇分析期間，自動顯示 Reels 和 Videos 的影片數量、總觀看數、平均觀看數。"
)

# 你的在地時區（用來轉換與比較）
LOCAL_TZ = ZoneInfo("America/Sao_Paulo")

# 1) 檔案上傳
uploaded_file = st.file_uploader("上傳 CSV 檔案", type=["csv"])

# 2) 日期區間（預設今天與今天-7）
start_date = st.date_input("開始日期", date.today() - timedelta(days=7))
end_date = st.date_input("結束日期", date.today())

if end_date < start_date:
    st.error("結束日期不可早於開始日期。")
    st.stop()

# --------- 工具函式 --------- #
DATE_CANDIDATES: List[str] = [
    "Publish time",
    "Publish date",
    "Published",
    "Date",
    "Created time",
    "Created Time",
    "Created At",
    "Post Created Date",
]

VIEW_CANDIDATES: List[str] = [
    "Views",
    "Video views",
    "Plays",
    "Video plays",
    "Lifetime total video views",
    "Lifetime Post total video views",
    "Lifetime Video Views",
]


def find_date_column(df: pd.DataFrame) -> Optional[str]:
    # 先嘗試固定候選
    for c in DATE_CANDIDATES:
        if c in df.columns:
            return c
    # 再嘗試以關鍵字模糊尋找
    lower = {c.lower(): c for c in df.columns}
    for key in lower:
        if ("publish" in key or "created" in key or key == "date") and (
            "time" in key or "date" in key or key in ("date",)
        ):
            return lower[key]
    return None


def find_view_candidates(df: pd.DataFrame) -> List[str]:
    # 以固定候選 + 關鍵字模糊搜尋
    found = [c for c in VIEW_CANDIDATES if c in df.columns]
    # 追加模糊搜尋
    for col in df.columns:
        lc = col.lower()
        if ("view" in lc or "play" in lc) and col not in found:
            found.append(col)
    return found


def detect_platform(df: pd.DataFrame) -> str:
    # 粗略偵測：依欄位判斷
    if "Page name" in df.columns or "Permalink" in df.columns:
        return "facebook"
    if "Account name" in df.columns or "Post type" in df.columns:
        return "instagram"
    return "unknown"


def classify_type_fb(row: pd.Series) -> str:
    link = str(row.get("Permalink", "")).lower()
    post_type = str(row.get("Post type", "")).lower()
    if "/reel" in link:
        return "Reel"
    if "/videos" in link or "video" in post_type:
        return "Video"
    return "Outro"


def classify_type_ig(row: pd.Series) -> str:
    post_type = str(row.get("Post type", row.get("Content type", ""))).lower()
    link = str(row.get("Permalink", "")).lower()
    if "reel" in post_type or "/reel" in link:
        return "Reel"
    if "video" in post_type:
        return "Video"
    return "Outro"


def analyze(df: pd.DataFrame, start_d: date, end_d: date) -> None:
    # 1) 解析日期欄位
    date_col = find_date_column(df)
    if not date_col:
        st.error("找不到日期欄位，請確認報表是否包含 Publish time / Publish date / Created time 等欄位。")
        return

    # **關鍵修正**：統一把日期欄位轉為 tz-aware（先轉 UTC，再轉本地時區）
    # 這樣不論原本是字串、naive datetime、或帶 Z/offset，都能統一比較
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce", utc=True)
    df = df.dropna(subset=[date_col])  # 清除轉換失敗的列，避免後續比較噴錯
    if df.empty:
        st.error(f"日期欄位「{date_col}」無法解析為日期時間。")
        return

    # 轉到本地時區後再做區間篩選（視覺與報表較直覺）
    df[date_col] = df[date_col].dt.tz_convert(LOCAL_TZ)

    # 將使用者選擇的日期區間轉為「本地時區」的日初/日末（tz-aware）
    start_ts = pd.Timestamp(datetime.combine(start_d, time.min), tz=LOCAL_TZ)
    end_ts = pd.Timestamp(datetime.combine(end_d, time.max), tz=LOCAL_TZ)

    # 安全比較（雙方同為 tz-aware 且同一時區）
    df = df[(df[date_col] >= start_ts) & (df[date_col] <= end_ts)]
    if df.empty:
        st.warning("在選定的日期區間內沒有資料。")
        return

    # 2) 偵測平台並分類 Reel / Video
    platform = detect_platform(df)

    if platform == "facebook":
        df["Tipo"] = df.apply(classify_type_fb, axis=1)
    elif platform == "instagram":
        df["Tipo"] = df.apply(classify_type_ig, axis=1)
    else:
        st.error("無法判斷平台，請確認報表欄位是否包含 Page name/Permalink 或 Account name/Post type。")
        return

    # 僅保留 Reel / Video
    df = df[df["Tipo"].isin(["Reel", "Video"])]
    if df.empty:
        st.warning("區間內沒有 Reel 或 Video 貼文。")
        return

    # 3) 選擇觀看數欄位
    view_opts = find_view_candidates(df)
    if not view_opts:
        st.error("找不到觀看數欄位，請確認是否包含 Views / Plays / Video views 等欄位。")
        return

    default_index = view_opts.index("Views") if "Views" in view_opts else 0
    views_col = st.selectbox("選擇觀看數欄位", view_opts, index=default_index)

    # 4) 數值轉換與清理
    df[views_col] = pd.to_numeric(df[views_col], errors="coerce")
    df = df[df[views_col].notna()]
    if df.empty:
        st.warning(f"欄位「{views_col}」在區間內沒有可用的數值。")
        return

    # 5) 彙總統計
    grouped = (
        df.groupby("Tipo", as_index=False)[views_col]
        .agg(貼文數量="count", 總觀看數="sum")
        .sort_values("Tipo")
    )
    grouped["平均觀看數"] = grouped["總觀看數"] / grouped["貼文數量"]
    grouped["總觀看數"] = grouped["總觀看數"].round(0).astype(int)
    grouped["平均觀看數"] = grouped["平均觀看數"].round(2)

    # 6) 顯示結果
    st.subheader("分析結果")
    st.write(f"平台：{platform.capitalize()}")
    st.write(f"區間：{start_d} 到 {end_d}")
    st.write(f"日期欄位：{date_col}")
    st.write(f"觀看數欄位：{views_col}")

    st.dataframe(grouped, use_container_width=True)

    # 額外提供明細下載（可選）
    with st.expander("下載區間內的明細（依選擇的欄位整理）"):
        cols_to_show = [date_col, views_col, "Tipo"]
        extra_cols = [
            c
            for c in ["Page name", "Account name", "Permalink", "Post type", "Content type", "Title"]
            if c in df.columns
        ]
        detail = df[cols_to_show + extra_cols].sort_values(date_col, ascending=False).copy()
        csv = detail.to_csv(index=False).encode("utf-8-sig")
        st.download_button("下載 CSV", csv, file_name="filtered_details.csv", mime="text/csv")
        st.dataframe(detail.head(50), use_container_width=True)

    # （可選）除錯資訊開關
    with st.expander("除錯資訊（需要時再展開）"):
        st.write("date_col dtype:", df[date_col].dtype)
        st.write("date_col tz:", getattr(df[date_col].dt, "tz", None))
        st.write("start_ts:", start_ts, "tz:", start_ts.tz)
        st.write("end_ts:", end_ts, "tz:", end_ts.tz)


# --------- 主流程 --------- #
if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
    except UnicodeDecodeError:
        # 若是 Excel 匯出的 CSV 可能需要指定編碼
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, encoding="utf-8-sig")
    except Exception as e:
        st.error(f"讀取 CSV 時發生錯誤：{e}")
        st.stop()

    with st.spinner("分析中..."):
        analyze(df, start_date, end_date)
else:
    st.info("請先上傳 CSV 檔案。")
