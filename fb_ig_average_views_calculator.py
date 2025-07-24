import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="IG / FB Reels 平均觀看分析", layout="centered")

st.title("📊 IG / FB Reels 觀看數分析工具")
st.markdown("上傳 Meta IG 或 FB 報表（CSV），選擇分析期間，自動顯示 Reels 的影片數量、總觀看數、平均觀看數。")

# 上傳 CSV
uploaded_file = st.file_uploader("📁 上傳 CSV 檔案", type="csv")

# 日期輸入
start_date = st.date_input("開始日期", datetime(2025, 6, 26))
end_date = st.date_input("結束日期", datetime(2025, 7, 23))

def analisar_rede_social_auto(df, data_inicio, data_fim):
    df["Publish time"] = pd.to_datetime(df["Publish time"], errors="coerce")
    data_inicio = pd.to_datetime(data_inicio)
    data_fim = pd.to_datetime(data_fim)
    df = df[(df["Publish time"] >= data_inicio) & (df["Publish time"] <= data_fim)]

    # 自動判斷平台
    if "Page name" in df.columns and "Permalink" in df.columns:
        plataforma = "facebook"
        df["Tipo"] = df["Permalink"].apply(
            lambda x: "Reel" if "/reel/" in str(x) else "Video" if "/videos/" in str(x) else "Outro"
        )
    elif "Account name" in df.columns and "Post type" in df.columns:
        plataforma = "instagram"
        df["Tipo"] = df["Post type"].apply(
            lambda x: "Reel" if str(x).strip().lower() == "ig reel" else "Outro"
        )
    else:
        return "無法判斷平台：缺少必要欄位"

    # 只保留 Reels
    df = df[df["Tipo"] == "Reel"]

    if "Views" not in df.columns:
        return "報表中缺少 'Views' 欄位"

    df = df[pd.to_numeric(df["Views"], errors="coerce").notna()]
    df["Views"] = df["Views"].astype(float)

    total_views = df["Views"].sum()
    num_posts = df.shape[0]
    avg_views = total_views / num_posts if num_posts > 0 else 0

    return f"""
✅ 平台：{plataforma.capitalize()}
📅 區間：{data_inicio.date()} 到 {data_fim.date()}
🎞️ Reels 貼文數量：{num_posts}
👀 總觀看數：{int(total_views):,}
📊 平均觀看數：{round(avg_views, 2):,}
""".strip()

# 執行分析
if uploaded_file is not None:
    with st.spinner("正在分析中..."):
        try:
            df = pd.read_csv(uploaded_file)
            resultado = analisar_rede_social_auto(df, start_date, end_date)
            st.success("分析完成")
            st.text(resultado)
        except Exception as e:
            st.error(f"分析時發生錯誤：{e}")
