# 📒 keihi-app（経費・売上管理アプリ）

軽貨物ドライバー向けに開発した、  
**売上・固定費・経費管理 + Excel反映まで一括で行える業務支援アプリ**です。

Streamlit + SQLite + Excel 自動連携で、  
日々の記帳〜月次管理を効率化しています。

---

## 🚀 主な機能

- 📈 売上入力（月別管理・上書き対応）
- 🏠 固定費管理（月別・自動更新）
- 🧾 経費入力（ワンクリ登録 / 手入力対応）
- 🧩 調整用データ管理（年次まとめ用）
- 📤 Excel自動反映（並び・書式保持）
- 💾 SQLiteローカル保存
- 🖥 macOSアイコン起動対応

---

## 🛠 使用技術

| 項目 | 内容 |
|------|------|
| 言語 | Python 3.12 |
| フレームワーク | Streamlit |
| DB | SQLite |
| Excel操作 | openpyxl |
| バージョン管理 | Git / GitHub |

---

## 📸 Screenshots

### 📈 売上入力
<img src="screenshots/sales.png" width="600">

### 🏠 固定費管理
<img src="screenshots/fixed.png" width="600">

### 🧾 経費入力
<img src="screenshots/expense.png" width="600">

### 🧩 調整用管理
<img src="screenshots/adjustment.png" width="600">

### 📤 Excel反映
<img src="screenshots/export.png" width="600">

---

## ▶ 起動方法

### ターミナル起動

cd ~/Desktop/keihi_app  
streamlit run app.py  

### macOS アイコン起動

Automator + launcher.sh により  
デスクトップから起動可能。

---

## 📂 ディレクトリ構成

keihi_app/  
├── app.py  
├── db.py  
├── export.py  
├── templates.json  
├── data.db  
├── screenshots/  
│   ├── sales.png  
│   ├── fixed.png  
│   ├── expense.png  
│   ├── adjustment.png  
│   └── export.png  
└── README.md  

---

## 🎯 開発目的

- 日々の経費・売上管理の自動化  
- 月末作業の削減  
- 確定申告対応の効率化  
- 業務アプリのポートフォリオ化  

---

## 📌 特徴

✔ 実務ベース設計  
✔ 継続改善型開発  
✔ UI/UX重視  
✔ 現場フィードバック反映  

---

## 👤 Author

たつのり  
軽貨物ドライバー / 個人開発  

---

## 📄 License

This project is for personal and portfolio use.

---

## ✅ 更新方法

git add README.md  
git commit -m "update README"  
git push
