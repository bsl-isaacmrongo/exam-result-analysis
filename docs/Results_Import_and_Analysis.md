# Results import and analysis (CEM baseline + IB results)

This document describes how external results are imported and analysed, and
lists every assumption made while building it. It covers the **external**
data only: the CEM IBE baseline and the final IB DP/CP results. Internal
tracking (mocks, teacher predictions, IA predictions) and grade boundaries from
the [SRS](IB_Results_VA_System_SRS.docx) are not implemented yet.

Sample files used to build and test the flow:

- [CEM IBE Baseline.xlsx](CEM%20IBE%20Baseline.xlsx): CEM baseline and predictions
- [IB Results 2026.xlsx](IB%20Results%202026.xlsx): final IB results (`IBDP` and `IBCP` sheets)
- [BGE IB Analysis 2026.docx](BGE%20IB%20Analysis%202026.docx): the school's manual analysis that the dashboards reproduce

## 1. Flow

1. An **admin** opens **Data imports** in the dashboard
   (`/ib/<school>/imports`), picks the file type (CEM baseline or IB
   results), the year and the exam session (May / November), and uploads an
   `.xlsx` file.
2. The API parses and validates the whole workbook. If any value is invalid,
   nothing is saved and every problem is listed (FR-1.2). Otherwise the rows are
   stored as one *import*, together with a summary (counts and warnings).
3. Importing the same file type again for the same school and session
   **replaces** the earlier import. The two files can be imported in either
   order.
4. When any page asks for the analysis, the API loads that session's imports.
   It then:
   - matches IB students to CEM students by name
   - applies the IB award rules
   - calculates value added (VA)
   - aggregates everything for DP, CP and Combined

   Nothing derived is stored, so a re-import or rule change takes effect immediately.
5. The UI shows the results on **Overview** (KPIs and charts rendered with
   `ngx-echarts`) and **Student results** (per-student award status and VA).

```
Excel ──► parsers.py ──► result_imports / cem_* / ib_* tables
                                   │
                    request time   ▼
          matching.py ─► rules.py ─► analysis.py ─► /api/analysis/ib ─► Overview / Student results
```

## 2. Where the code is

| Part | Location |
| --- | --- |
| Tables | [api/app/models/results.py](../api/app/models/results.py), migration [20261105_02](../api/alembic/versions/20261105_02_create_result_imports.py) |
| Subject catalogue and labels | [subjects.py](../api/app/features/results/subjects.py) |
| Workbook parsing and validation | [parsers.py](../api/app/features/results/parsers.py) |
| Student name matching | [matching.py](../api/app/features/results/matching.py) |
| Core matrix and award conditions | [rules.py](../api/app/features/results/rules.py) |
| Statistics | [analysis.py](../api/app/features/results/analysis.py) |
| Endpoints | [router.py](../api/app/features/results/router.py) |
| API tests (use the sample workbooks) | [api/tests/test_results.py](../api/tests/test_results.py) |
| UI service and types | [ui/src/app/core/results/](../ui/src/app/core/results/) |
| Chart options (ECharts) | [chart-options.ts](../ui/src/app/shared/charts/chart-options.ts) |
| Pages | [imports](../ui/src/app/features/imports/), [overview](../ui/src/app/features/dashboard/overview/), [students](../ui/src/app/features/students/) |

The unused placeholder upload/analysis stubs (`features/uploads`,
`features/analysis/tasks.py`, `models/student_result.py`) were removed and
replaced by this feature.

## 3. Input files

### 3.1 CEM baseline

One sheet; the first row holds the headers; one row per student and subject.

| Column (header matched case-insensitively) | Accepted headers | Required | Example |
| --- | --- | --- | --- |
| Student name, `Last, First` | `StudentName`, `Student Name`, `Name`, `Student` | yes | `Abdirahman, Rahma` |
| Gender | `Gender`, `Sex` | no | `F` |
| Baseline (overall ability standard score) | `baseline`, `Overall`, `IBE`, `Overall ability`, `Score` | no | `84.58` |
| Subject | `Subject` | yes | `IB-S-French_ab_initio` |
| Predicted IB points | `CABTIC`, `Prediction`, `Predicted`, `Predicted points`, `Predicted grade` | yes | `5` |

- The subject must have the form `IB-H-<name>` (HL) or `IB-S-<name>` (SL).
- The subject name is mapped to the catalogue (section 5). Unknown subjects
  are kept, with a warning, but are not used for VA.
