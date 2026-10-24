# docling-project/DeskForge-1M

Use (SPEC): grounder + ELEMENT

- Revision: `7a3923760e65974825aba6f21073e4e146a361c5`
- Total size: 1143.06 GB in 1203 files
- License: card tag: `mit`; LICENSE file: MIT License
- Platform split: Linux desktop (AT-SPI roles, GNOME/MATE apps such as homebank, pluma, gnome-system-monitor); synthetic scenes with occlusion. Not macOS.
- Approx. tokens per converted example (Qwen3.5 tokenizer): ~285 tokens per instruction-index row; per observation the leaf.json element list is the ELEMENT input (n_elements varies; not measured since the tars were not downloaded)

## Row counts (parquet footers)

| files | rows |
|---|---|
| `checksums/shard_stats` | 1,151 |
| `demo/preview` | 5,283 |
| `index/episodes/test_app` | 6,553 |
| `index/episodes/test_id` | 2,524 |
| `index/episodes/test_resolution` | 8,535 |
| `index/episodes/test_theme` | 5,586 |
| `index/episodes/train` | 111,249 |
| `index/episodes/val` | 1,284 |
| `index/instructions/test_app` | 22,729 |
| `index/instructions/test_id` | 12,589 |
| `index/instructions/test_resolution` | 43,210 |
| `index/instructions/test_theme` | 27,175 |
| `index/instructions/train` | 551,651 |
| `index/instructions/val` | 6,281 |
| `index/observations/test_app` | 43,206 |
| `index/observations/test_id` | 22,550 |
| `index/observations/test_resolution` | 79,212 |
| `index/observations/test_theme` | 51,627 |
| `index/observations/train` | 999,494 |
| `index/observations/val` | 11,279 |
| `index/scenes` | 323,731 |
| `index/shard_members` | 4,829,472 |
| `index/transitions/test_app` | 32,848 |
| `index/transitions/test_id` | 17,383 |
| `index/transitions/test_resolution` | 58,792 |
| `index/transitions/test_theme` | 38,671 |
| `index/transitions/train` | 760,850 |
| `index/transitions/val` | 8,667 |

## Schema (`index/instructions/val.parquet`)

```
transition_id: string
split: string
before_key: string
after_key: string
target_uid: string
action_type: string
action_point_px: list<element: int32>
  child 0, element: int32
action_target_bbox_px: list<element: int32>
  child 0, element: int32
primary_style: string
primary_instruction: string
instruction_variants: list<element: struct<style: string, text: string>>
  child 0, element: struct<style: string, text: string>
      child 0, style: string
      child 1, text: string
referring_expression: string
```

## Notes

Payload is 1,157 uncompressed tars (1.14 TB, ~1 GB each, 4 members per observation: png, leaf.json, screentag.txt, record.json), plus small parquet indexes. Row counts from indexes: instructions train 2,423,244 / val 27,511 / test_app 105,336 / test_id 55,046 / test_resolution 189,749 / test_theme 123,059; scenes 323,731. Instruction rows: transition_id, before/after keys, target_uid, action_type, action_point_px, action_target_bbox_px, primary_instruction, instruction_variants[{style,text}], referring_expression. `index/shard_members.parquet` gives per-member byte offsets, so single leaf.json members can be range-read without downloading a whole tar.

## 3 raw examples (long strings and binary truncated)

```json
{
 "transition_id": "shard-0001__ep__1877e2bca05a2e9f__t01",
 "split": "val",
 "before_key": "shard-0001__scene-1877e2bca05a2e9f-step00",
 "after_key": "shard-0001__scene-1877e2bca05a2e9f-step01",
 "target_uid": "ead5cb8165462425",
 "action_type": "click",
 "action_point_px": [
  158,
  137
 ],
 "action_target_bbox_px": [
  134,
  113,
  182,
  161
 ],
 "primary_style": "standard",
 "primary_instruction": "Switch the left sidebar of Visual Studio Code to the Explorer view.",
 "instruction_variants": [
  {
   "style": "standard",
   "text": "Switch the left sidebar of Visual Studio Code to the Explorer view."
  },
  {
   "style": "detailed_contextual",
   "text": "Switch the left sidebar of Visual Studio Code from the Source Control view to the Explorer view to display the project files."
  }
 ],
 "referring_expression": "the Explorer icon on the left sidebar of Visual Studio Code"
}
```

```json
{
 "transition_id": "shard-0003__ep__4841e2a2764d0b7e__t01",
 "split": "val",
 "before_key": "shard-0003__scene-4841e2a2764d0b7e-step00",
 "after_key": "shard-0003__scene-4841e2a2764d0b7e-step01",
 "target_uid": "80b06ebf5db974e2",
 "action_type": "click",
 "action_point_px": [
  472,
  618
 ],
 "action_target_bbox_px": [
  409,
  604,
  536,
  632
 ],
 "primary_style": "standard",
 "primary_instruction": "Enter the number one into the calculator.",
 "instruction_variants": [
  {
   "style": "standard",
   "text": "Enter the number one into the calculator."
  },
  {
   "style": "detailed_contextual",
   "text": "In the calculator window, input the digit one using the numeric keypad."
  }
 ],
 "referring_expression": "the button labeled 1 in the calculator's numeric keypad"
}
```

```json
{
 "transition_id": "shard-0003__ep__bd182221cc4f5be0__t01",
 "split": "val",
 "before_key": "shard-0003__scene-bd182221cc4f5be0-step00",
 "after_key": "shard-0003__scene-bd182221cc4f5be0-step01",
 "target_uid": "de3312325a7044de",
 "action_type": "click",
 "action_point_px": [
  769,
  158
 ],
 "action_target_bbox_px": [
  602,
  147,
  936,
  169
 ],
 "primary_style": "standard",
 "primary_instruction": "Switch focus to the Visual Studio Code window.",
 "instruction_variants": [
  {
   "style": "standard",
   "text": "Switch focus to the Visual Studio Code window."
  },
  {
   "style": "detailed_contextual",
   "text": "Activate the Visual Studio Code window that is currently behind the Archive Manager window."
  }
 ],
 "referring_expression": "the Visual Studio Code window displaying the main.py file"
}
```
