# Offline trace: one page through crawl → clean → chunk → tag → index

Page: https://global.hanyang.ac.kr/eng/s3/s3_2_1.php (ERICA, "International Student Insurance"). Raw file `Sources/data/HYU/raw/e5/e5b2c234b6f622395b6a71c18b4aba8a186eaa531aac20504e2a9f4d5dac05fe.html` (gitignored), fetched 2026-11-10T02:20:42.831941Z, 46,152 bytes, sha256 `e5b2c234b6f62239…`.

## 1. Raw HTML (snippet around the premium table)

```html
s="fade-up" data-aos-delay="100">University Group Insurance Coverage</h4>
		<p class="p-line" data-aos="fade-up" data-aos-delay="200">1st semester - Mar. 1-Sep. 1 / 2nd semester - Sep, 1-Mar. 1</p>
	</article>
	<article class="arti3">
		<h4 class="sub-tit-h4" data-aos="fade-up" data-aos-delay="300">University Group Insurance Premium</h4>
		<p class="p-line" data-aos="fade-up" data-aos-delay="400">KRW 25,000 (same premium for undergraduate and graduate schools)</p>
	</article>
	<article class="arti4">
		<h4 class="sub-tit-h4" data-aos="fade-up" data-aos-delay="100">University Group Insurance Subscription Instructions</h4>
		<p class="p-line" data-aos="fade-up" data-aos-delay="200">Insurance premium will appear as a separate item on each student’s tuition bill</p>
		<p class="p-line" data-ao
```

## 2. Cleaned text in the snapshot (`documents.jsonl`, e-mails masked)

3,509 characters, 37 spans (headings, paragraphs, table rows). First 900 characters:

```
Insurance Information
As of March 1, 2021, the Korean Ministry of Health and Welfare's National Health Insurance Policy for International Students went into effect. Thus, as of the 1st semester of the 2021 school year, ERICA international student medical insurance consists of two different insurance policies: the university’s group insurance policy and the National Health Insurance policy.
University Group Insurance Coverage
1st semester - Mar. 1-Sep. 1 / 2nd semester - Sep, 1-Mar. 1
University Group Insurance Premium
KRW 25,000 (same premium for undergraduate and graduate schools)
University Group Insurance Subscription Instructions
Insurance premium will appear as a separate item on each student’s tuition bill
Students must pay their insurance premium (lump-sum) when paying for their tuition
Returning students who took a leave of absence after paying tuition or those who completed the 
```

## 3. Chunks in index r5 (10 chunks; section-aware, 320 BGE tokens, 48 overlap)

| # | Section heading | Tokens | Characters | First words |
|---|---|---|---|---|
| 0 | Insurance Information | 66 | 370 | As of March 1, 2021, the Korean Ministry of Health and Welfare's Natio |
| 1 | University Group Insurance Coverage | 21 | 59 | 1st semester - Mar. 1-Sep. 1 / 2nd semester - Sep, 1-Mar. 1 |
| 2 | University Group Insurance Premium | 15 | 64 | KRW 25,000 (same premium for undergraduate and graduate schools) |
| 3 | University Group Insurance Subscription Instructio | 91 | 523 | Insurance premium will appear as a separate item on each student’s tui |
| 4 | University group insurance coverage details | 84 | 427 | Death from injury/death from disease/aftereffects Reimbursable medical |
| 5 | Penalties for Overdue Payment | 67 | 402 | Insurance premiums are charged to each student’s tuition bill every se |
| 6 | Refunds for University Group Insurance | 53 | 213 | When taking a leave of absence, withdrawing from school, or being expe |
| 7 | Remarks | 47 | 252 | In the case of medical expenses stemming from hospitalization and surg |
| 8 | Filing a Claim for University Group Insurance Bene | 111 | 513 | 1) When receiving hospital treatment or purchasing medicine, inquire b |
| 9 | Enquiries for University Group Insurance claims | 150 | 307 | <div class="dl-box flex-box"> <dl> <dt>Phone:</dt> <dd> <span>Korean,  |

## 4. Tags on two chunks (applicability condition, rules only in r5)

**Chunk 2** (contains "University Group Insurance Premium"), condition status `conditioned`, tag bucket `rule_tagged`:

```
KRW 25,000 (same premium for undergraduate and graduate schools)
```

```json
{
 "campus": [
  "erica"
 ],
 "scope": "campus",
 "constraints": {
  "degree_level": [
   "undergraduate",
   "master",
   "doctoral"
  ]
 },
 "any_of": [],
 "requirements": [],
 "effective_term": null,
 "superseded_by": null,
 "extraction_method": {
  "scope": "site_default",
  "campus": "site_default",
  "superseded_by": "snapshot",
  "degree_level": "rule"
 }
}
```

**Chunk 5** (contains "Penalties for Overdue Payment"), condition status `unknown`, tag bucket `rule_cue_unknown`:

```
Insurance premiums are charged to each student’s tuition bill every semester. Students may register and enroll once they pay their full tuition and insurance premium amount.
Failure to pay the insurance premium within the tuition payment period will render the student unable to enroll and thus be expelled from the university
No insurance benefits when using medical institutions for treatment or care
```

```json
{
 "campus": [
  "erica"
 ],
 "scope": "campus",
 "constraints": {},
 "any_of": [],
 "requirements": [],
 "effective_term": null,
 "superseded_by": null,
 "extraction_method": {
  "scope": "site_default",
  "campus": "site_default",
  "superseded_by": "snapshot"
 }
}
```

