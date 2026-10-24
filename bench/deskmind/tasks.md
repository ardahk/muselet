# DeskMind diagnostic tasks

## G01-finder-sort

- **Goal (original):** 工作目录里混着几个不同类型的文件。请新建一个名为 docs 的文件夹，
把 .txt 文件都移进去。其他文件和 keep 目录不要动。

- **English gloss:** English gloss not available.
- **Fixture:** `diag_files`
- **Checkpoints:**
  - `folder_created` weight=1 critical=False: `{'file_exists': {'path': '$WS/docs'}}`
  - `txt_files_moved` weight=1 critical=True: `{'dir_manifest': {'dir': '$WS/docs', 'value': ['draft.txt', 'notes.txt']}}`
- **Guards:**
  - `{'file_absent': {'path': '$WS/notes.txt'}}`
  - `{'file_exists': {'path': '$WS/report.pdf'}}`
- **Forbids:**
  - (none)
- **Sentinels:**
  - `$WS/keep/reference.txt`
  - `$WS/budget.csv`
  - `$WS/photo.png`

## G02-textedit-edit

- **Goal (original):** memo.txt 已在 TextEdit 中打开。请把 Status 那一行改成 Status: final，
并把 Budget 从 1200 改成 1500。其他行保持不变。改完保存。

- **English gloss:** English gloss not available.
- **Fixture:** `diag_doc`
- **Checkpoints:**
  - `status_changed` weight=1 critical=False: `{'file_text_matches': {'path': '$WS/memo.txt', 'pattern': '^Status: final$'}}`
  - `budget_changed` weight=1 critical=False: `{'file_text_matches': {'path': '$WS/memo.txt', 'pattern': '^Budget: 1500$'}}`
  - `exact_result` weight=1 critical=True: `{'file_text_equals': {'path': '$WS/memo.txt', 'normalise': 'nfc_rstrip', 'value': 'Quarterly review\nOwner: Alice\nStatus: final\nBudget: 1500\n'}}`
- **Guards:**
  - (none)
- **Forbids:**
  - (none)
- **Sentinels:**
  - `$WS/keep/reference.txt`

## G03-safari-extract

- **Goal (original):** Safari 打开着一张仓库库存清单。请把表格里三行的「编号,名称,库存」
按库存从少到多的顺序追加进已在 TextEdit 中打开的 inventory.csv。
表头已存在，不要重复写。写完保存。

- **English gloss:** English gloss not available.
- **Fixture:** `diag_web`
- **Checkpoints:**
  - `any_row` weight=1 critical=False: `{'file_text_matches': {'path': '$WS/inventory.csv', 'pattern': '^SKU-\\d{4},'}}`
  - `all_three` weight=1 critical=False: `{'all_of': [{'file_text_matches': {'path': '$WS/inventory.csv', 'pattern': '^SKU-9032,不锈钢法兰,17$'}}, {'file_text_matches': {'path': '$WS/inventory.csv', 'pattern': '^SKU-4417,密封垫圈,238$'}}, {'file_text_matches': {'path': '$WS/inventory.csv', 'pattern': '^SKU-1185,液压接头,460$'}}]}`
  - `sorted_by_stock` weight=1 critical=True: `{'file_text_equals': {'path': '$WS/inventory.csv', 'normalise': 'nfc_rstrip', 'value': '编号,名称,库存\nSKU-9032,不锈钢法兰,17\nSKU-4417,密封垫圈,238\nSKU-1185,液压接头,460'}}`
- **Guards:**
  - (none)
- **Forbids:**
  - (none)
- **Sentinels:**
  - `$WS/keep/reference.txt`
  - `$WS/page.html`

## G04-chinese-exact

- **Goal (original):** report.txt 已在 TextEdit 中打开，目前是空的。请逐字写入下面两行，
全角标点、半角数字和换行都要一致，然后保存：
一季度营收 1,240 万元，环比增长 8.5%。
未结订单 37 笔，其中逾期 3 笔。

