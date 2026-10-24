# LangAGI-Lab/Mind2Web-axtree

Use (SPEC): ELEMENT decisions (web AX)

- Revision: `d6f833f80dd6298e991150dfb397f1690aa444a6`
- Total size: 0.96 GB in 15 files
- License: card tag: none; LICENSE file: none. **NO license tag, no LICENSE file, no license section in the README. The original Mind2Web is CC-BY-4.0 but this derivative states nothing: needs lead decision.**
- Platform split: web (Mind2Web websites, desktop Chrome)
- Approx. tokens per converted example (Qwen3.5 tokenizer): ~6,400 tokens for `accessibility_tree` + task + action of one step (15K chars); will need pruning to around the candidates for a System-1 ELEMENT prompt

## Row counts (parquet footers)

| files | rows |
|---|---|
| `data/train` | 7,775 |

## Schema (`data/train-00008-of-00013.parquet`)

```
action_uid: string
raw_html: string
cleaned_html: string
operation: string
pos_candidates: list<element: string>
  child 0, element: string
neg_candidates: list<element: string>
  child 0, element: string
website: string
domain: string
subdomain: string
annotation_id: string
confirmed_task: string
action_reprs: list<element: string>
  child 0, element: string
target_action_index: string
target_action_reprs: string
accessibility_tree: string
action: string
original_action_repr: string
original_pos_candidate: struct<attributes: struct<alt: string, aria_description: string, aria_label: string, backend_node_id (... 391 chars omitted)
  child 0, attributes: struct<alt: string, aria_description: string, aria_label: string, backend_node_id: string, bounding_ (... 280 chars omitted)
      child 0, alt: string
      child 1, aria_description: string
      child 2, aria_label: string
      child 3, backend_node_id: string
      child 4, bounding_box_rect: string
      child 5, class: string
      child 6, data_pw_testid_buckeye_candidate: string
      child 7, id: string
      child 8, input_checked: string
      child 9, input_value: string
      child 10, is_clickable: string
      child 11, label: string
      child 12, name: string
      child 13, placeholder: string
      child 14, role: string
      child 15, text_value: string
      child 16, title: string
      child 17, type: string
      child 18, value: string
  child 1, backend_node_id: string
  child 2, is_original_target: bool
  child 3, is_top_level_target: bool
  child 4, tag: string
match_type: string
```

## Notes

One row per action step (7,775 rows). `pos_candidates`/`neg_candidates` give the target and distractor elements; `action` is already in axtree-id form, e.g. `type [98] [Hotels]`. Also carries raw/cleaned HTML (large; drop).

## 3 raw examples (long strings and binary truncated)

```json
{
 "action_uid": "62440a28-36b1-4101-bba1-55fc81c56f90",
 "raw_html": "<!DOCTYPE html PUBLIC \"-//W3C//DTD HTML 4.0 Transitional//EN\" \"http://www.w3.org/TR/REC-html40/loose.dtd\">\n<html backend_node_id=\"101\" bounding_box_rect=\"0,0,1280,4189.25\" class=\" csscalc cssanimations appearance svg\">\n  <body>\n    <header backend_node_id=\"241\" bounding_box_rect=\"0,0,1280,80\" role=\"banner\" class=\"global-header nocontent  hide-in-app\">\n      <div backend_node_id=\"244\" bounding_box_rect=\"0,0,1280,80\" class=\"header-content push\">\n        <div backend_node_id=\"246\" bounding_box_rect=\"20,22,154,36\" class=\"logo-header\">\n          <a backend_node_id=\"248\" bounding_box_rect=\"20,22,154... <147081 chars>",
 "cleaned_html": "<html backend_node_id=\"101\">\n  <body>\n    <header backend_node_id=\"241\" role=\"banner\">\n      <div backend_node_id=\"244\">\n        <a backend_node_id=\"248\" title=\"Travelzoo\">\n            <text backend_node_id=\"249\">Travelzoo</text>\n          </a>\n        <div backend_node_id=\"254\">\n          <a backend_node_id=\"256\" role=\"button\">\n            <text backend_node_id=\"257\">Menu</text>\n          </a>\n          <div backend_node_id=\"259\">\n            <ul backend_node_id=\"261\">\n              <li backend_node_id=\"263\">\n                <iframe backend_node_id=\"89\" name=\"f3f67040dcc25c4\" title=\"fb:like F... <64792 chars>",
 "operation": "{\"original_op\": \"TYPE\", \"value\": \"Hotels\", \"op\": \"TYPE\"}"
... (truncated)
```

