# OS-Copilot/OS-Atlas-data

Use (SPEC): grounder (macOS)

- Revision: `e3a4c90c5f6129c25efdaa0671b08a11f7cb8f3f`
- Total size: 816.07 GB in 43 files
- License: card tag: `apache-2.0`; LICENSE file: none
- Platform split: desktop_domain/macos_splited.json: macOS only
- Approx. tokens per converted example (Qwen3.5 tokenizer): ~30-60 tokens per element (instruction + normalized bbox); ~4 elements per screenshot

## Files sampled

- `desktop_domain/macos_splited.json`: 6.5 MB, est. rows 4441 (from bytes/row of the sampled head), keys: `elements`, `img_filename`

## Notes

macos_splited.json (6.5 MB): 4,441 screenshots, 18,399 elements, `{img_filename, elements:[{instruction, bbox [l,t,r,b] in 0-1, data_type}]}`. data_type is an AX role (AXStaticText 13,266, AXTextField 1,167, AXRadioButton 1,041, AXButton 838, ...). Mostly static text, so it is weak for clickable-target grounding. Images: desktop_domain/macos_images.zip (5.5 GB); not downloaded. The README `instruction` is a referring expression from the a11y tree, not a user command.

## 3 raw examples (long strings and binary truncated)

```json
{
 "img_filename": "20240905_135955_screenshot.png",
 "elements": [
  {
   "instruction": "Clear the Streets!",
   "bbox": [
    0.37777777777777777,
    0.5033333333333333,
    0.44930555555555557,
    0.5655555555555556
   ],
   "data_type": "AXStaticText"
  },
  {
   "instruction": "ESSENTIALS, A+ Apps for Students, Make the most of class and study time",
   "bbox": [
    0.8555555555555555,
    0.4588888888888889,
    1.0909722222222222,
    0.7144444444444444
   ],
   "data_type": "AXStaticText"
  },
  {
   "instruction": "TRY NOW, Learn Hit Pop Songs With Duolingo, New tracks just got added to the Music course",
   "bbox": [
    0.60625,
    0.4588888888888889,
    0.8416666666666667,
    0.7144444444444444
   ],
   "data_type": "AXStaticText"
  },
  {
   "instruction": "A+ Apps for Students",
   "bbox": [
    0.37430555555555556,
    0.14333333333333334,
    0.5305555555555556,
    0.17444444444444446
   ],
   "data_type": "AXStaticText"
  },
  {
   "instruction": "Discover",
   "bbox": [
    0.5763888888888888,
    0.07666666666666666,
    0.6229166666666667,
    0.09777777777777778
   ],
   "data_type": "AXStaticText"
  }
 ]
}
```

```json
{
 "img_filename": "20240905_135955_screenshot.png",
 "elements": [
  {
   "instruction": "MAJOR UPDATE, Clear the Streets, Pull off impossible stunts in Asphalt Legends: Unite",
   "bbox": [
    0.35694444444444445,
    0.4588888888888889,
    0.5923611111111111,
    0.7144444444444444
   ],
   "data_type": "AXStaticText"
  },
  {
   "instruction": "0.4285714328289032",
   "bbox": [
    0.73125,
    0.9344444444444444,
    0.7444444444444445,
    0.9933333333333333
   ],
   "data_type": "AXDockItem"
  },
  {
   "instruction": "Learn Hit Pop Songs With Duolingo",
   "bbox": [
    0.6270833333333333,
    0.5033333333333333,
    0.6986111111111111,
    0.5655555555555556
   ],
   "data_type": "AXStaticText"
  },
  {
   "instruction": "Yen Wang",
   "bbox": [
    0.17569444444444443,
    0.7933333333333333,
    0.3284722222222222,
    0.8555555555555555
   ],
   "data_type": "AXButton"
  },
  {
   "instruction": "Try These Mac Favorites",
   "bbox": [
    0.35694444444444445,
    0.7688888888888888,
    0.5118055555555555,
    0.7955555555555556
   ],
   "data_type": "AXStaticText"
  }
 ]
}
```

```json
{
 "img_filename": "20240905_135955_screenshot_sub1.png",
 "elements": [
  {
   "instruction": "Discover",
   "bbox": [
    0.1527777777777778,
    0.15333333333333332,
    0.24583333333333332,
    0.19555555555555557
   ],
   "data_type": "AXStaticText"
  }
 ]
}
```