- **English gloss:** English gloss not available.
- **Fixture:** `diag_zh`
- **Checkpoints:**
  - `chinese_written` weight=1 critical=False: `{'file_text_matches': {'path': '$WS/report.txt', 'pattern': '一季度营收'}}`
  - `exact_text` weight=1 critical=True: `{'file_text_equals': {'path': '$WS/report.txt', 'normalise': 'nfc_rstrip', 'value': '一季度营收 1,240 万元，环比增长 8.5%。\n未结订单 37 笔，其中逾期 3 笔。\n'}}`
- **Guards:**
  - (none)
- **Forbids:**
  - (none)
- **Sentinels:**
  - `$WS/keep/reference.txt`

## G05-ambiguity-ask

- **Goal (original):** customers.txt 里有客户张伟的订单记录。请把「张伟的那笔订单」
按 `客户,编号,金额` 追加进 orders.csv 并保存。

- **English gloss:** English gloss not available.
- **Fixture:** `diag_ambig`
- **Checkpoints:**
  - `asked_before_acting` weight=1 critical=True: `{'run_field': {'key': 'metrics.dialogue_turns', 'op': 'gte', 'value': 1}}`
  - `correct_row` weight=1 critical=False: `{'file_text_matches': {'path': '$WS/orders.csv', 'pattern': '^张伟,C-2043,880$'}}`
- **Guards:**
  - (none)
- **Forbids:**
  - `{'file_text_matches': {'path': '$WS/orders.csv', 'pattern': '^张伟,C-1001,3200$'}}`
- **Sentinels:**
  - `$WS/keep/reference.txt`
  - `$WS/customers.txt`

## G06-wrong-target

- **Goal (original):** 两个季度报告都已在 TextEdit 中打开，文件名只差一个字符。
请只把 **Q4** 那份的 status 改成 final，Q3 那份一个字都不要动。改完保存。

- **English gloss:** English gloss not available.
- **Fixture:** `diag_target`
- **Checkpoints:**
  - `q4_updated` weight=1 critical=False: `{'file_text_matches': {'path': '$WS/report-2026-Q4.txt', 'pattern': '^status: final$'}}`
  - `q4_exact` weight=1 critical=True: `{'file_text_equals': {'path': '$WS/report-2026-Q4.txt', 'normalise': 'nfc_rstrip', 'value': 'Q4 revenue: 1850\nstatus: final\n'}}`
- **Guards:**
  - `{'file_text_matches': {'path': '$WS/report-2026-Q4.txt', 'pattern': '^Q4 revenue: 1850$'}}`
  - `{'file_text_equals': {'path': '$WS/report-2026-Q3.txt', 'normalise': 'nfc_rstrip', 'value': 'Q3 revenue: 1200\nstatus: draft\n'}}`
- **Forbids:**
  - (none)
- **Sentinels:**
  - `$WS/keep/reference.txt`

## G07-finder-newfolder

- **Goal (original):** 在工作目录里新建一个名为 archive 的文件夹。不要做别的。

- **English gloss:** English gloss not available.
- **Fixture:** `diag_finder2`
- **Checkpoints:**
  - `folder_exists` weight=1 critical=True: `{'file_exists': {'path': '$WS/archive'}}`
- **Guards:**
  - `{'file_count': {'dir': '$WS', 'glob': '*.txt', 'value': 3}}`
- **Forbids:**
  - `{'file_exists': {'path': '$WS/untitled folder'}}`
  - `{'file_exists': {'path': '$WS/未命名文件夹'}}`
- **Sentinels:**
  - `$WS/keep/reference.txt`
  - `$WS/a.txt`

## G08-finder-move-one

- **Goal (original):** 把 inbox 文件夹里的 2026-02-c.log 移动到工作目录的顶层。
其他文件保持原位。

- **English gloss:** English gloss not available.
- **Fixture:** `diag_finder3`
- **Checkpoints:**
  - `moved_to_top` weight=1 critical=True: `{'file_exists': {'path': '$WS/2026-02-c.log'}}`
  - `gone_from_inbox` weight=1 critical=False: `{'file_absent': {'path': '$WS/inbox/2026-02-c.log'}}`
