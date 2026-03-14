# Week 3 Assignment: Automated Regional Impact Auditor (ARIA)

# 第 3 週作業：河川洪災避難所風險評估

**繳交期限：下次上課前**

---

## 1. 任務目標 (Goal)

開發一個 Jupyter Notebook 分析流程：利用 **水利署河川圖資** 建立多級警戒緩衝區，結合 **消防署避難收容所資料**（政府開放平台 CSV），評估各行政區的避難所洪災風險與收容量缺口。

**跟課堂 Lab 的差異：**
- Lab 用 osmnx 抓少量資料，學 sjoin 概念 → **作業用政府完整資料，做真實決策分析**
- Lab 做單一 500m buffer → **作業做 500m / 1km / 2km 三級風險區**
- Lab 只看「在不在裡面」→ **作業要回答「收容量夠不夠」**

---

## 2. 資料來源 (Data Sources)

### A. 河川資料 — 水利署

河川面（Polygon）直接下載：

```python
import geopandas as gpd
rivers = gpd.read_file('https://gic.wra.gov.tw/Gis/gic/API/Google/DownLoad.aspx?fname=RIVERPOLY&filetype=SHP')
```

> **瀏覽頁面**：[水利空間資訊服務平台](https://gic.wra.gov.tw/Gis/gic/API/Google/Index.aspx)

### B. 避難收容所資料 — 消防署（政府開放平台）

從政府開放資料平台下載避難收容處所 CSV：

- **來源**：[data.gov.tw/dataset/73242](https://data.gov.tw/dataset/73242)
- 包含全國數千筆避難所，有經緯度、收容人數、地址等欄位

```python
import pandas as pd

shelters_csv = pd.read_csv('避難收容處所.csv')  # 自行下載後放入 data/
shelters = gpd.GeoDataFrame(
    shelters_csv,
    geometry=gpd.points_from_xy(shelters_csv['經度'], shelters_csv['緯度']),
    crs='EPSG:4326'
)
```

> **注意**：原始資料可能有座標為 0、空值、或經緯度反置的問題（Week 2 的教訓）。載入後務必先做資料清理。

### C. 鄉鎮市區界 — 國土測繪中心

用於分區統計與地圖背景：

```python
from urllib.parse import quote
url = 'https://www.tgos.tw/tgos/VirtualDir/Product/3fe61d4a-ca23-4f45-8aca-4a536f40f290/' + quote('鄉(鎮、市、區)界線1140318.zip')
townships = gpd.read_file(url)
```

---

## 3. 核心要求 (Requirements)

### A. 資料載入與清理 (Data Ingestion & Cleaning)

1. 讀取水利署河川面 Shapefile → 檢查 CRS（應為 EPSG:3826）
2. 讀取消防署避難所 CSV → 轉為 GeoDataFrame → 轉換至 **EPSG:3826**
3. **資料清理**：過濾座標為 0 或超出台灣範圍的記錄，記錄清理前後的筆數差異
4. 讀取鄉鎮界 → 轉換至 **EPSG:3826**

### B. 多級緩衝區分析 (Multi-Buffer Risk Zoning)

1. **三級河川警戒緩衝區**：
   - 從 `.env` 讀取參數：`BUFFER_HIGH=500`、`BUFFER_MED=1000`、`BUFFER_LOW=2000`（單位：公尺）
   - 建立三層緩衝區：**高風險（500m）/ 中風險（1km）/ 低風險（2km）**
   - 必須在 EPSG:3826 下做 buffer（Lab 1 的教訓）

2. **空間連接 (Spatial Join)**：
   - `gpd.sjoin()` 找出各級緩衝區內的避難所
   - 標記每個避難所的風險等級：高 / 中 / 低 / 安全
   - 處理一對多問題：若一個避難所同時落在多個緩衝區，取最高風險等級

### C. 收容量缺口分析 (Capacity Gap Analysis)

這是跟 Lab 的關鍵差異——不只看「哪些避難所在風險區」，還要回答實際問題：

1. **分區統計**：按鄉鎮市區彙總
   - 各區高/中/低風險避難所數量
   - 各區風險區內的總收容人數
   - 各區安全避難所的總收容人數

2. **缺口判斷**：
   - 哪些行政區的安全避難所收容量不足（安全區收容量 < 風險區內常住人口的一定比例）？
   - 產出一份 **風險最高的 Top 10 行政區** 排名

### D. 視覺化 (Visualization)

1. **互動式風險地圖**（`.explore()` 或 `folium`）：
   - 河川面（藍色）
   - 三級緩衝區（紅/橙/黃，半透明）
   - 避難所依風險等級著色：紅 = 高風險、橙 = 中風險、黃 = 低風險、綠 = 安全
   - 鄉鎮界作為背景
   - 點擊避難所可顯示名稱、收容人數、風險等級

2. **靜態統計圖**：
   - 長條圖：Top 10 高風險行政區的避難所數量 vs. 收容量
   - 另存 `risk_map.png`

### E. 專業規範 (Infrastructure)

1. **環境變數**：緩衝距離、目標縣市等參數放在 `.env`，用 `python-dotenv` 讀取
2. **Markdown Cells**：每個分析步驟之前寫一段說明（Captain's Log）
3. **GitHub**：使用 `gh` CLI 建立 Repo，`.env` 加入 `.gitignore`
4. **README.md**：包含 **AI 診斷日誌** — 記錄你在過程中遇到的問題及如何解決

---

## 4. 推薦的 Vibe Coding Prompt

> "I need to assess flood risk for shelters near rivers in Taiwan. I have:
> 1. WRA river polygons: `gpd.read_file('https://gic.wra.gov.tw/Gis/gic/API/Google/DownLoad.aspx?fname=RIVERPOLY&filetype=SHP')`
> 2. Fire Agency shelter CSV from data.gov.tw (with lon/lat and capacity columns)
> 3. Township boundaries from TGOS
>
> Help me:
> 1. Clean the shelter CSV (remove rows with 0 or null coordinates)
> 2. Create THREE buffer zones around rivers: 500m (high), 1km (medium), 2km (low)
> 3. Run gpd.sjoin for each buffer and assign risk levels (highest wins)
> 4. Group by township: count shelters per risk level, sum capacity
> 5. Find the Top 10 most at-risk townships
> 6. Create an interactive risk map and a bar chart of the Top 10
> 7. Export shelter_risk_audit.json with each shelter's risk level"

---

## 5. 繳交清單 (Deliverables)

1. **GitHub Repo URL**
2. **`ARIA.ipynb`** — 完整分析 Notebook（含 Markdown 說明）
3. **`shelter_risk_audit.json`** — 避難所風險清單（含 shelter_id、name、risk_level、capacity）
4. **`risk_map.png`** — 靜態風險地圖或統計圖
5. **`README.md`** — 包含 AI 診斷日誌

---

## 6. 評量標準

| 項目 | 比重 |
|------|------|
| 資料載入 + 清理 + CRS 正確處理 | 20% |
| 三級緩衝區 + 空間連接 + 風險分級 | 25% |
| 收容量缺口分析 + 分區統計 | 20% |
| 風險地圖品質（互動 + 靜態） | 15% |
| Git workflow + .env + Markdown + AI 診斷日誌 | 20% |

---

## 7. 提示與注意事項

- **安裝套件**：`pip install geopandas folium mapclassify python-dotenv`
- **河川資料**：可用 `gpd.read_file()` 直接讀取水利署 URL（見上方範例），資料為 EPSG:3826
- **避難所 CSV**：從 [data.gov.tw/dataset/73242](https://data.gov.tw/dataset/73242) 下載，注意編碼（Big5 或 UTF-8）
- **座標清理**：經度應在 119~122、緯度在 21~26 之間，超出範圍的都是問題資料
- **一對多 sjoin**：一個避難所可能同時在 500m 和 1km 緩衝區內，應取最高風險等級（Lab 2 的教訓）
- **Week 3 課堂連結**：Lab 1 教 buffer 概念、Lab 2 教 sjoin 概念 → 作業是進階的完整版

---

*"The buffer renders. The join completes. But is the city's shelter capacity enough to evacuate the flood zone?"*