- `ab initio` in the name means the ab initio variant. `French_B` and
  `Spanish_B` are the language B variant.
- `Mathematics` without "analysis" or "applications" matches **both** AA and
  AI results.
- `Information Technology in a Global Socie…` (truncated by CEM) is mapped to
  **Digital Society**, which replaced ITGS.

### 3.2 IB results

Each sheet that contains a header row of subject abbreviations is read. The
sheet is treated as **CP** if its name contains `CP`, **DP** if it contains
`DP`, and otherwise as CP only when it has `BTEC` or `RP` columns.

- **Header row:** the row in the first 15 with the most known subject
  abbreviations (`Eng`, `Fre`, `Spa`, `Swa`, `Swe`, `Bus`, `Eco`, `His`,
  `Psy`, `DS`, `ESS`, `SEHS`, `Bio`, `Che`, `Phy`, `Mat`, `Art`, `Dra`).
  Headers may also include the level, e.g. `Bio HL`, `Fre Ab`, `Mat SL AI`.
- **Other columns** are found by their header in the header row, or in the row
  above for merged cells: `EE`, `TOK`, `EP` (core points), `Total`, `Notes`,
  `BTEC…` and `RP`.
- **EE:** in the sample, `EE` spans two columns, holding the EE subject
  (`Phy`) and then the grade (`C`).
- **Student rows:** column A is a number and there is a name before the first
  subject column. In the sample, column B is the first name and column C the
  last name.
- **Rows that are skipped:** summary rows such as *Average Points*,
  *Diploma %* and *CP Awarded*, and blank rows.
- **Non-numeric subject entries** such as `LD` or `Port` are kept as "other
  entries" without a grade, and a warning is added.

#### Level and variant from cell colours (assumption)

The sample workbook has no HL/SL column, so the level is read from the fill
colour of each grade cell. This legend was inferred from the sample; it
matches the counts in the school's report, for example Mat HL AA 3, Mat SL AA
20, Mat SL AI 9 and Fre Ab 5:

| Fill | Language B subjects (Fre, Spa, Swa) | Mathematics | Other subjects |
| --- | --- | --- | --- |
| None / white / theme colour | HL | HL **AA** | HL |
| Green (e.g. `92D050`) | SL | SL **AA** | SL |
| Yellow (e.g. `FFFF00`) | **ab initio** | SL **AI** | *unknown* |
| Any other colour | *unknown* | *unknown* | *unknown* |

Colours are classified by hue, so similar greens and yellows also work.

When the level is *unknown*, the import warns, and the analysis uses the level
of the matching CEM prediction. In the sample this happens once: Augustin
Maillard's Chemistry cell is light yellow, so CEM's `IB-S-Chemistry` gives SL.
If there is no CEM prediction, the subject is shown without a level.

A level written in the column header (e.g. `Bio HL`) always takes precedence
over the colour.

### 3.3 Validation

**Errors** reject the whole file and are listed, up to 50:

- not a valid `.xlsx` file
- missing required CEM columns
- a CEM subject not in the `IB-H-`/`IB-S-` format
- a CEM prediction that is not a number from 1 to 7
- an invalid baseline
- the same subject twice for one CEM student
- a subject grade that is not a whole number from 1 to 7
- an EE, TOK or RP grade that is not A–E
- core points that are not 0–3
- a total that is not 0–45
- no student rows

**Warnings** are kept with the import and shown in the history:

- unknown CEM subjects
- unknown levels
- duplicate names in a pathway
- non-numeric entries

Upload limits: `.xlsx`/`.xlsm` only, 5 MB maximum.

## 4. Matching students (assumption: no shared student ID)

The two files have no common student ID (the SRS expects one) and write names
differently, e.g. CEM `Abdirahman, Rahma` vs IB `Rahama Abdirahman`. Matching
is therefore done by name, one-to-one, every time the analysis runs:

1. **Normalise names:** remove accents, lowercase, drop apostrophes, split
   into words. A `?` (CEM exports lose accented characters, e.g.
   `J?r?me-Micka?l`) matches up to two characters.
2. **Surname:** a CEM student is a candidate only if at least one word of the
   CEM **last name** appears anywhere in the IB name. This copes with swapped
   or bracketed names such as `Aruna (Lwanzo)` and `(Michael) Tyler`.
3. **First name:** the remaining words are compared by similarity. A score of
   **0.8** or more (e.g. `Rahama`/`Rahma`) is a *confident* match.
4. **Pairing:** the best-scoring pairs are paired first, and each student is
   used only once.
