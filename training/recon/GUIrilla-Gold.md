# macpaw-research/GUIrilla-Gold

Use (SPEC): held-out eval only (never train)

- Revision: `bae08db45b0c8e789a4c41f4340ccfabc59206f0`
- Total size: 1.93 GB in 7 files
- License: card tag: `cc-by-nc-4.0`; LICENSE file: Attribution-NonCommercial 4.0 International
- Platform split: macOS only
- Approx. tokens per converted example (Qwen3.5 tokenizer): same format as GUIrilla-Task (~400-1,000 tokens converted, AX JSON 20K+ chars in the sampled row)

## Row counts (parquet footers)

| files | rows |
|---|---|
| `data/train` | 1,283 |

## Schema (`data/train-00001-of-00004.parquet`)

```
screen_id: int32
app_name: string
task: string
raw_task: string
action: string
image: struct<bytes: binary, path: string>
  child 0, bytes: binary
  child 1, path: string
image_cropped: struct<bytes: binary, path: string>
  child 0, bytes: binary
  child 1, path: string
accessibility: string
scaling_factor: float
element_data: string
original_task: bool
task_category: string
element_category: string
```

## Notes

Same schema as GUIrilla-Task. EVAL ONLY per AGENTS.md: dedupe GUIrilla-Task training rows against it (by `screen_id`/`app_name`+`task`) before Phase 2.

## 3 raw examples (long strings and binary truncated)

```json
{
 "screen_id": 1106,
 "app_name": "com.apple.stocks",
 "task": "View detailed information for Boeing Company stock",
 "raw_task": "The Boeing Company, BA [177,95, change, up 1,69 points]",
 "action": "left click (373.0, 458.5)",
 "image": {
  "bytes": "<1974072 bytes>",
  "path": null
 },
 "image_cropped": {
  "bytes": "<348221 bytes>",
  "path": null
 },
 "accessibility": "{\"id\": \"7512aa2e586c2f3a3029b401dc34dcc9\", \"name\": \"Business_News\", \"role\": \"AXWindow\", \"description\": null, \"role_description\": \"standard window\", \"value\": null, \"absolute_position\": \"208.00;34.00\", \"position\": \"0.00;0.00\", \"size\": \"1024;768\", \"enabled\": false, \"bbox\": [0, 0, 1024, 768], \"visible_bbox\": [0, 0, 1024, 768], \"children\": [{\"id\": \"1a55a5dec6f8fcc0e75355b61857a572\", \"name\": \"empty-name-AXButton\", \"role\": \"AXButton\", \"description\": null, \"role_description\": \"full screen button\", \"value\": null, \"absolute_position\": \"266.00;52.00\", \"position\": \"58.00;18.00\", \"size\": \"16;16\", \"enabled\"... <24498 chars>",
 "scaling_factor": 2.0,
 "element_data": "{\n    \"id\": \"eb1e94fa363ae871fcb46f85dae431fd\",\n    \"name\": \"empty-name-AXGenericElement\",\n    \"role\": \"AXGenericElement\",\n    \"description\": \"The Boeing Company, BA\",\n    \"role_description\": \"\",\n    \"value\": \"177,95, change, up 1,69 points\",\n    \"absolute_position\": \"218.00;428.00\",\n    \"position\": \"10.00;394.00\",\n    \"size\": \"310;61\",\n 
... (truncated)
```

```json
{
 "screen_id": 1334,
 "app_name": "com.bigmac.TodoTimeTracker",
 "task": "Edit a label",
 "raw_task": "button Edit_Label",
 "action": "left click (755.0, 145.0)",
 "image": {
  "bytes": "<65056 bytes>",
  "path": null
 },
 "image_cropped": {
  "bytes": "<30476 bytes>",
  "path": null
 },
 "accessibility": "{\"id\": \"652ddd8d6de0c3cc3739dd4ef7350fc3\", \"name\": \"TodoTimeTracker\", \"role\": \"AXWindow\", \"description\": null, \"role_description\": \"standard window\", \"value\": null, \"absolute_position\": \"216.00;25.00\", \"position\": \"0.00;0.00\", \"size\": \"690;1028\", \"enabled\": false, \"bbox\": \"\", \"visible_bbox\": \"\", \"children\": [{\"id\": \"dd5ad361235dcc41f7e38f5d8a655157\", \"name\": \"empty-name-AXScrollArea\", \"role\": \"AXScrollArea\", \"description\": null, \"role_description\": \"scroll area\", \"value\": null, \"absolute_position\": \"256.00;359.00\", \"position\": \"40.00;334.00\", \"size\": \"610;654\", \"enabled\": false, \"bbox\": \"\", \"v... <13354 chars>",
 "scaling_factor": 1.0,
 "element_data": "{\n    \"id\": \"acda58be980525017fcba220cfec590c\",\n    \"name\": \"Edit_Label\",\n    \"role\": \"AXButton\",\n    \"description\": null,\n    \"role_description\": \"button\",\n    \"value\": null,\n    \"absolute_position\": \"714.00;134.00\",\n    \"position\": \"498.00;109.00\",\n    \"size\": \"82;22\",\n    \"enabled\": true,\n    \"bbox\": [\n        498,\n        109,\n        580,\n        131\n    ],\n    \"visible_bbox\": [\n   
... (truncated)
```

```json
{
 "screen_id": 6111,
 "app_name": "com.shrek.winmailreader",
 "task": "Open the Jiumo e-book download website",
 "raw_task": "button Jiumo",
 "action": "left click (955.0, 641.0)",
 "image": {
  "bytes": "<195178 bytes>",
  "path": null
 },
 "image_cropped": {
  "bytes": "<37434 bytes>",
  "path": null
 },
 "accessibility": "{\"id\": \"06bdb5adf27789a4f6958cce0dea53ae\", \"name\": \"GM_CHM_Reader\", \"role\": \"AXWindow\", \"description\": null, \"role_description\": \"standard window\", \"value\": null, \"absolute_position\": \"413.00;96.00\", \"position\": \"0.00;0.00\", \"size\": \"950;830\", \"enabled\": false, \"bbox\": [0, 0, 950, 830], \"visible_bbox\": [0, 0, 950, 830], \"children\": [{\"id\": \"1f4b1f765123275cc2b6827877a5c510\", \"name\": \"empty-name-AXGroup\", \"role\": \"AXGroup\", \"description\": null, \"role_description\": \"group\", \"value\": null, \"absolute_position\": \"413.00;176.00\", \"position\": \"0.00;80.00\", \"size\": \"950;750\", \"enabled\": false, \"bbox\":... <15968 chars>",
 "scaling_factor": 1.0,
 "element_data": "{\n    \"id\": \"f16f84f53e63c8e17afd88cc88391b62\",\n    \"name\": \"Jiumo\",\n    \"role\": \"AXButton\",\n    \"description\": null,\n    \"role_description\": \"button\",\n    \"value\": null,\n    \"absolute_position\": \"924.00;632.50\",\n    \"position\": \"511.00;536.50\",\n    \"size\": \"62;17\",\n    \"enabled\": true,\n    \"bbox\": [\n        511,\n        536,\n        573,\n        553\n    ],\n    \"visible_bbox\":
... (truncated)
```
