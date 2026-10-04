# Zotero collection criteria

<!--
An example criteria file for Settings → Where to send → "By criteria file (Claude)".
Copy it (for example to zotero_criteria.md), choose that file in Settings, and edit it.

- One line per Zotero collection, named exactly as in Zotero.
- Indent subcollections by two spaces under their parent.
- "- Name: criterion" → Claude puts papers that fit the criterion into this collection.
- "- Name" (no criterion) → not filled automatically (parent or excluded folder).
- Collection keys are not needed. Only if several collections share a name and the path
  does not tell them apart (or the name contains a colon), add the key in square brackets:
  "- Korea [ABCD1234]: ...". The key is in the address bar of the Zotero web library.
- Text inside these comment marks is ignored.
-->

- 00_Inbox

- 01_Research
  - Educational inequality: studies in which educational attainment or achievement is the dependent variable and family background, gender, or race is the main independent variable
    - Korea: studies of educational inequality in South Korea
  - Returns to education: studies in which education is the independent variable and wages, earnings, or income are the dependent variable
  - Family formation: studies in which marriage, cohabitation, childbearing, or partner choice is the dependent variable
  - Low fertility: studies whose main motivation is to explain low fertility
  - Text analysis: studies that use text-as-data methods (topic models, word embeddings, LLM-based coding)
  - Dissertation references

- 02_Teaching
  - Research methods
    - Experiments: studies about or using field, survey, or lab experiments
    - Measurement: studies about operationalization, measurement, and scales
  - Causal inference
    - Instrumental variables: studies about IV methods or using IV as the main identification strategy
    - Difference-in-differences: studies about DiD or event-study designs, or using them as the main method
    - Regression discontinuity: studies about RD designs or using RD as the main method