5. **Surname-only match:** accepted only when it is unambiguous both ways, and
   flagged **for review**. Example: `Coco Monasch` ↔ `Charlotte Chipo
   Monasch`, a nickname.

Results with the sample files:

- 52 students matched (51 confident, 1 for review).
- **Lewis Ochola** and **Nathan Tassew** have no CEM record, so they have no
  VA, gender or baseline.
- Every CEM student is matched.

The Overview shows these lists, and Student results marks the affected
students *Review*.

Gender and baseline come from CEM only, because the IB results file has
neither. Unmatched students are therefore missing from gender and
baseline-band breakdowns.

## 5. Subject catalogue

| Key | Label | Name | Group | Variants |
| --- | --- | --- | --- | --- |
| eng | Eng | English A | 1 | — (Language & Literature and Literature are not distinguished) |
| swe | Swe | Swedish | 1 | — |
| fre | Fre | French | 2 | B (HL/SL), ab initio |
| spa | Spa | Spanish | 2 | B (HL/SL), ab initio |
| swa | Swa | Kiswahili | 2 | B (HL/SL), ab initio |
| bus | Bus | Business Management | 3 | — |
| eco | Eco | Economics | 3 | — |
| his | His | History | 3 | — |
| psy | Psy | Psychology | 3 | — |
| ds | DS | Digital Society (CEM: ITGS) | 3 | — |
| ess | ESS | Environmental Systems & Societies | 4 | — |
| sehs | SEHS | Sports, Exercise & Health Science | 4 | — |
| bio | Bio | Biology | 4 | — |
| che | Che | Chemistry | 4 | — |
| phy | Phy | Physics | 4 | — |
| mat | Mat | Mathematics | 5 | AA, AI |
| art | Art | Visual Arts | 6 | — |
| dra | Theatre | Theatre | 6 | — |
| mus | Mus | Music | 6 | — |

Labels follow the school's report, for example `Eng HL`, `Fre Ab`,
`Mat SL AI` and `Theatre HL`.

Assumptions:

- Kiswahili is treated as a language B subject.
- Swedish (school-supported self-taught) is group 1.
- ESS is group 4, although it is an interdisciplinary 3/4 subject.

## 6. Analysis rules

### 6.1 Value added

- **Subject VA = IB grade − CEM predicted points.** Predictions are used
  unrounded and VA is rounded to 2 decimals.
- **Which prediction is used:** one for the same subject. For languages, the
  ab initio/B variant must match. For Maths, AA/AI must match only when both
  sides specify it. A prediction at the **same level** is preferred;
  otherwise the other level's prediction is used (students sometimes change
  level after the baseline).
- **Proxy predictions:** when CEM has no prediction for the subject itself,
  another subject's prediction stands in (same level preferred), tried in
  this order:

  | Subject | Proxies |
  | --- | --- |
  | ESS | Biology |
  | Visual Arts | Theatre, then Music |
  | Theatre | Music, then Visual Arts |
  | Music | Theatre, then Visual Arts |

  If Music, Theatre and Visual Arts are all missing, any other subject in the
  same subject group (group 6) is used. The result's `predicted_from` names
  the stand-in (e.g. `Bio HL`) and the student view shows "via Bio HL".
  Rules live in `PROXIES` / `GROUP_FALLBACK` in
  [subjects.py](../api/app/features/results/subjects.py).
- **No prediction, no VA:** subjects with neither their own nor a proxy
  prediction have no VA. In the sample these are Kiswahili, Swedish, Visual
  Arts and Theatre (CEM has no arts predictions to stand in).
- **VA averages:** the mean of every subject result that has a VA. Student
  averages, subject averages and the cohort "average subject VA" all use this.
- **Significance threshold:** ±1.0 (`VA_THRESHOLD`, SRS 3.5). Charts draw it as
  dashed lines and tables colour values beyond it. KPI cards colour the cohort
  average beyond ±0.5.
- **Not calculated:** overall DP points VA (FR-3.2). The CEM file gives no
  predicted total, and the SRS leaves open whether to derive one (section 8,
  item 9).

### 6.2 DP: core points and Diploma

Core points come from the EE × TOK matrix in SRS 3.2 ([rules.py](../api/app/features/results/rules.py)).

- **Core points:** the file's `EP` value is used when present. If it differs
  from the matrix, the student gets a check note.
- **Total points:** the file's `Total` is used when present; otherwise
  subject points plus core points. A mismatch gives a check note.
