# Xanadu_Steam_CN



> *本项目仅应用于Steam版Xanadu Next（当前官方版本 1.0.2.0）
>
> *计划中所有的汉化文本、汉化图像均移植自娱乐通代理版《迷城的国度》，目前在方块平台仍有销售。本次汉化移植离不开代理商与原汉化人员的付出，希望大家享受本次移植的同时尽可能支持原代理商。
>
> [方块平台上本作原代理版的传送门](http://store.cubejoy.com/html/en/store/goodsdetail/detail200.html)



## 下载地址

当前补丁版本为1.00，更新日期2019.07.09

##### 度盘链接：

https://pan.baidu.com/s/1UZguqK8B6bZNhs76QqkGow 提取码: 5v86

##### MEGA盘链接：

https://mega.nz/#!CX5kkawJ!5X8lJGDJBUYO9PRRbU62DiU5-CxzFUpevhX-YO_qEoo



## 安装说明

覆盖至游戏根目录
若需恢复为英文原版可直接使用Steam的验证完整性功能



## 特别感谢

娱乐通汉化版的所有原工作人员

ZenHax论坛的[Ekey](https://www.zenhax.com/viewtopic.php?f=9&t=3347&hilit=xanadu)&站长[aluigi](https://www.zenhax.com/viewtopic.php?f=9&t=11072)，提供了dat解包脚本与字模解密脚本，没有他们的大腿是完不成本次移植的
@yzzbz 点拨了游戏可能使用的壳和对应工具


## 使用工具

- [Quickbms](http://aluigi.altervista.org/)（解包封包）
- [falcnvrt](falcnvrt/itm Converter/itp Converter/iti Converter)
- [MadEdit-Mod](https://sourceforge.net/projects/madedit-mod/)（日文汉字转换、文本编辑）
- [TiledGlyph](https://github.com/wmltogether/TiledGlyph)（字模制作）
- CrystalTile2（字模替换）
- Steamless（脱壳工具）


## 其他说明

1.
   有任何汉化方面的问题请直接回复反馈，将会尽量修正

2. 有一处拿精灵卡片的跳跳乐，和60帧黑魂类似会有跳跃判定上的变化，游戏内刷新率设置改为粗糙后有奇效

3. 死者的异界没有经过比较完整的测试，同样有问题可以尽快反馈

4. GOG版请额外下载对应exe文件替换



## TODO LIST

![Progress](http://progressed.io/bar/100)简单处理脚本的工具编写

![Progress](http://progressed.io/bar/99)主程序内文本的汉化

![Progress](http://progressed.io/bar/100)文本移植

![Progress](http://progressed.io/bar/100)图片移植

![Progress](http://progressed.io/bar/85)测试

-AND MORE


## 繁體中文版（Traditional Chinese）

本目錄另有繁體中文（台灣用語）移植，見工作區 `Xanadu_TC/`（完整工具鏈
與流程記錄 `xanadu_tc.md`）與成品 `MainData.TW/`（安裝方式同上，直接
覆蓋至遊戲根目錄；exe 以 GOG 版為底）：

- 文本：簡體文本經 OpenCC `s2twp` 轉換＋台灣用語修正（滑鼠/軟體/記憶體/
  影片/網路/遊標/預設/存檔/解析度/視窗/更新率，系統菜單→系統選單）＋
  日文漢字正規化（霊剣亜図徳→靈劍亞圖德等，`Xanadu_TC/tools/jpnorm.py`
  共 184 組），仍以 Shift-JIS 編碼保存（缺字重映射表 164 項）。
- 字庫：沿用 Shift-JIS 槽位方案，以 Noto Sans TC（缺字 fallback SC）
  重繪字模（襯線體已換為黑體，更接近原版字形），
  `font_scn/font_sys` 各重繪 165 槽（含説槽說字）。
  字模索引公式以反匯編遊戲主程序字形查找函數為準（見 `xanadu_tc.md`）。
- 圖片：11 張 AREANAME/BOSS 卡以標楷體重製（標題下為同向模糊光暈，
  已驗證非鏡像倒影）。
- 範圍與簡體版相同（area00、05–10＋系統）；area01–04、12、14、20、
  51、52、60 未漢化。
- 注意：繁體 exe 以 GOG 版為底，Steam 版需另行移植。
- 成品 `MainData.TW/`（23 個文件，與實測版本哈希一致）附 `BUILD_INFO.txt`
  可核對構建日期；遊戲內實測＋全量校驗（`verify_1_3.py`、
  `verify_build.py`）皆通過。