```json
{
 "action_uid": "fcad2218-4124-4bbc-bee8-b921a0a01c0b",
 "raw_html": "<!DOCTYPE html PUBLIC \"-//W3C//DTD HTML 4.0 Transitional//EN\" \"http://www.w3.org/TR/REC-html40/loose.dtd\">\n<html backend_node_id=\"6289\" bounding_box_rect=\"0,0,1280,4189.25\" class=\" csscalc cssanimations appearance svg\">\n  <body>\n    <header backend_node_id=\"6429\" bounding_box_rect=\"0,0,1280,80\" role=\"banner\" class=\"global-header nocontent  hide-in-app\">\n      <div backend_node_id=\"6432\" bounding_box_rect=\"0,0,1280,80\" class=\"header-content push\">\n        <div backend_node_id=\"6434\" bounding_box_rect=\"20,22,154,36\" class=\"logo-header\">\n          <a backend_node_id=\"6436\" bounding_box_rect=\"20,2... <147976 chars>",
 "cleaned_html": "<html backend_node_id=\"6289\">\n  <body>\n    <header backend_node_id=\"6429\" role=\"banner\">\n      <div backend_node_id=\"6432\">\n        <a backend_node_id=\"6436\" title=\"Travelzoo\">\n            <text backend_node_id=\"6437\">Travelzoo</text>\n          </a>\n        <div backend_node_id=\"6442\">\n          <a backend_node_id=\"6444\" role=\"button\">\n            <text backend_node_id=\"6445\">Menu</text>\n          </a>\n          <div backend_node_id=\"6447\">\n            <ul backend_node_id=\"6449\">\n              <li backend_node_id=\"6451\">\n                <iframe backend_node_id=\"6278\" name=\"f3f67040dcc25c4\" tit... <65105 chars>",
 "operation": "{\"original_op\": \"CLICK\", \"value\": \"\", \"op\": \"CLICK\"}",
 "p
... (truncated)
```

```json
{
 "action_uid": "babd2160-a830-4bcf-a262-9729e78664c1",
 "raw_html": "<!DOCTYPE html PUBLIC \"-//W3C//DTD HTML 4.0 Transitional//EN\" \"http://www.w3.org/TR/REC-html40/loose.dtd\">\n<html backend_node_id=\"12765\" bounding_box_rect=\"0,0,1280,4191.25\" class=\" csscalc cssanimations appearance svg\">\n  <body>\n    <header backend_node_id=\"12905\" bounding_box_rect=\"0,0,1280,80\" role=\"banner\" class=\"global-header nocontent  hide-in-app\">\n      <div backend_node_id=\"12908\" bounding_box_rect=\"0,0,1280,80\" class=\"header-content push\">\n        <div backend_node_id=\"12910\" bounding_box_rect=\"20,22,154,36\" class=\"logo-header\">\n          <a backend_node_id=\"12912\" bounding_box_rect=... <182961 chars>",
 "cleaned_html": "<html backend_node_id=\"12765\">\n  <body>\n    <header backend_node_id=\"12905\" role=\"banner\">\n      <div backend_node_id=\"12908\">\n        <a backend_node_id=\"12912\" title=\"Travelzoo\">\n            <text backend_node_id=\"12913\">Travelzoo</text>\n          </a>\n        <div backend_node_id=\"12918\">\n          <a backend_node_id=\"12920\" role=\"button\">\n            <text backend_node_id=\"12921\">Menu</text>\n          </a>\n          <div backend_node_id=\"12923\">\n            <ul backend_node_id=\"12925\">\n              <li backend_node_id=\"12927\">\n                <iframe backend_node_id=\"12753\" name=\"f3f67040... <79541 chars>",
 "operation": "{\"original_op\": \"TYPE\", \"value\": \"Mexico\", \"op\": \"TYPE\"}",
 
... (truncated)
```