- **Diploma:** awarded only if **no** condition below is triggered. The
  award is recalculated from the grades; the file's notes column is not used.

| Code | Diploma withheld if | Notes |
| --- | --- | --- |
| D0 | Fewer than 6 subject grades | Added; not in the SRS list |
| D1 | Total < 24 | |
| D2 | HL total < 12 (best three if four HL) | |
| D3 | SL total < 9 (< 6 with only two SL subjects) | As written in the SRS. The IB's own rule for two SL subjects is ≥ 5; confirm. |
| D4 | Any grade 1 | |
| D5 | Three or more grade 2s | |
| D6 | Four or more grades of 3 or lower | |
| D7 | E in TOK or EE | |
| D8 | CAS not completed | **Not evaluated**: CAS isn't in the file. Shown as "Not in imported data". |

Other DP items not implemented:

- **Bilingual Diploma (FR-2.5):** not evaluated (rules to confirm). The
  file's notes, e.g. "Bilingual Diploma", are shown as-is.
- **Course (certificate) candidates (FR-2.6):** not distinguished.

### 6.3 CP: certificate

| Code | Not awarded if | Data |
| --- | --- | --- |
| C1 | Fewer than two DP courses at grade 3+, or any grade 1 | From the results |
| C2 | Reflective Project grade E | The `RP` column; empty in the sample, so not checked |
| C3–C5 | PPS, Service Learning, Language Development | Not in the file, so not checked |
| C6 | Career-related study not passed | The `BTEC` column; *failed* only when it contains `U` or `Fail`. Missing means not checked. |

"Certificate rate" therefore means *meets every condition that can be checked
from the imported data*. Conditions that couldn't be checked are listed per
student.

### 6.4 Cohort and statistics

- **Cohort:** a candidate counts in a cohort only if they have at least one
  numeric subject grade. Students with no DP courses, such as the BTEC-only
  student in the sample (Atieno Tru Kerkering), are listed in Student results
  but left out of the statistics. Sample cohorts: **DP 32, CP 21, Combined 53**.
- **DP denominator:** all DP candidates, including those not awarded the
  Diploma. Pass rate 30/32 = **93.8%**.
- **Over 40 / over 35 points:** strictly greater than (`> 40`, `> 35`), as in
  the report. Sample: **9.4%** and **40.6%**.
- **Average points:** DP uses total points (sample 33.6; 34.3 for Diploma
  holders). CP uses the sum of DP course grades (12.4). Combined averages both
  (25.2), as in the report's "Student average".
- **Average subject grade:** the mean of all subject grades.
- **Share of each grade:** the % of all subject grades in the pathway at each
  grade from 7 to 1.
- **Uptake:** students taking a subject at that level ÷ pathway cohort, e.g.
  DP Eng HL 18/32 = 56%. CP uses the CP cohort, so it divides by the number of
  CP students, not a fixed 6 subjects.
- **Gender breakdowns:** use CEM gender, so unmatched students are excluded.
- **Baseline bands (residual matrix, FR-3.4):** fixed bands on the CEM standard
  score: < 90, 90–99, 100–109, 110–119, 120+. The SRS leaves the banding open
  (section 8, item 4).
- **Scatter (FR-7.2):** CEM baseline against DP total points, or against the
  CP average DP grade, with a least-squares trendline and r².
- **"All schools":** pools every IB school's imports for the session. Matching
  is still done within each school.

### 6.5 Verified against the school's report

[test_results.py](../api/tests/test_results.py) checks these figures from
the sample workbooks against [BGE IB Analysis 2026](BGE%20IB%20Analysis%202026.docx):

- Diploma rate 93.8%; over 40 points 9.4%; over 35 points 40.6%
- DP average 33.6, and 34.3 for Diploma holders
- CP average 12.4; Combined average 25.2
- DP grade shares 7–1: 10%, 34%, 36%, 15%, 4%, 1%, 0%
- DP uptake: Eng HL 56%, Mat SL AA 63%, Mat SL AI 9 students, Fre Ab 5 students
- Withheld Diplomas: K. Munene (D1, D2) and D. Raithatha (D2)

**Known differences.** Many subject VA averages differ from the report. The
report shows VA for subjects CEM doesn't predict (ESS, Kiswahili, Swedish,
Theatre, Art), so it must have used other predictions or proxies that aren't
in the CEM file. Its "Cum VA" (DP −0.19) is also defined differently: this
system's average subject VA for DP is −0.43. Confirm the intended definitions
(section 8).

