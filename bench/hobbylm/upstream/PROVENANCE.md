# HobbyLM vendored files

- Hugging Face source: [`Hobbylm/hobbylm-1B-computer-use`](https://huggingface.co/Hobbylm/hobbylm-1B-computer-use)
- Frozen revision: `4ea1389b68f5a6f7ec72200543fd8374c14d4526`
- License: Apache-2.0; the upstream `LICENSE` is included verbatim.
- Round 4 is the 125-request sealed live set ("90/125" completed pass-bar target).
- Other frozen sets include r1 (95), r2 (95), r3 (107), System Settings navigation, Calculator tasks, prompts, and pass-bar amendments.
- GitHub links present in the upstream model card: `https://github.com/mediar-ai/mcp-server-macos-use`

| File | SHA-256 |
|---|---|
| `LICENSE` | `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` |
| `README.md` | `c8c636e9f2150e6070be1aa1a91f0ba3497d99a64f48cc0906769f73dfe01513` |
| `data/frozen/calc-prompt.json` | `f9a2346a314ff89544fbd3aec33129708455cf1197a8d7b207af4df9a2e4160f` |
| `data/frozen/calc-tasks.json` | `2764f4a93de6addfe9fed36334b1da27d2703fd6fbb66a11e9734f0804ae3b80` |
| `data/frozen/hobbymac-pass-bar-amendment-1.json` | `58706f4fb0abd39659d243cb6a565c23d5c2ce0bb144693281cbbbbe27f54feb` |
| `data/frozen/hobbymac-pass-bar-amendment-2-owner-75.json` | `6806d8057d9119d13b9dfcd67a74efecd39473d481b6e90ab8dc61b063566ec5` |
| `data/frozen/hobbymac-pass-bar.json` | `4ce1515584727287097ffd85da72b8c8df72fa088aca05afe88db030f3757cfe` |
| `data/frozen/hobbymac-round2-note.json` | `7d6b7f39a1349e823f38b42466bd0e8be66da585f69c3b6781c5df81c2cf9613` |
| `data/frozen/hobbymac-round3-note.json` | `cee9de00205acce2826da486d935b04210b8f707f37852392b8e6edc2b8eb00e` |
| `data/frozen/hobbymac-round4-note.json` | `b9af07c18be8ab505ff281d374576bb9ea2c1c297cd3a52c9d478f7ec49d91bb` |
| `data/frozen/hobbymac-sealed-test-r2.tsv` | `9c28e19c1d1943cd0e93dd25c365c7408364eab6ee1e919f7bc223db157e1b41` |
| `data/frozen/hobbymac-sealed-test-r3.tsv` | `3b4fafcc745c8c2ea017dd9f0e300d9a60a03870d466932d3b598e8598c7b20e` |
| `data/frozen/hobbymac-sealed-test-r4.tsv` | `ce47570115f4257129edf3b81c8e5abc9d8ea69cae4b9d4c19bff16da93ec052` |
| `data/frozen/hobbymac-sealed-test.tsv` | `226220477cca432da009bbcc04e8af5ac3b1645a425ae464d659924fdc44c05e` |
| `data/frozen/prompt.json` | `f7924b847176e99c62b13af292ea479bab105e51501294e51be41c37c4a7dfef` |
| `data/frozen/tasks-amendment-1.json` | `642674041ffd68ea45ed0da3643b78758f8d5dfc2116650614214c612819431c` |
| `data/frozen/tasks.json` | `9e8e499395d43e65af08188e864337326fb3da1f2734367c30d88d378b8f21c4` |
| `data/hobbymac-regex-sealed-r2.json` | `93c99129719fa1cb477a466256d225984aba81746d3ef8574881f0a638f62246` |
| `data/hobbymac-regex-sealed-r3.json` | `d4f768a9c74c20250283ace963eafbceaa52bc0b149467583a5c74fd2a867f9e` |
| `data/hobbymac-regex-sealed-r4.json` | `93c99129719fa1cb477a466256d225984aba81746d3ef8574881f0a638f62246` |
| `data/hobbymac-regex-sealed.json` | `f6123a63b443c73e5c235063565a15c32c8bf39b111b0a54dc57ed6b58223391` |
| `hobby/brightness.swift` | `bbd0a5cbe5da8df3eec7c79360790bd1868b3fabe120ffaceb9770d193ebe592` |
| `hobby/calc_checker.swift` | `f991cad815e02dabb58a5deae06707a13b3a5aaa4ffe961e860ff9e3b6be3f44` |
| `hobby/calendar_tool.py` | `bc2197b879440dbdcae7062be48b3ab1f1324c45cbfeec347ae03293425f9403` |
| `hobby/checker.swift` | `41c3c0ce6886697cf23e6bb9d4aad6b1949cfbf9a5c29f5683076d12ff91606d` |
| `hobby/hobbymac_data.py` | `38b4155aa848e1d507c060839a5515596424f9e5502aee67a55365430eecde53` |
| `hobby/hobbymac_run.py` | `a27aed006a846046947fb988ca17b3e503dc30f2d96972020aa1e57fee56bb4a` |
| `hobby/hobbymac_score.py` | `8a06aa85b1778effaa196ba64deccfdadd0f2ab7da678ada39f5fe1d61dce18b` |
| `hobby/mcp_client.py` | `d709a47bf541d8d9bb578c59f01874cea8ce4d6eeb1233ab7e9e67a41fed293b` |
| `hobby/media_key.swift` | `6f2857e16b4bcc3742591338587b2b430ced2e8a7b5130a664f72012b12057dc` |
| `scripts/setup.sh` | `23c6c5914a36303dccee7e4db11eeb5e1355639bd9bd620a118f3324ce516b22` |

- `hobby/calc_checker.swift` is patched (Muselet, 6a37d0c): macOS 27 Calculator's display is an AXScrollArea with AXIdentifier `StandardInputView;value:<n>` and no `Input` description; the original condition is kept. Same element, same value.
