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

# 以網址網域為主的偵測，失敗再用欄位特徵打分
def detect_platform(df: pd.DataFrame) -> str:
    cols = set(df.columns)

    # 1) 先看 Permalink 網域（最可靠）
    if "Permalink" in cols:
        s = df["Permalink"].astype(str).str.lower()
        ig_hits = s.str.contains("instagram.com", na=False).sum()
        fb_hits = s.str.contains("facebook.com", na=False).sum()
        # 如果明顯偏向某一方，就回傳
        if ig_hits > fb_hits and ig_hits > 0:
            return "instagram"
        if fb_hits > ig_hits and fb_hits > 0:
            return "facebook"
        # 若網址沒有網域資訊，也別急著判定，繼續用欄位特徵來看

    # 2) 欄位特徵打分
    ig_like = {
        "Account name", "Username", "Owner", "Owner Name", "Content type",
        "Media type", "Caption", "IG Post ID", "Instagram post ID",
        "Insights for Instagram Reels", "Reel audio", "Reel length"
    }
    fb_like = {
        "Page name", "Page ID", "Message", "FB Post ID", "Story ID",
        "Permalink URL", "Is video", "Post ID", "Lifetime total video views"
    }

    ig_score = len(ig_like & cols)
    fb_score = len(fb_like & cols)

    if ig_score > fb_score and ig_score >= 1:
        return "instagram"
    if fb_score > ig_score and fb_score >= 1:
        return "facebook"

    # 3) 最後的安全網：看 Post type / Content type 的值裡是否有 reel/video 字樣
    sample_cols = [c for c in ["Post type", "Content type"] if c in cols]
    for c in sample_cols:
        s = df[c].astype(str).str.lower()
        if s.str.contains("reel", na=False).sum() > 0 and not s.str.contains("page", na=False).any():
            # IG 常見有 "reel" 字樣、且不像 FB Page
            return "instagram"

    return "unknown"


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
    # 1) 解析日期欄位（統一 tz-aware）
    date_col = find_date_column(df)
    if not date_col:
        st.error("找不到日期欄位，請確認報表是否包含 Publish time / Publish date / Created time 等欄位。")
        return

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce", utc=True)
    df = df.dropna(subset=[date_col])
    if df.empty:
        st.error(f"日期欄位「{date_col}」無法解析為日期時間。")
        return

    # 轉至當地時區
    df[date_col] = df[date_col].dt.tz_convert(LOCAL_TZ)

    # 使用者區間 -> 當地時區的日初/日末（tz-aware）
    start_ts = pd.Timestamp(datetime.combine(start_d, time.min), tz=LOCAL_TZ)
    end_ts = pd.Timestamp(datetime.combine(end_d, time.max), tz=LOCAL_TZ)

    # 篩選區間
    df = df[(df[date_col] >= start_ts) & (df[date_col] <= end_ts)]
    if df.empty:
        st.warning("在選定的日期區間內沒有資料。")
        return

    # 2) 偵測平台（提供手動覆蓋）
    auto_platform = detect_platform(df)  # 'facebook' | 'instagram' | 'unknown'
    options = ["facebook", "instagram"]
    default_idx = 0 if auto_platform == "facebook" else 1
    if auto_platform == "unknown":
        st.info("無法可靠判斷資料來源平台，請手動選擇。")
        default_idx = 0  # 預設選 Facebook，但可自行切換
    platform = st.selectbox("平台（可手動覆蓋）", options, index=default_idx, help="若自動判斷有誤，請在此切換。")

    # 3) 依平台分類 Reel / Video
    if platform == "facebook":
        df["Tipo"] = df.apply(classify_type_fb, axis=1)
    else:
        df["Tipo"] = df.apply(classify_type_ig, axis=1)

    # 僅保留 Reel / Video
    df = df[df["Tipo"].isin(["Reel", "Video"])]
    if df.empty:
        st.warning("區間內沒有 Reel 或 Video 貼文。")
        return

    # 4) 選擇觀看數欄位
    view_opts = find_view_candidates(df)
    if not view_opts:
        st.error("找不到觀看數欄位，請確認是否包含 Views / Plays / Video views 等欄位。")
        return
    default_index = view_opts.index("Views") if "Views" in view_opts else 0
    views_col = st.selectbox("選擇觀看數欄位", view_opts, index=default_index)

    # 5) 數值轉換與清理
    df[views_col] = pd.to_numeric(df[views_col], errors="coerce")
    df = df[df[views_col].notna()]
    if df.empty:
        st.warning(f"欄位「{views_col}」在區間內沒有可用的數值。")
        return

    # 6) 彙總統計（各類型 + 全部合計）
    grouped = (
        df.groupby("Tipo", as_index=False)[views_col]
        .agg(貼文數量="count", 總觀看數="sum")
        .sort_values("Tipo")
    )
    grouped["平均觀看數"] = (grouped["總觀看數"] / grouped["貼文數量"]).round(2)
    grouped["總觀看數"] = grouped["總觀看數"].round(0).astype(int)

    # ▶ Reel + Video 合計（加權平均 = 總觀看數 / 貼文數量）
    total_posts = int(df.shape[0])
    total_views = int(df[views_col].sum())
    overall_avg = round(total_views / total_posts, 2) if total_posts else 0.0

    overall_row = pd.DataFrame(
        [{
            "Tipo": "Reel + Video（合計）",
            "貼文數量": total_posts,
            "總觀看數": total_views,
            "平均觀看數": overall_avg,
        }]
    )

    # 合併並顯示
    grouped_with_total = pd.concat([overall_row, grouped], ignore_index=True)

    st.subheader("分析結果")
    st.write(f"平台（自動判斷）：{auto_platform}")
    st.write(f"平台（實際使用）：{platform}")
    st.write(f"區間：{start_d} 到 {end_d}")
    st.write(f"日期欄位：{date_col}")
    st.write(f"觀看數欄位：{views_col}")

    st.metric("全影片平均觀看數（Reel + Video）", f"{overall_avg:,.2f}")
    st.dataframe(grouped_with_total, use_container_width=True)

    # 明細下載
    with st.expander("下載區間內的明細（依選擇的欄位整理）"):
        cols_to_show = [date_col, views_col, "Tipo"]
        extra_cols = [
            c for c in ["Page name", "Account name", "Permalink", "Post type", "Content type", "Title"]
            if c in df.columns
        ]
        detail = df[cols_to_show + extra_cols].sort_values(date_col, ascending=False).copy()
        csv = detail.to_csv(index=False).encode("utf-8-sig")
        st.download_button("下載 CSV", csv, file_name="filtered_details.csv", mime="text/csv")
        st.dataframe(detail.head(50), use_container_width=True)

    # 除錯資訊（需要時再展開）
    with st.expander("除錯資訊（需要時再展開）"):
        st.write("date_col dtype:", df[date_col].dtype)
        st.write("date_col tz:", getattr(df[date_col].dt, "tz", None))
        st.write("start_ts:", start_ts, "tz:", start_ts.tz)
        st.write("end_ts:", end_ts, "tz:", end_ts.tz)
        if "Permalink" in df.columns:
            s = df["Permalink"].astype(str).str.lower()
            st.write("instagram.com hits:", int(s.str.contains("instagram.com", na=False).sum()))
            st.write("facebook.com hits:", int(s.str.contains("facebook.com", na=False).sum()))

# --------- 主流程 --------- #
if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
    except UnicodeDecodeError:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, encoding="utf-8-sig")
    except Exception as e:
        st.error(f"讀取 CSV 時發生錯誤：{e}")
        st.stop()

    with st.spinner("分析中..."):
        analyze(df, start_date, end_date)
else:
    st.info("請先上傳 CSV 檔案。")