## 7. Storage and API

### Tables

| Table | Contents |
| --- | --- |
| `result_imports` | One row per uploaded file: school, kind (`cem` / `ib_results`), year, session (`may` / `nov`), filename, summary (JSON), uploader, time. Unique per school + year + session + kind. |
| `cem_students` | One row per CEM student: first and last name, gender, baseline. |
| `cem_predictions` | One row per student and subject: raw CEM subject, catalogue key, level, variant, predicted points. |
| `ib_candidates` | One row per IB student: pathway, name, EE subject and grade, TOK grade, core points, total, RP grade, BTEC result, notes. |
| `ib_subject_results` | One row per student and subject: key, level (may be NULL), variant, grade (NULL for `LD` / `Port`), raw value. |

Deleting an import also deletes its rows. Schools are deleted with their
imports.

### Endpoints

| Method | Path | Who | Purpose |
| --- | --- | --- | --- |
| GET | `/api/imports?school=bge` | signed in | Import history, newest session first. `school=all` covers every IB school. |
| POST | `/api/imports` | admin | Multipart form: `school`, `kind`, `year`, `session`, `file`. Returns `201` with the summary, `422` with `{"detail": {"message", "errors": [...]}}`, or `413` if too large. |
| DELETE | `/api/imports/{id}` | admin | Removes an import. |
| GET | `/api/analysis/ib?school=bge[&year=2026&session=may]` | signed in | Analysis for a session; defaults to the latest session with IB results. `analysis` is `null` until IB results are imported. |

Imports are only accepted for a single school that offers the IB, not for
`all`.

## 8. Assumptions and open questions

| # | Assumption made | To confirm |
| --- | --- | --- |
| 1 | Students are matched by name (section 4); surname-only matches are flagged | Add a student ID to both exports (SRS FR-1.1) |
| 2 | Cell colours encode the level and variant (3.2) | Add explicit level columns or headers such as `Bio HL` |
| 3 | `Eng` is English A; Language & Literature and Literature are not distinguished | Whether the report needs both |
| 4 | Maths HL is always AA (the colour legend has no HL AI) | Whether any student takes Maths HL AI |
| 5 | No VA without a CEM prediction for the same subject; no proxies | How the report got VA for ESS, Kiswahili, Swedish, Theatre and Art |
| 6 | The other level's prediction is used if the student changed level | Or should VA be left blank? |
| 7 | VA uses unrounded CEM predictions; overall DP VA is not calculated | SRS item 9: derive a predicted total? |
| 8 | VA threshold ±1.0 for subjects | SRS item 3 |
| 9 | Fixed baseline bands for the residual matrix | SRS item 4 |
| 10 | D3 uses "< 6 with two SL subjects" as written in the SRS | The IB rule is ≥ 5 |
| 11 | D0 is added for fewer than 6 subject grades | Keep or drop |
| 12 | CAS, CP PPS, Service Learning and Language Development are not in the files, so not checked | Whether they will be supplied |
| 13 | BTEC is failed only when it contains `U` or `Fail` | Provider grade scales (SRS item 6) |
| 14 | The Bilingual Diploma is not evaluated | SRS item 1 |
| 15 | The baseline is the CEM IBE overall score; no (I)GCSE alternative or school percentile | SRS items 2 and 8 |
| 16 | Students with no DP courses are excluded from the statistics | Or report them separately? |
| 17 | Average VA is the mean over all subject results with a VA | The report's "Cum VA" definition |
| 18 | The year and session come from the upload form, not the file | — |
| 19 | Importing again replaces the previous file for that school, session and type | — |
| 20 | Only admins import or delete; every signed-in user can view | — |

## 9. Not implemented yet

- Internal tracking imports: mocks, IA predictions, teacher targets and
  predicted grades. These cover PG accuracy and teacher-target VA (FR-3.3,
  FR-4.3, FR-4.4).
- Grade boundaries and the near-boundary flag (FR-6.1, FR-6.2).
- CEM section scores (Vocabulary, Maths, Non-verbal) and CEM chances data
  (FR-3.9, FR-6.3); the sample file only has the overall score.
- EAL, SEN and ethnicity filters (FR-5.1); these fields aren't in the files.
- Multi-year trends (FR-6.4). Several sessions can be imported and selected,
  but there are no trend charts yet.
- The printable student snapshot (FR-7.4).
- Rules stored as editable configuration: they are constants in
  [rules.py](../api/app/features/results/rules.py).
