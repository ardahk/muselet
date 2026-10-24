# markov-ai/computer-use

Use (SPEC): planner (AX + screenshots, OSWorld)

- Revision: `de58c88b4b33dd03fa4d5d0f490748f576bd37b3`
- Total size: 2.12 GB in 331 files
- License: card tag: `apache-2.0`; LICENSE file: none
- Platform split: Linux (OSWorld Ubuntu VM): chrome, gimp, libreoffice_*, thunderbird, vlc, vs_code, os, multi_apps
- Approx. tokens per converted example (Qwen3.5 tokenizer): ~4.4K tokens per step for the linearized AX tree; ~280 tokens per model response

## Row counts (parquet footers)

| files | rows |
|---|---|
| `data/train` | 313 |

## Schema (`data/train-00005-of-00016.parquet`)

```
task_id: string
domain: string
instruction: string
score: float
num_steps: int32
actions: list<element: string>
  child 0, element: string
responses: list<element: string>
  child 0, element: string
screenshots: list<element: struct<bytes: binary, path: string>>
  child 0, element: struct<bytes: binary, path: string>
      child 0, bytes: binary
      child 1, path: string
accessibility_trees: list<element: string>
  child 0, element: string
exe_statuses: list<element: string>
  child 0, element: string
exe_outputs: list<element: string>
  child 0, element: string
exe_errors: list<element: string>
  child 0, element: string
rewards: list<element: float>
  child 0, element: float
dones: list<element: bool>
  child 0, element: bool
recording_path: string
```

## Notes

Parquet footers give 313 rows but the README says 160 rows / 1,378 steps, so the card is stale or rows are duplicated. One row = whole trajectory, with parallel per-step lists (actions, responses, screenshots, accessibility_trees, rewards). Actions are python `osworld_tools` calls (e.g. `ImpressTools.duplicate_slide(...)`), not GUI actions, which only partly fit our action DSL. All rows have score 1.0 (successes only). Also includes 313 mp4 recordings (1.1 GB); not downloaded.

## 3 raw examples (long strings and binary truncated)

```json
{
 "task_id": "9ec204e4-f0a3-42f8-8458-b772a6797cab",
 "domain": "libreoffice_impress",
 "instruction": "Please duplicate the last two slides and insert the copies in alternating order, so the sequence becomes: original slide A, original slide B, then duplicated slide A, duplicated slide B.",
 "score": 1.0,
 "num_steps": 4,
 "actions": [
  "import sys; sys.path.insert(0, '/home/user/osworld_tools'); from libreoffice_impress import *; ImpressTools.get_slide_count(); ImpressTools.print_result()",
  "import sys; sys.path.insert(0, '/home/user/osworld_tools'); from libreoffice_impress import *; ImpressTools.duplicate_slide(slide_index=23); ImpressTools.print_result()",
  "import sys; sys.path.insert(0, '/home/user/osworld_tools'); from libreoffice_impress import *; ImpressTools.duplicate_slide(slide_index=24); ImpressTools.print_result()",
  "DONE"
 ],
 "responses": [
  "<think>\n1. VERIFICATION: This is the first step. I need to determine the total number of slides to identify the \"last two slides\".\n2. CURRENT STATE: LibreOffice Impress is open with a presentation titled \"MLA_Workshop_061X_Works_Cited.pptx\". The status bar indicates \"Slide 1 of 24\", meaning there are 24 slides. The last two slides are Slide 23 and Slide 24.\n3. PLAN: \n    - Identify slide indices: Slide A = 23, Slide B = 24.\n    - Duplicate Slide 23 (Slide A). It will be placed at the end (Slide 25).\n    - Duplicate Slide 24 (Slide B). It will be placed at the end (Slide 26).\n    - The sequence... <89
... (truncated)
```

```json
{
 "task_id": "a097acff-6266-4291-9fbd-137af7ecd439",
 "domain": "libreoffice_impress",
 "instruction": "Could you help me save my slides as pre.pptx on the Desktop?",
 "score": 1.0,
 "num_steps": 2,
 "actions": [
  "import sys; sys.path.insert(0, '/home/user/osworld_tools'); from libreoffice_impress import *; ImpressTools.save_as(file_path='/home/user/Desktop/pre.pptx', overwrite=True); ImpressTools.print_result()",
  "DONE"
 ],
 "responses": [
  "<think>\n1. VERIFICATION: This is the first step. LibreOffice Impress is open with a file named \"Secrets-of-Monetizing-Video.pptx\".\n2. CURRENT STATE: I see the LibreOffice Impress interface. The task is to save the current presentation as \"pre.pptx\" on the Desktop.\n3. NEXT STEP: I will use the `ImpressTools.save_as` method to save the file with the specified name and location.\n4. ACTION: Call `ImpressTools.save_as` with the path `/home/user/Desktop/pre.pptx`.\n</think>\n\n```python\nImpressTools.save_as(file_path='/home/user/Desktop/pre.pptx', overwrite=True)\n```",
  "<think>\n1. VERIFICATION: The previous action `ImpressTools.save_as(file_path='/home/user/Desktop/pre.pptx', overwrite=True)` was executed. Looking at the current window title in the accessibility tree: `root-pane pre.pptx - LibreOffice Impress`. This confirms the file has been renamed and saved as requested.\n2. CURRENT STATE: The application is now showing \"pre.pptx\" as the active document. The task was to save the slides as \"pre.pptx\" on the Desktop.\n3
... (truncated)
```

```json
{
 "task_id": "ac1b39ff-ee4d-4483-abce-c117e98942f0",
 "domain": "libreoffice_impress",
 "instruction": "Move the table on Page 3 to the bottom of the slide.",
 "score": 1.0,
 "num_steps": 4,
 "actions": [
  "import sys; sys.path.insert(0, '/home/user/osworld_tools'); from libreoffice_impress import *; ImpressTools.go_to_slide(slide_index=3); ImpressTools.print_result()",
  "import sys; sys.path.insert(0, '/home/user/osworld_tools'); from libreoffice_impress import *; ImpressTools.position_box(slide_index=3, box_index=1, position='bottom'); ImpressTools.print_result()",
  "pyautogui.moveTo(830, 500); pyautogui.dragTo(830, 950, duration=1.); pyautogui.mouseUp(); print('Drag and Drop Success')",
  "DONE"
 ],
 "responses": [
  "<臨```python\nImpressTools.go_to_slide(slide_index=3)\n```",
  "<think>\n1. VERIFICATION: The previous action `go_to_slide(slide_index=3)` was successful. The current slide is \"Movie List\" (Slide 3 of 3), as confirmed by the status bar and the slide preview pane.\n2. CURRENT STATE: I am on Slide 3. There is a table (represented by table-cells A1 through C3) and a text placeholder. The table is currently positioned in the upper-middle section of the slide.\n3. NEXT STEP: To move the table to the bottom, I will use `ImpressTools.position_box`. Based on the accessibility tree, the table elements are contained within \"PlaceHolder 2\" (box_index 1, since \"PlaceHold... <813 chars>",
  "<think>\n1. VERIFICATION: The previous action `position_box(slide_index=3
... (truncated)
```
