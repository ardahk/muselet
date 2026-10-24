# xlangai/AgentNet

Use (SPEC): vision planner (screenshots + pyautogui); macOS slice via meta_data_merged.jsonl `system`

- Revision: `d76ee50a63fad81cfdbe576416757d7c2091ed50`
- Total size: 199.56 GB in 44 files
- License: card tag: `mit`; LICENSE file: MIT License
- Platform split: meta_data_merged.jsonl (22,532 rows): Windows 12,364 / Darwin 5,168 / Ubuntu 5,000. The macOS value is `Darwin`, not `macOS`; `release` is the Darwin kernel version (e.g. 24.1.0).
- Approx. tokens per converted example (Qwen3.5 tokenizer): ~6.3K tokens for a 7-step trajectory text (observation+thought+action+code+reflection), ~800 tokens per step; screenshots excluded

## Files sampled

- `meta_data_merged.jsonl`: 18.8 MB, est. rows 20107 (from bytes/row of the sampled head), keys: `action_entropy`, `action_frequency`, `applications`, `complexity`, `domains`, `instruction`, `release`, `screen_height`, `screen_width`, `step_num`, `system`, `task_description_alignment`, `task_description_ambiguity`, `task_id`, `verify_feedback`, `websites`
- `agentnet_win_mac_18k.jsonl`: 1400.6 MB, est. rows 21709 (from bytes/row of the sampled head), keys: `actual_task`, `alignment_score`, `efficiency_score`, `instruction`, `natural_language_task`, `reason`, `task_completed`, `task_difficulty`, `task_id`, `traj`

## Notes

Trajectories are in agentnet_win_mac_18k.jsonl (1.4 GB, ~21.7K rows) and agentnet_ubuntu_5k.jsonl. Each `traj` step has image filename, observation, thought, action, code (`pyautogui.click(x=0.1632, y=0.2711)`, normalized coords), last_step_correct/redundant, reflection. Images are split zip archives (~195 GB); not downloaded.

## 3 raw examples (long strings and binary truncated)

```json
{
 "task_id": "20240927235321_5855063d-3f37-47a4-ab45-5247adfdb6f7",
 "instruction": "sort the table in ascending order based on the number column data in excel",
 "verify_feedback": {
  "quality": "ok"
 },
 "domains": "Office Tools",
 "system": "Windows",
 "release": "11",
 "applications": [
  "wps office"
 ],
 "websites": [],
 "step_num": 7,
 "screen_width": 1440,
 "screen_height": 900,
 "task_description_alignment": "High Alignment",
 "task_description_ambiguity": "None",
 "complexity": {
  "multi_application_or_website": false,
  "contains_professional_knowledge": false,
  "involves_uncommon_features": false,
  "involves_repetitive_simple_subtasks": false,
  "logically_coherent_long_task": true,
  "complexity_score": 3
 },
 "action_entropy": 0.5917,
 "action_frequency": {
  "click": 6,
  "terminate": 1
 }
}
```

```json
{
 "task_id": "20240930165051_ea4e464c-7278-4365-8b72-2f512258d1ba",
 "instruction": "Use Excel Formula NORM to sample 30 point from Standard normal distribution",
 "verify_feedback": {
  "quality": "ok"
 },
 "domains": "Office Tools",
 "system": "Windows",
 "release": "10",
 "applications": [
  "microsoft excel"
 ],
 "websites": [],
 "step_num": 6,
 "screen_width": 1920,
 "screen_height": 1080,
 "task_description_alignment": "High Alignment",
 "task_description_ambiguity": "None",
 "complexity": {
  "multi_application_or_website": false,
  "contains_professional_knowledge": false,
  "involves_uncommon_features": false,
  "involves_repetitive_simple_subtasks": true,
  "logically_coherent_long_task": true,
  "complexity_score": 3
 },
 "action_entropy": 2.4194,
 "action_frequency": {
  "click": 3,
  "write": 2,
  "press": 1,
  "moveTo": 1,
  "dragTo": 1,
  "terminate": 1
 }
}
```

```json
{
 "task_id": "20240923010833_927af299-f6dc-4686-8221-b7f29cbe90b8",
 "instruction": "Install the Google Scholar Button extension in Google Chrome",
 "verify_feedback": {
  "quality": "ok"
 },
 "domains": "Web Tools & Internet Utilities",
 "system": "Darwin",
 "release": "21.6.0",
 "applications": [
  "google chrome"
 ],
 "websites": [
  "google",
  "chrome web store"
 ],
 "step_num": 6,
 "screen_width": 1728,
 "screen_height": 1117,
 "task_description_alignment": "High Alignment",
 "task_description_ambiguity": "None",
 "complexity": {
  "multi_application_or_website": false,
  "contains_professional_knowledge": false,
  "involves_uncommon_features": false,
  "involves_repetitive_simple_subtasks": false,
  "logically_coherent_long_task": true,
  "complexity_score": 3
 },
 "action_entropy": 1.6645,
 "action_frequency": {
  "click": 4,
  "write": 1,
  "press": 1,
  "terminate": 1
 }
}
```
