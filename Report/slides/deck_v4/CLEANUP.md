# Deck v4 cleanup (v5 Phase 1, 2026-11-20 14:19 KST)

Commit 72a05f6 pushed intermediate inputs (label inputs, drafts, seeds, bundles, raw follow-up runs, blind judge items).
They were untracked from the tip with `git rm --cached`; the local copies stay, and their patterns are now in `.gitignore`.
Git history was not rewritten, so they remain in 72a05f6. Frozen labels, hash files, label outputs, adjudications, METHODOLOGY and summaries stay tracked.

| File | Bytes | SHA-256 |
|---|---|---|
| `followup/judge/items.jsonl` | 1354253 | `f98b2e91a1f991ce6a0c58f131472c1f6d51c7817db60ab3ebcddd5d8269268b` |
| `followup/runs.jsonl` | 984455 | `09d457308e49cb9a858897de100644fa0bf7f92861b5477bf06daf9946385773` |
| `questions/bundles.jsonl` | 389859 | `56a9095003eac93ce5ea48f8d5c6d52f554e69784c7643a37b1964ae6f2e25ab` |
| `questions/drafts/bundle_in_5.jsonl` | 140619 | `bad9a3875a679cbf95c1c2c01739124cbfe0be66ea4629de790b8ea18ef05010` |
| `questions/drafts/bundle_in_6.jsonl` | 121783 | `fe6d87ca5137003792eb4cc8cabb485e9d1519eaa7367f3b881c2479060cdad1` |
| `questions/drafts/bundle_in_7.jsonl` | 127457 | `00586cca4dd23ac5b3f6757285f7b38ab68bac2347b41fd4b04df8bd643a50ef` |
| `questions/drafts/writer_in_1.jsonl` | 178683 | `843dc237497159344c772b3e97dca86603cb7e445589a338c6b87c6786a5593d` |
| `questions/drafts/writer_in_2.jsonl` | 169021 | `f7954604bada5cdef88d6472f0cc6c0e35f16b98209950a8f7a9705e06035822` |
| `questions/drafts/writer_in_3.jsonl` | 169809 | `d97594b213b274b30c2fdb9ae7d8ae849f7bbc04e95173a5ad8415dabbacafac` |
| `questions/drafts/writer_in_4.jsonl` | 140830 | `d9b3d1230ee01ae46410fb3453f3a35ea9f75015a5e39cab9875b727d0d03170` |
| `questions/label_input.jsonl` | 1526516 | `ea9ab356561202a56b648c124d630ac3da2e5cfdaae7d9de5b16fdc71aa13a3f` |
| `questions/label_input_1.jsonl` | 304094 | `abaf3332a55fc014fd67bbd569553e6c755e3b0a4d45ed12c0b1541faf93dcf1` |
| `questions/label_input_2.jsonl` | 324731 | `cee4881a81d69b6ae921b2cca692f6edcd74c043dc444ed6b11ade7c47e75802` |
| `questions/label_input_3.jsonl` | 350672 | `1937100dec7ae03627b3dca420ee7766caf0d187a96a2243f6cba6db04546bb2` |
| `questions/label_input_4.jsonl` | 334984 | `dbb7038c9da97addacbd394495991b04e9d037ea92c6ee5d9466d44372312dd7` |
| `questions/label_input_buffer.jsonl` | 648514 | `376ed82f900a73230bd8cd8f7b4cfd886d4c9c70c1240843236758873ae45a58` |
| `questions/label_input_buffer2.jsonl` | 198247 | `674aa46dedcdcd0a1661cc8bb397d8a074084c49e18e01dfe105075ced490280` |
| `questions/prepared_dev2.jsonl` | 98049 | `bede5baeddba8331af27736d435ca6f171e2f321d38a426037926c45b3b2f102` |
| `questions/prepared_test3.jsonl` | 224108 | `dfa3d42e3ea12444f7e18bc7b9d7832db9af66a3399a750e3511955130c81050` |
| `questions/seeds.jsonl` | 653876 | `cced463ec496196d3ab16a87aefd3d7088a6e148896bca2cc588562b626c5910` |
| `questions/selection_reserve.jsonl` | 184674 | `c3774448f3e4f1e3775c5a5c35ccdd7229fc37bcc5e8b8009149f3752687b1c0` |
| `questions/verification_input_1.jsonl` | 611578 | `556e4ed9f1a6e9162c459eb309d72127420f0e32ef419ebfcede690eb518a3be` |
| `questions/verification_input_2.jsonl` | 602606 | `a556123dd38432beeaf295f76e229798b8e5c4715ba1a60f8d7047f313f99e7b` |
