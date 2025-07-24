IG & FB 影片觀看數分析工具

公司周報表會用到的分析 Facebook 與 Instagram 匯出報表的小工具，可快速計算指定期間內影片（Videos / Reels）的：
- 影片數量
- 總觀看次數
- 平均觀看次數（每部影片）

部署平台：Streamlit Cloud  
支援檔案格式：Facebook / Instagram 匯出的 CSV 報表  
可自訂分析的日期範圍  

---

## 使用方法（使用 Streamlit 網頁工具）

### 第一次使用：

1. 下載 Facebook / Instagram 的影片成效報表（CSV）
2. 開啟線上工具網址（由你部署後產生）
3. 上傳報表
4. 選擇起始日期（分析的是「影片發佈日」）
5. 點選「開始分析」即可！

---

## 檔案結構

| 檔案             | 說明                       |
|------------------|----------------------------|
| `app.py`         | Streamlit 主程式           |
| `requirements.txt` | 安裝所需 Python 套件      |

---

## 支援的 Post Type

| 平台     | Post Type 名稱     |
|----------|--------------------|
| Facebook | `Videos`, `Reels` |
| Instagram| `IG reel`         |

---
## 問題反饋

聯絡 @MabelHsu
