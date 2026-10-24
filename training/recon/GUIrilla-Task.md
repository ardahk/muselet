# macpaw-research/GUIrilla-Task

Use (SPEC): ELEMENT decisions (macOS AX)

- Revision: `ec4853a26f96e1c8adcc31670054f58a67a87297`
- Total size: 46.88 GB in 104 files
- License: card tag: `cc-by-nc-4.0`; LICENSE file: Attribution-NonCommercial 4.0 International
- Platform split: macOS only (app_name = bundle id, e.g. com.tencent.Foxmail)
- Approx. tokens per converted example (Qwen3.5 tokenizer): ~413 tokens for one example converted to the AGENTS.md observation format (32 AX nodes from the `accessibility` JSON tree + task + action); raw `accessibility` JSON is ~11K chars

## Row counts (parquet footers)

| files | rows |
|---|---|
| `data/test` | 1,565 |
| `data/train` | 25,606 |

## Schema (`data/train-00010-of-00096.parquet`)

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

Each row = one screen + one task + one ground-truth action (`left click (x, y)` / `type ...`). `element_data` identifies the target element, so ELEMENT labels can be read from the AX tree without images. Parquet shards embed full screenshots (`image`, ~2 MB each), so a text-only pass still downloads 46.9 GB unless columns are projected (parquet column projection over HTTP range reads avoids the image bytes). Has a `test` split (1,565 rows): treat as held-out alongside GUIrilla-Gold.

## 3 raw examples (long strings and binary truncated)

```json
{
 "screen_id": 6490,
 "app_name": "com.tencent.Foxmail",
 "task": "Use your IMAP password as SuperSecure123!",
 "raw_task": "secure text field []",
 "action": "type SuperSecure123!",
 "image": {
  "bytes": "<2020923 bytes>",
  "path": "image.png"
 },
 "image_cropped": {
  "bytes": "<98679 bytes>",
  "path": "image_cropped.png"
 },
 "accessibility": "{\"id\": \"b62cf86aaca9ec3b779012d0c2620873\", \"name\": \"Setup_Account\", \"role\": \"AXWindow\", \"description\": null, \"role_description\": \"standard window\", \"value\": null, \"absolute_position\": \"485.00;130.00\", \"position\": \"0.00;0.00\", \"size\": \"470;508\", \"enabled\": false, \"bbox\": [0, 0, 470, 508], \"visible_bbox\": [0, 0, 470, 508], \"children\": [{\"id\": \"962074694be48bb318f30a4c3a49a479\", \"name\": \"Continue\", \"role\": \"AXButton\", \"description\": null, \"role_description\": \"button\", \"value\": null, \"absolute_position\": \"865.00;602.00\", \"position\": \"380.00;472.00\", \"size\": \"82;26\", \"enabled\": true, \"bbox\": [380, ... <11289 chars>",
 "scaling_factor": 2.0,
 "element_data": "{'original_id': '2e80f5880bda86b6c656c07c7a671f52', 'name': 'empty-name-AXTextField', 'role': 'AXTextField', 'description': None, 'role_description': 'secure text field', 'value': '\\uf79a\\uf79a\\uf79a\\uf79a\\uf79a\\uf79a\\uf79a\\uf79a\\uf79a\\uf79a\\uf79a', 'absolute_position': '647.00;299.00', 'position': '162.00;169.00', 'size': '266;24', 'bbox': [162, 169, 428, 193], 'visible_bbox': [162, 
... (truncated)
```

```json
{
 "screen_id": 2202,
 "app_name": "com.dekorra.EazyDraw",
 "task": "Switch to grid view in the canvas area",
 "raw_task": "button",
 "action": "left click (487.0, 66.0)",
 "image": {
  "bytes": "<254662 bytes>",
  "path": "image.png"
 },
 "image_cropped": {
  "bytes": "<62343 bytes>",
  "path": "image_cropped.png"
 },
 "accessibility": "{\"id\": \"67b7b0ddda60d73979ec293ac0cb8c90\", \"name\": \"Untitled\", \"role\": \"AXWindow\", \"description\": null, \"role_description\": \"standard window\", \"value\": null, \"absolute_position\": \"108.00;39.00\", \"position\": \"0.00;0.00\", \"size\": \"746;524\", \"enabled\": false, \"bbox\": [0, 0, 746, 524], \"visible_bbox\": [0, 0, 746, 524], \"children\": [{\"id\": \"39fe5a488717412e721dcea06c14b11f\", \"name\": \"empty-name-AXPopUpButton\", \"role\": \"AXPopUpButton\", \"description\": null, \"role_description\": \"pop up button\", \"value\": \"Add Layer\", \"absolute_position\": \"184.00;547.00\", \"position\": \"76.00;508.00\", \"size\": \"129;18\", \"e... <39564 chars>",
 "scaling_factor": 1.0,
 "element_data": "{'original_id': '6623f460ecebeabf83b5cbf244e40bdf', 'name': 'empty-name-AXButton', 'role': 'AXButton', 'description': None, 'role_description': 'button', 'value': None, 'absolute_position': '584.00;96.00', 'position': '476.00;57.00', 'size': '22;18', 'bbox': [476, 57, 498, 75], 'visible_bbox': [476, 57, 496, 75], 'enabled': True, 'children': []}",
 "original_task": false,
 "task_category": "Navigation",
 "element_catego
... (truncated)
```

```json
{
 "screen_id": 2202,
 "app_name": "com.dekorra.EazyDraw",
 "task": "Enable grid snapping",
 "raw_task": "button",
 "action": "left click (466.0, 66.0)",
 "image": {
  "bytes": "<254662 bytes>",
  "path": "image.png"
 },
 "image_cropped": {
  "bytes": "<62343 bytes>",
  "path": "image_cropped.png"
 },
 "accessibility": "{\"id\": \"67b7b0ddda60d73979ec293ac0cb8c90\", \"name\": \"Untitled\", \"role\": \"AXWindow\", \"description\": null, \"role_description\": \"standard window\", \"value\": null, \"absolute_position\": \"108.00;39.00\", \"position\": \"0.00;0.00\", \"size\": \"746;524\", \"enabled\": false, \"bbox\": [0, 0, 746, 524], \"visible_bbox\": [0, 0, 746, 524], \"children\": [{\"id\": \"39fe5a488717412e721dcea06c14b11f\", \"name\": \"empty-name-AXPopUpButton\", \"role\": \"AXPopUpButton\", \"description\": null, \"role_description\": \"pop up button\", \"value\": \"Add Layer\", \"absolute_position\": \"184.00;547.00\", \"position\": \"76.00;508.00\", \"size\": \"129;18\", \"e... <39564 chars>",
 "scaling_factor": 1.0,
 "element_data": "{'original_id': '91adc91edf2c5dc3239b6f95c238b725', 'name': 'empty-name-AXButton', 'role': 'AXButton', 'description': None, 'role_description': 'button', 'value': None, 'absolute_position': '564.00;96.00', 'position': '456.00;57.00', 'size': '20;18', 'bbox': [456, 57, 476, 75], 'visible_bbox': [456, 57, 476, 75], 'enabled': False, 'children': []}",
 "original_task": false,
 "task_category": "Settings",
 "element_category": "Button"
}
```