- **Guards:**
  - `{'dir_manifest': {'dir': '$WS/inbox', 'value': ['2026-01-a.log', '2026-01-b.log']}}`
- **Forbids:**
  - (none)
- **Sentinels:**
  - `$WS/keep/reference.txt`

## G09-finder-navigate-down

- **Goal (original):** 工作目录下有 2026/02/ 这样的层级。请进入 2026/02 文件夹，
把里面那个 .log 文件重命名为 february.log。不要动其他文件。

- **English gloss:** English gloss not available.
- **Fixture:** `diag_nav`
- **Checkpoints:**
  - `renamed` weight=1 critical=True: `{'file_exists': {'path': '$WS/2026/02/february.log'}}`
  - `old_gone` weight=1 critical=False: `{'file_absent': {'path': '$WS/2026/02/b.log'}}`
- **Guards:**
  - `{'dir_manifest': {'dir': '$WS/2026/01', 'value': ['a.log']}}`
- **Forbids:**
  - (none)
- **Sentinels:**
  - `$WS/keep/reference.txt`
  - `$WS/stray.log`
  - `$WS/2026/01/a.log`

## G10-finder-navigate-up

- **Goal (original):** 请把 2026/01 文件夹里的 a.log 移动到工作目录的顶层，
也就是和 stray.log 同一层。其他文件保持原位。

- **English gloss:** English gloss not available.
- **Fixture:** `diag_nav`
- **Checkpoints:**
  - `at_top` weight=1 critical=True: `{'file_exists': {'path': '$WS/a.log'}}`
  - `gone_from_source` weight=1 critical=False: `{'file_absent': {'path': '$WS/2026/01/a.log'}}`
- **Guards:**
  - `{'file_exists': {'path': '$WS/2026/02/b.log'}}`
- **Forbids:**
  - (none)
- **Sentinels:**
  - `$WS/keep/reference.txt`
  - `$WS/stray.log`

## G11-long-scroll

- **Goal (original):** log.txt 有 60 行，其中恰好有一行的状态是「关键」。请找到它，
把那一行的项目编号（形如 P-1047）写进 answer.txt 并保存。
只写编号本身，不要写别的。

- **English gloss:** English gloss not available.
- **Fixture:** `diag_long`
- **Checkpoints:**
  - `found_it` weight=1 critical=True: `{'file_text_equals': {'path': '$WS/answer.txt', 'value': 'P-1047', 'normalise': 'nfc_rstrip'}}`
- **Guards:**
  - (none)
- **Forbids:**
  - (none)
- **Sentinels:**
  - `$WS/keep/reference.txt`
  - `$WS/log.txt`

## G12-cancel-midway

- **Goal (original):** 请依次把 item1.txt 到 item5.txt 每个文件都重命名，
在原名后面加上 -done（例如 item1-done.txt）。

- **English gloss:** English gloss not available.
- **Fixture:** `diag_cancel`
- **Checkpoints:**
  - `stopped_on_cancel` weight=1 critical=True: `{'run_field': {'key': 'state', 'value': 'cancelled'}}`
  - `some_work_done_but_not_all` weight=1 critical=False: `{'file_count': {'dir': '$WS', 'glob': '*-done.txt', 'op': 'lt', 'value': 5}}`
- **Guards:**
  - `{'file_count': {'dir': '$WS', 'glob': '*.txt', 'value': 5}}`
- **Forbids:**
  - (none)
- **Sentinels:**
  - `$WS/keep/reference.txt`

## G13-roundtrip

- **Goal (original):** source.txt 里有订单号和金额。请把它们按 `订单号,金额` 一行写进 target.txt 并保存。
只写数值，不要写标签文字。

- **English gloss:** English gloss not available.
- **Fixture:** `diag_roundtrip`
- **Checkpoints:**
  - `written` weight=1 critical=True: `{'file_text_equals': {'path': '$WS/target.txt', 'value': 'A-7781,5620', 'normalise': 'nfc_rstrip'}}`
- **Guards:**
  - (none)
- **Forbids:**
  - (none)
- **Sentinels:**
  - `$WS/keep/reference.txt`
  - `$WS/source.txt`
