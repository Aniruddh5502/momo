---
name: reporting
description: Use this skill instructions when you want to write a report, when the user tells you to write a report, analysis, notes that need detail.
---

# STEPS
## 1. Collect Context
Before you start writing gather massive amounts of context on each aspect you want to cover in the report. From experiments results, research, paper summary.

Write supporting document to gather context if needed. which needs to be cleared after writing down the final report.

## Structuring
First write the structure of the report in the final report document. Never write the whole document at one tool call. Avoid any extra formatting other than Hashtags as anchors.

EX: First write to report.md
```text
# TITLE 1

## SUBTITLE 1

## SUBTITLE 2

.
.
.

## CONCLUSION
```

## Details filling loop
Take Each section/subsection and use the *edit tool* to edit and fill in details. Use the SUBTITLE name as old str and then the SUBTITLE + details you want to include as new_str.

Continue this loop till all the sections, subsections as been filled with details.

## Verification
Ask these questions before you finalize a report.
- [ ] If someone without the context you have read this report, would he understand it? If not then simplify
- [ ] Does the language seems easy for anyone to understand? If not edit them to make them easier to understand.
- [ ] Does the report qualify all the aspects to fill details that the user asked?
- [ ] Does the document uses any other formatting syntaxes other than hashtags? like **highlight**, `single coma`, "double coma", *italic*. then remove them and use plain string.
If the report doesn't pass any one of these criterias then you need to fix those aspects.