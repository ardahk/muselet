# Qwen/WebWorldData

Use (SPEC): ELEMENT + planner (web AX trajectories)

- Revision: `e108c5f8e35445c9ddff71cde2a5b1fc4db4020c`
- Total size: 52.24 GB in 3 files
- License: card tag: `apache-2.0`; LICENSE file: none
- Platform split: web (open web, Playwright); English + Chinese
- Approx. tokens per converted example (Qwen3.5 tokenizer): 1.2K-20.5K tokens per conversation in the first 5 rows (median ~6.8K); README says max context 30K

## Files sampled

- `WebWorld_Training.jsonl`: 52243.3 MB, est. rows 639981 (from bytes/row of the sampled head), keys: `conversations`

## Notes

Single 52.2 GB jsonl (`WebWorld_Training.jsonl`), schema `{conversations:[{from,value}]}` in ShareGPT form. These are WORLD-MODEL samples (human = page state + action, gpt = predicted NEXT PAGE STATE), not agent policy samples. Turning them into ELEMENT/planner data means re-deriving (state, action) pairs from the human turns; the gpt side is a next-state AX tree, not an action. This is a schema/use mismatch with the spec ('ELEMENT + planner'); flagging instead of redesigning. Row count: README 1,059,348 trajectories; byte-rate estimate from the first 4 MB is ~640K lines (lines may hold several trajectories, or rows vary in size).

## 3 raw examples (long strings and binary truncated)

```json
{
 "conversations": [
  {
   "from": "human",
   "value": "You are a web world model. I will provide you with an initial page state and a sequence of actions. For each action, predict the resulting page state.\nStrictly maintain the original format. Output only the full page state without explanations, code, or truncation.\n\nInitial Page State:\nRootWebArea 'Natural Homeopathic Remedies in New Zealand | NaturoPharm', focused, busy=1\n\t[83] region 'top of page'\n\t[96] banner ''\n\t\t[107] heading 'Auckland North'\n\t\t[113] heading 'Auckland North'\n\t\t[116] link 'Buy Now'\n\t\t\tStaticText 'Buy Now'\n\t\t[119] link 'Buy Now'\n\t\t\tStaticText 'Buy Now'\n\t\t[122] link ''\n\t\t\t[12... <6783 chars>"
  },
  {
   "from": "gpt",
   "value": "RootWebArea 'Terms and Conditions | naturopharm', focused, busy=1\n\t[69] region 'top of page'\n\t[82] banner ''\n\t\t[93] heading 'Auckland North'\n\t\t[99] heading 'Auckland North'\n\t\t[102] link 'Buy Now'\n\t\t\tStaticText 'Buy Now'\n\t\t[105] link 'Buy Now'\n\t\t\tStaticText 'Buy Now'\n\t\t[108] link ''\n\t\t\t[109] image ''\n\t\t[113] generic, live='polite', relevant='additions text'\n\t\t\t[116] search ''\n\t\t\t\t[126] searchbox 'Search here...'\n\t\t[134] button ''\n\t\t\t[136] image ''\n\t\t[137] navigation 'Site'\n\t\t\t[138] list ''\n\t\t\t\t[139] listitem ''\n\t\t\t\t\t[140] link 'Shop by Health Concern'\n\t\t\t\t\t\t[143] paragraph ''\n\t\t\t\t\t\t\tStaticText ... <15138 chars>"
  },
  {
   "from": "human",
   "value": "Cont
... (truncated)
```

```json
{
 "conversations": [
  {
   "from": "human",
   "value": "You are a web world model. I will provide you with an initial page state and a sequence of actions. For each action, predict the resulting page state.\nStrictly maintain the original format. Output only the full page state without explanations, code, or truncation.\n\nInitial Page State:\nRootWebArea 'Arnott – Eye associates', focused\n\t[36] link 'Arnott'\n\t\t[37] image 'Arnott'\n\t[43] link 'Phone'\n\t\tStaticText 'Phone'\n\t[46] link 'enquiries@arnotteye.com'\n\t\tStaticText 'enquiries@arnotteye.com'\n\t[49] list ''\n\t\t[50] listitem ''\n\t\t\t[51] link 'Conditions & Treatments'\n\t\t\t\t[53] image ''\n\t\t[67] listitem ''\n... <6707 chars>"
  },
  {
   "from": "gpt",
   "value": "RootWebArea 'Glaucoma – Arnott', focused\n\t[35] link 'Arnott'\n\t\t[36] image 'Arnott'\n\t[42] link 'Phone'\n\t\tStaticText 'Phone'\n\t[45] link 'enquiries@arnotteye.com'\n\t\tStaticText 'enquiries@arnotteye.com'\n\t[48] list ''\n\t\t[49] listitem ''\n\t\t\t[50] link 'Conditions & Treatments'\n\t\t\t\t[52] image ''\n\t\t[66] listitem ''\n\t\t\t[67] link 'Consultants'\n\t\t[68] listitem ''\n\t\t\t[69] link 'Why book a consultation'\n\t\t[70] listitem ''\n\t\t\t[71] link 'Contact'\n\t\t[72] listitem ''\n\t\t\t[73] link 'About'\n\t[74] link 'BOOK A CONSULTATION'\n\t[77] paragraph ''\n\t\t[78] strong ''\n\t\t\tStaticText 'Have an emergency?'\n\t\tStaticText ''\n\t\tSta... <5687 chars>"
  },
  {
   "from": "human",
   "value": "Continue the
... (truncated)
```

```json
{
 "conversations": [
  {
   "from": "human",
   "value": "You are a web world model. I will provide you with an initial page state and a sequence of actions. For each action, predict the resulting page state.\nStrictly maintain the original format. Output only the full page state without explanations, code, or truncation.\n\nInitial Page State:\nRootWebArea 'virginiapicnicbasket.com', focused\n\t[a] Iframe ''\n\t\tRootWebArea ''\n\t[13] main ''\n\t\t[15] heading 'VIRGINIAPICNICBASKET.COM'\n\t\t[16] Section ''\n\t\t\t[b] Iframe ''\n\t\t\t\tRootWebArea ''\n\t\t\t\t\t[b8] region ''\n\t\t\t\t\t\tStaticText 'Related searches'\n\t\t\t\t\t\t[b14] link 'Gift Hampers'\n\t\t\t\t\t\t\tStaticText 'Gift Hampers'\n\t\t\t... <988 chars>"
  },
  {
   "from": "gpt",
   "value": "RootWebArea 'Privacy Policy', focused\n\t[6] heading 'PRIVACY POLICY AND COOKIES'\n\t\tStaticText 'PRIVACY POLICY AND COOKIES'\n\t[8] paragraph ''\n\t\tStaticText 'Last Updated: January 21, 2025'\n\t[10] paragraph ''\n\t\tStaticText 'This web page (the \"Website\") was generated by the domain owner using the Bodis Domain Platform owned by Bodis, LLC (\"we\", \"us\", or \"our\").'\n\t[11] paragraph ''\n\t\tStaticText 'Disclaimer'\n\t\tStaticText ': We have no relationship with any advertisers, advertisements, or third-party content that may be displayed on the Website. Reference to any specific service or brand is not contro... <47569 chars>"
  },
  {
   "from": "human",
   "value": "Continue the trajectory. Given the
... (truncated)
```
