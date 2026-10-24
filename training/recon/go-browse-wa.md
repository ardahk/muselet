# apurvaga/go-browse-wa

Use (SPEC): planner (web AX, incl. failures)

- Revision: `4b14ddca1dd9f87b5323ec9c96daaef1391b6612`
- Total size: 0.85 GB in 11 files
- License: card tag: none; LICENSE file: none. **The spec says MIT, but the HF card has no license tag, no LICENSE file and no license section. Needs confirmation (the Go-Browse paper/code repo may state it).**
- Platform split: web (WebArena sites: OpenStreetMap, shopping, gitlab, ...)
- Approx. tokens per converted example (Qwen3.5 tokenizer): ~5.2K-7.1K tokens per step (system + goal + AX tree + completion)

## Row counts (parquet footers)

| files | rows |
|---|---|
| `data/train` | 164,533 |

## Schema (`data/train-00000-of-00009.parquet`)

```
step_idx: int64
step_data: struct<prompt: list<element: struct<role: string, content: string>>, completion: list<element: struc (... 34 chars omitted)
  child 0, prompt: list<element: struct<role: string, content: string>>
      child 0, element: struct<role: string, content: string>
          child 0, role: string
          child 1, content: string
  child 1, completion: list<element: struct<role: string, content: string>>
      child 0, element: struct<role: string, content: string>
          child 0, role: string
          child 1, content: string
traj_reward: double
next_step_idx: int64
traj_length: int64
step_number: int64
```

## Notes

One row per step, already chat-formatted (`step_data.prompt` = system+user with AX tree, `completion` = assistant JSON `{thought, action}` with BrowserGym actions like `click('149')`). `traj_reward` (all 1.0 in the first shard sample) is what separates successes from failures; the failure share is not counted yet (needs a full-column scan of `traj_reward`, ~cheap via projection).

## 3 raw examples (long strings and binary truncated)

```json
{
 "step_idx": 0,
 "step_data": {
  "prompt": [
   {
    "role": "system",
    "content": "# Instructions\nYou are a UI Assistant, your goal is to help the user perform tasks using a web browser. \nReview the instructions from the user, the current state of the page and all other information to find the best possible next action to accomplish your goal. Your answer will be interpreted and executed by a program, make sure to follow the formatting instructions.\n"
   },
   {
    "role": "user",
    "content": "# Goal\nFind driving directions from Central Park, New York to Times Square, New York using the Car (OSRM) option.\n\n# Current page Accessibility Tree\nRootWebArea 'OpenStreetMap', focused, url='http://ec2-3-148-123-246.us-east-2.compute.amazonaws.com:3000/#map=7/42.896/-75.108'\n\t[44] banner ''\n\t\t[45] heading 'OpenStreetMap logo OpenStreetMap'\n\t\t\t[46] link 'OpenStreetMap logo OpenStreetMap', url='http://ec2-3-148-123-246.us-east-2.compute.amazonaws.com:3000/#map=7/42.896/-75.108'\n\t\t\t\t[49] image 'OpenStreetMap logo', url='http://ec2-3-148-123-246.us-east-2.compute.amazonaws.com:3000/assets/osm_log... <12629 chars>"
   }
  ],
  "completion": [
   {
    "role": "assistant",
    "content": "{\"thought\": \"Looking at the current page, I can see I'm on OpenStreetMap. To find directions, I need to click on the 'Find directions between two points' link which has a directions icon. I can see this element with ID 149 in the accessibility tree.\", \"action\": \"click
... (truncated)
```

```json
{
 "step_idx": 1,
 "step_data": {
  "prompt": [
   {
    "role": "system",
    "content": "# Instructions\nYou are a UI Assistant, your goal is to help the user perform tasks using a web browser. \nReview the instructions from the user, the current state of the page and all other information to find the best possible next action to accomplish your goal. Your answer will be interpreted and executed by a program, make sure to follow the formatting instructions.\n"
   },
   {
    "role": "user",
    "content": "# Goal\nFind driving directions from Central Park, New York to Times Square, New York using the Car (OSRM) option.\n\n# Current page Accessibility Tree\nRootWebArea 'OpenStreetMap', focused, url='http://ec2-3-148-123-246.us-east-2.compute.amazonaws.com:3000/directions'\n\t[44] banner ''\n\t\t[45] heading 'OpenStreetMap logo OpenStreetMap'\n\t\t\t[46] link 'OpenStreetMap logo OpenStreetMap', url='http://ec2-3-148-123-246.us-east-2.compute.amazonaws.com:3000/#map=7/42.896/-75.108'\n\t\t\t\t[49] image 'OpenStreetMap logo', url='http://ec2-3-148-123-246.us-east-2.compute.amazonaws.com:3000/assets/osm_logo-4afddaae0... <13182 chars>"
   }
  ],
  "completion": [
   {
    "role": "assistant",
    "content": "{\"thought\": \"I'm now on the OpenStreetMap directions page. To find driving directions from Central Park to Times Square, I need to:\\n1. Enter 'Central Park, New York' in the 'From' textbox\\n2. Enter 'Times Square, New York' in the 'To' textbox\\n3. Ensure 'Car (OSRM)' i
... (truncated)
```

```json
{
 "step_idx": 2,
 "step_data": {
  "prompt": [
   {
    "role": "system",
    "content": "# Instructions\nYou are a UI Assistant, your goal is to help the user perform tasks using a web browser. \nReview the instructions from the user, the current state of the page and all other information to find the best possible next action to accomplish your goal. Your answer will be interpreted and executed by a program, make sure to follow the formatting instructions.\n"
   },
   {
    "role": "user",
    "content": "# Goal\nFind driving directions from Central Park, New York to Times Square, New York using the Car (OSRM) option.\n\n# Current page Accessibility Tree\nRootWebArea 'OpenStreetMap', focused, url='http://ec2-3-148-123-246.us-east-2.compute.amazonaws.com:3000/directions'\n\t[44] banner ''\n\t\t[45] heading 'OpenStreetMap logo OpenStreetMap'\n\t\t\t[46] link 'OpenStreetMap logo OpenStreetMap', url='http://ec2-3-148-123-246.us-east-2.compute.amazonaws.com:3000/#map=7/42.896/-75.108'\n\t\t\t\t[49] image 'OpenStreetMap logo', url='http://ec2-3-148-123-246.us-east-2.compute.amazonaws.com:3000/assets/osm_logo-4afddaae0... <13762 chars>"
   }
  ],
  "completion": [
   {
    "role": "assistant",
    "content": "{\"thought\": \"I've already filled in the 'From' field with 'Central Park, New York'. Now I need to fill in the 'To' field with 'Times Square, New York'. Looking at the accessibility tree, I can see the 'To' textbox with bid '163'. After filling this field, I'll need to cli
... (truncated)
```
