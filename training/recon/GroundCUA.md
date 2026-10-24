# ServiceNow/GroundCUA

Use (SPEC): grounder

- Revision: `5d6845b0116029d46ec762e734701c5b8ce207c3`
- Total size: 21.66 GB in 100000 files
- License: card tag: `mit`; LICENSE file: none
- Platform split: 87 desktop apps across Windows, macOS, Linux and cross-platform (per README); no per-file platform field, so the platform split must be derived from app folder names
- Approx. tokens per converted example (Qwen3.5 tokenizer): ~200 tokens per element annotation (bbox + text + category); one screenshot json holds ~60 elements

## Files sampled

- `data/Matrix/55d94757d28ae8276e27c1dbb5da8a4b403e7a48a8773f97ae39a192fe6dab40.json`: 0.0 MB, est. rows 62 (from bytes/row of the sampled head), keys: `bbox`, `category`, `id`, `image_path`, `text`

## Notes

Layout is `data/<App>/<sha256>.json` (51,175 annotation files) + `images/<App>/<sha256>.png` (48,823 PNGs, 20.6 GB). Each json is a list of `{image_path, bbox[x1,y1,x2,y2] px, text, category, id}`. Some json files are empty (`[]`, 2 bytes). README size category is 1M-10M elements.

## 3 raw examples (long strings and binary truncated)

```json
{
 "image_path": "Matrix/55d94757d28ae8276e27c1dbb5da8a4b403e7a48a8773f97ae39a192fe6dab40.png",
 "bbox": [
  1684.1115371209478,
  14.759149529452769,
  1710.043917741373,
  39.04635761589404
 ],
 "text": "click video call",
 "category": "",
 "id": "3ca70a90-5261-4b6f-9147-3588cdd4456c"
}
```

```json
{
 "image_path": "Matrix/55d94757d28ae8276e27c1dbb5da8a4b403e7a48a8773f97ae39a192fe6dab40.png",
 "bbox": [
  117.9,
  146.05998977661133,
  153.9,
  180.8999897766113
 ],
 "text": "people",
 "category": "",
 "id": "ea92f46d-085a-488f-b838-220f09030c97"
}
```

```json
{
 "image_path": "Matrix/55d94757d28ae8276e27c1dbb5da8a4b403e7a48a8773f97ae39a192fe6dab40.png",
 "bbox": [
  60.3,
  104.52000000000001,
  170.70000000000002,
  127.3
 ],
 "text": "people",
 "category": "",
 "id": "d03051bb-e3ba-4c11-b3e9-060766d864cc"
}
```
