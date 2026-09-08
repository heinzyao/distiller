# 部署資源收斂

盤點與執行日期：2026-09-08。起因是升級 GitHub Actions 版本時，發現
`deploy.yml` 有一筆未提交的服務改名，往下追出一組彼此不一致的部署資源。

盤點時沒有任何東西是壞的 —— 資料每週有更新、bot 正常運作。問題是同一件事
存在兩三套資源，而真正在運作的那套不是 CI 部署的那套。

## 盤點結果

真正在維護資料的是**本機 launchd**：`~/Library/LaunchAgents/com.distiller.diffords.plist`，
每週日 04:00 跑 `scripts/run_diffords.sh`，寫入 `gs://diffords-cocktails-data`。
最近一次 2026-09-06 04:00 成功（新增 104 筆、跳過 6842 筆）。

雲端則留著兩套從未收斂的舊資源：

| 資源 | 狀態 |
|---|---|
| Cloud Scheduler `distiller-weekly-scrape` / `distiller-weekly-diffords` | **PAUSED**，非執行中 |
| Cloud Run job `distiller-scraper` / `distiller-diffords` | 最後執行 2026-05-17，寫入 `distiller-data` |
| Cloud Run service `distiller-bot`（rev 00039）/ `diffords-cocktails-bot`（rev 00001） | 兩個並存，image 相同 |

> 訂正：盤點初稿寫成「Scheduler 每週準時執行、產出無人使用」，實際上兩個
> Scheduler 都是 PAUSED，自 2026-05 起就沒再觸發過。是休眠的殘留，不是在跑的殭屍。

## 決定

1. **服務名切到 `diffords-cocktails-bot`**，淘汰 `distiller-bot`。
2. **排程維持本機 launchd**，雲端排程不再使用，並寫進 `CLAUDE.md`。
3. **plist 只留在用的那份**（`com.distiller.diffords`）。

## 已完成

- [x] 刪除 Cloud Scheduler `distiller-weekly-scrape`、`distiller-weekly-diffords`
- [x] 刪除 Cloud Run job `distiller-scraper`、`distiller-diffords`
- [x] 刪除 repo 內未安裝也未使用的 `com.diffords-scraper.plist`
- [x] `CLAUDE.md` 新增 Deployment and scheduling 段落，寫明排程刻意放在本機
- [x] 提交 `deploy.yml` / `scripts/deploy_gcp.sh` 的服務改名

## 待辦（需人工介入，有先後順序）

- [ ] push 到 main，讓 CI 部署出 `diffords-cocktails-bot` 的新 revision
- [ ] **在 LINE Developers Console 把 webhook 改成新服務的 `/webhook`**
      —— 這步之前，流量仍由 `distiller-bot` 承接，改了 CI 也沒用
- [ ] 驗證 bot 指令正常
- [ ] 刪除 `distiller-bot` 服務

## 未處理：`gs://distiller-data`

原本列為「確認無其他用途後刪除」，查證後**發現不只一個檔案**，因此保留：

| 物件 | 大小 | 最後更新 |
|---|---|---|
| `diffords.db` | 48 KiB | 2026-04-13 |
| `distiller.db` | 4.98 MiB | 2026-05-17 |

`distiller.db` 是舊的烈酒評論資料庫。`CLAUDE.md` 寫明烈酒評論爬蟲已不在專案
範圍內，但資料本身是否要留作封存沒有記錄。**在決定之前不要刪這個 bucket。**

## Review

雲端殘留資源已清乾淨，Cloud Run 現在只剩 `diffords-cocktails-scraper` 一個 job。
服務改名的 commit 已備妥但未 push —— push 會觸發真正的 Cloud Run 部署，且必須
搭配 LINE webhook 的手動切換才算完成。
