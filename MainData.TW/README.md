# Xanadu Next 繁體中文補丁（台灣用語）/ Traditional Chinese Patch

由簡體漢化移植的繁體版本（文本、圖像移植自娛樂通代理版《迷城的國度》，
字庫與文本流程由 `Xanadu_TC/` 工具鏈從源頭重建）。

## 版本

- TW patch v0.2（與 `Xanadu_TC/xanadu_tc.md` 記錄的流程同步）
- 適用遊戲版本：GOG 版 Xanadu Next（exe 由 GOG 版打補丁）
  Steam 版 1.0.2.0 需要以 Steam exe 為底重新打 `Text/exe内文本` 补丁，
  本包 exe 不適用 Steam 版。

## 安裝說明

將本目錄內所有文件覆蓋至遊戲根目錄（`XANADU.exe` 所在目錄）。
如需恢復，請使用 GOG Galaxy 的驗證/修復功能。

## 內容

- `DATA/SYSTEM/system.arc`：對話/系統字庫（繁體字形重製）
- `DATA/Map/area{00,05,06,07,08,09,10}.arc`：劇本漢化（繁體）
- `DATA/chr/Object.tbl`：怪物名漢化
- `DATA/equip/equip.arc`：道具/守護者名漢化
- `DATA/Picture/picture.arc`：11 張標題/頭目卡繁體重製
- `XANADU.exe`：程序內文本漢化（GOG 版）
- `xanadu_cfg.exe`：對話框文本漢化（UTF-16 部分為繁體）；選單選項
  （下拉選項等單字節 GBK 字符串，在非簡體系統下顯示為亂碼）保留 GOG
  英文原文

## 範圍

與簡體版相同：area00、05–10 及系統部分；area01–04、12、14、20、
51、52、60 未漢化（與簡體版範圍一致）。

## 已知事項

- 以 `Xanadu_TC/tools/verify_build.py` 全量校驗通過。
- 60 幀跳躍判定問題同簡體版說明（刷新率設為粗糙）。
