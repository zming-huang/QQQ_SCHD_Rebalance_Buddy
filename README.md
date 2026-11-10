# QQQ × SCHD Rebalance Buddy

多语言说明 / Multi-language guide / 多言語ガイド / Guía multilingüe

**中文** ｜ [English](#english) ｜ [日本語](#日本語) ｜ [Español](#español)

---

<a id="中文"></a>

## 中文（简体）

基于 `stragy.md`（Cover 增长最优 / 通用投资组合理论）的桌面工具：
**自动取价 + 定期提醒 + 窗口界面操作**，帮你执行「50:50 纪律性再平衡」。

### 快速开始

双击 **`launch.bat`** 即可启动（无需安装任何第三方库，仅用 Python 标准库）。

> 要求：本机已装 Python 3.10+（自带 tkinter）。脚本会自动寻找 pythonw.exe。

### 功能一览

| 页面 | 说明 |
| --- | --- |
| 仪表盘 | QQQ / SCHD 实时价格（红涨绿跌）、组合总市值、当前配置 vs 50:50 目标、偏差、调仓建议（按整数股） |
| 持仓与参数 | 股数、QQQ 目标占比、偏差阈值（默认 5%）、定期再平衡间隔（默认 31 天）、上次再平衡日期 |
| 策略回测 | 拉取历史月度价格，对比 **QQQ 单持 / SCHD 单持 / 50:50 不再平衡 / 50:50 月度再平衡** 的净值曲线、年化收益、波动与最大回撤 |
| 再平衡记录 | 每次调仓的时间、股数、金额与备注，可导出 CSV |
| 提醒与设置 | 自动刷新间隔、每日提醒时间、开机自启、数据文件夹 |
| 策略原理 | 为什么再平衡能「无中生有」，以及必须知道的风险 |

### 提醒规则（满足其一即弹窗）

1. 距上次再平衡 ≥ 定期间隔（默认 31 天）；
2. 目标偏差 ≥ 阈值（默认 5%，即 55:45 触发）。

抑制规则：未启用提醒 / 未到每日提醒时间 / 当天已提醒 / 处于「3 天后再提醒」期间。
弹窗只提示、**不自动交易**，确认后可一键记录本次再平衡（自动回写持仓与日期）。

### 数据与多用户

- 数据保存在 `buddy/data/state.json`，首次运行会自动迁移旧版 `rebalance_state.json` 的持仓。
- 侧栏可**新建 / 改名 / 删除**多个用户组合（如 本人 / 家人 / 测试仓），各自独立保存股数、参数与记录。

### 价格来源

- 主：Yahoo Finance（含近一月走势迷你图）
- 备：新浪财经（网络不通时自动切换；仍失败可点右上角「手动价格」）

### 文件结构

```
buddy/
├─ launch.bat      ← 双击启动
├─ main.py         ← 入口（含错误日志 buddy/data/error.log）
├─ config.py       配置与路径
├─ store.py        多用户档案 + 记录持久化
├─ prices.py       行情获取（Yahoo / 新浪）
├─ strategy.py     再平衡计算 + 回测
├─ reminders.py    提醒判定
├─ theme.py        浅色主题
├─ widgets.py      界面组件（卡片/配置条/折线图）
└─ ui_app.py       主窗口
```

### 免责声明

本工具仅为个人理财辅助，不构成投资建议。两资产同时下跌时组合仍会亏损；
再平衡频率过高会被手续费与税侵蚀。历史回测不代表未来收益。

---

<a id="english"></a>

## English

A desktop tool built on `stragy.md` (Cover's growth-optimal portfolio theory):
**automatic price fetching + scheduled reminders + a graphical interface** that helps you keep a disciplined 50:50 rebalance.

### Quick start

Double-click **`launch.bat`** to start. No third-party libraries are required — Python's standard library is enough.

> Requirement: Python 3.10+ installed (with tkinter). The script locates `pythonw.exe` automatically.

### Features

| Page | Description |
| --- | --- |
| Dashboard | Live QQQ / SCHD prices (red = up, green = down, Chinese convention), total portfolio value, current allocation vs. the 50:50 target, deviation, and a trade suggestion rounded to whole shares |
| Holdings & Parameters | Share counts, QQQ target weight, deviation threshold (default 5%), rebalance interval (default 31 days), date of the last rebalance |
| Backtest | Downloads monthly history and compares **QQQ only / SCHD only / 50:50 buy-and-hold / 50:50 monthly rebalance** — equity curves, annualized return, volatility and maximum drawdown |
| Rebalance Log | Date, shares, amount and notes for every rebalance; exportable to CSV |
| Reminders & Settings | Auto-refresh interval, daily reminder time, launch at startup, data folder |
| Strategy Explained | Why rebalancing can create value "out of thin air", plus the risks you must know |

### Reminder rules (a popup appears if either is true)

1. Days since the last rebalance ≥ the interval (default 31 days);
2. Deviation from target ≥ the threshold (default 5%, i.e. triggered at 55:45).

Suppression: reminders disabled / before the daily reminder time / already notified today / currently in a "remind me in 3 days" period.
The popup only notifies — it **never trades automatically**. After confirming, you can log the rebalance in one click (holdings and date are written back automatically).

### Data & multiple users

- Data is stored in `buddy/data/state.json`. On first run, holdings from the legacy `rebalance_state.json` are migrated automatically.
- The sidebar lets you **create / rename / delete** multiple portfolios (e.g. Self / Family / Test account), each with its own shares, parameters and log.

### Price sources

- Primary: Yahoo Finance (includes a one-month sparkline)
- Fallback: Sina Finance (switches over automatically when the network fails; if both fail, click "Manual price" in the top-right corner)

### Project layout

```
buddy/
├─ launch.bat      ← double-click to start
├─ main.py         ← entry point (error log: buddy/data/error.log)
├─ config.py       configuration and paths
├─ store.py        multi-user profiles + log persistence
├─ prices.py       market data (Yahoo / Sina)
├─ strategy.py     rebalance math + backtest
├─ reminders.py    reminder decision logic
├─ theme.py        light theme
├─ widgets.py      UI components (cards / allocation bar / line chart)
└─ ui_app.py       main window
```

### Disclaimer

This tool is a personal finance aid only and does not constitute investment advice. A portfolio still loses money when both assets fall;
rebalancing too often is eroded by fees and taxes. Past backtests do not guarantee future returns.

---

<a id="日本語"></a>

## 日本語

`stragy.md`（Cover の成長最適ポートフォリオ理論）に基づくデスクトップツールです。
**価格の自動取得 ＋ 定期リマインダー ＋ ウィンドウ画面での操作**により、「50:50 の規律あるリバランス」を実行できます。

### クイックスタート

**`launch.bat`** をダブルクリックするだけで起動します（サードパーティ製ライブラリは不要、Python 標準ライブラリのみで動作します）。

> 必要条件：Python 3.10 以上（tkinter 同梱）がインストールされていること。スクリプトが `pythonw.exe` を自動的に探します。

### 機能一覧

| 画面 | 内容 |
| --- | --- |
| ダッシュボード | QQQ / SCHD のリアルタイム価格（上昇＝赤、下落＝緑／中国の慣習）、ポートフォリオ総額、現在の比率と 50:50 目標との比較、乖離率、売買提案（株数は整数に丸め） |
| 保有株とパラメータ | 保有株数、QQQ の目標比率、乖離しきい値（既定 5%）、定期リバランス間隔（既定 31 日）、前回リバランス日 |
| バックテスト | 月次ヒストリカルデータを取得し、**QQQ 単独 / SCHD 単独 / 50:50 リバランスなし / 50:50 毎月リバランス** を比較（純資産曲線、年率リターン、ボラティリティ、最大ドローダウン） |
| リバランス履歴 | 各リバランスの日時・株数・金額・メモ。CSV 書き出し可能 |
| リマインダーと設定 | 自動更新間隔、毎日の通知時刻、スタートアップ登録、データフォルダー |
| 戦略の考え方 | なぜリバランスが「無から価値を生む」のか、そして必ず知っておくべきリスク |

### リマインダーの条件（いずれかを満たすとポップアップ）

1. 前回リバランスからの経過日数 ≧ 設定間隔（既定 31 日）
2. 目標比率からの乖離 ≧ しきい値（既定 5%、つまり 55:45 で発動）

抑止条件：リマインダー無効 / 毎日の通知時刻前 / 当日通知済み / 「3 日後に再通知」期間中。
ポップアップは通知のみで、**自動売買は行いません**。確認後、ワンクリックで今回のリバランスを記録できます（保有株数と日付は自動で更新されます）。

### データとマルチユーザー

- データは `buddy/data/state.json` に保存されます。初回起動時に旧版 `rebalance_state.json` の保有情報を自動移行します。
- サイドバーで複数のポートフォリオを**作成 / 名前変更 / 削除**できます（例：本人 / 家族 / テスト口座）。それぞれ株数・パラメータ・履歴を独立して保持します。

### 価格データの取得元

- メイン：Yahoo Finance（直近 1 か月のミニチャート付き）
- サブ：新浪財経（Sina Finance／通信失敗時に自動切り替え。両方失敗した場合は右上の「手動価格」をクリック）

### ファイル構成

```
buddy/
├─ launch.bat      ← ダブルクリックで起動
├─ main.py         ← エントリーポイント（エラーログ: buddy/data/error.log）
├─ config.py       設定とパス
├─ store.py        マルチユーザープロファイル＋履歴の保存
├─ prices.py       相場データ取得（Yahoo / Sina）
├─ strategy.py     リバランス計算＋バックテスト
├─ reminders.py    リマインダー判定
├─ theme.py        ライトテーマ
├─ widgets.py      UI 部品（カード／比率バー／折れ線グラフ）
└─ ui_app.py       メインウィンドウ
```

### 免責事項

本ツールは個人の資産管理を補助するものであり、投資助言ではありません。2 つの資産が同時に下落すればポートフォリオは損失を出します。
リバランスの頻度が高すぎると手数料と税金に侵食されます。過去のバックテストは将来のリターンを保証するものではありません。

---

<a id="español"></a>

## Español

Herramienta de escritorio basada en `stragy.md` (teoría de la cartera de crecimiento óptimo de Cover):
**obtención automática de precios + recordatorios programados + interfaz gráfica** que le ayuda a mantener un rebalanceo disciplinado 50:50.

### Inicio rápido

Haga doble clic en **`launch.bat`** para iniciar. No requiere librerías de terceros: basta con la biblioteca estándar de Python.

> Requisito: Python 3.10 o superior instalado (con tkinter). El script localiza `pythonw.exe` automáticamente.

### Funciones

| Página | Descripción |
| --- | --- |
| Panel | Precios en vivo de QQQ / SCHD (rojo = sube, verde = baja, convención china), valor total de la cartera, asignación actual frente al objetivo 50:50, desviación y sugerencia de operación redondeada a acciones enteras |
| Posiciones y parámetros | Número de acciones, peso objetivo de QQQ, umbral de desviación (5% por defecto), intervalo de rebalanceo (31 días por defecto) y fecha del último rebalanceo |
| Backtest | Descarga el histórico mensual y compara **solo QQQ / solo SCHD / 50:50 sin rebalanceo / 50:50 con rebalanceo mensual**: curvas de capital, rentabilidad anualizada, volatilidad y máxima caída |
| Historial de rebalanceos | Fecha, acciones, importe y notas de cada rebalanceo; exportable a CSV |
| Recordatorios y ajustes | Intervalo de actualización automática, hora del recordatorio diario, inicio automático, carpeta de datos |
| Cómo funciona la estrategia | Por qué el rebalanceo puede crear valor «de la nada» y los riesgos que debe conocer |

### Reglas de recordatorio (aparece un aviso si se cumple alguna)

1. Días desde el último rebalanceo ≥ el intervalo configurado (31 días por defecto);
2. Desviación respecto al objetivo ≥ el umbral (5% por defecto, es decir, se activa en 55:45).

Supresión: recordatorios desactivados / antes de la hora diaria / ya avisado hoy / en periodo de «recordar en 3 días».
El aviso solo informa y **nunca opera automáticamente**. Tras confirmar, puede registrar el rebalanceo con un clic (las posiciones y la fecha se actualizan solas).

### Datos y multiusuario

- Los datos se guardan en `buddy/data/state.json`. En la primera ejecución se migran automáticamente las posiciones del antiguo `rebalance_state.json`.
- La barra lateral permite **crear / renombrar / eliminar** varias carteras (p. ej. Personal / Familia / Cuenta de prueba), cada una con sus propias acciones, parámetros e historial.

### Fuentes de precios

- Principal: Yahoo Finance (incluye minigráfico del último mes)
- Alternativa: Sina Finance (cambia automáticamente si falla la red; si ambas fallan, pulse «Precio manual» arriba a la derecha)

### Estructura del proyecto

```
buddy/
├─ launch.bat      ← doble clic para iniciar
├─ main.py         ← punto de entrada (registro de errores: buddy/data/error.log)
├─ config.py       configuración y rutas
├─ store.py        perfiles multiusuario + persistencia del historial
├─ prices.py       datos de mercado (Yahoo / Sina)
├─ strategy.py     cálculo de rebalanceo + backtest
├─ reminders.py    lógica de decisión de recordatorios
├─ theme.py        tema claro
├─ widgets.py      componentes de interfaz (tarjetas / barra de asignación / gráfico)
└─ ui_app.py       ventana principal
```

### Aviso legal

Esta herramienta es solo una ayuda para las finanzas personales y no constituye asesoramiento de inversión. La cartera seguirá perdiendo dinero si ambos activos caen;
rebalancear con demasiada frecuencia se ve erosionado por comisiones e impuestos. Los backtests pasados no garantizan rentabilidades futuras.
