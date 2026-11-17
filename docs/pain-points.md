# Pain points (Step 5)

Status: DRAFT

<!--
HOW THIS FILE IS USED
- The tool picks up to 2 pain points for the contact's role group:
    S = security / CISO / compliance / GRC   (Hunter rule 1)
    C = CTO / head of engineering            (Hunter rule 2)
    F = founder                              (Hunter rule 3)
- These are TYPICAL challenges for the role. They are never stated as facts about the company.
- "needs evidence" rows are used ONLY when the company picture has a quoted page fact of that kind:
    cert_in_progress  = the site says a certification is in progress
    compliance_job    = an open security / compliance / GRC / risk / audit job
    team_size         = the site states a team size
  Rows marked "-" can always be used.
- Order matters: usable "needs evidence" rows come first, then the rest top to bottom.
- "email phrase" is dropped into the email as is, so keep it short and lower-case.
- While Status is DRAFT, this list is only used on TEST ONLY runs. Change it to APPROVED when happy.
- F5 was deleted in the old project. Keep ids stable; do not reuse a deleted id.
-->

| id | group | needs evidence | pain point (typical for the role) | email phrase |
|----|-------|----------------|-----------------------------------|--------------|
| S1 | S | - | Audit evidence is collected by hand: screenshots, spreadsheets and chasing control owners. | collecting audit evidence by hand |
| S2 | S | - | Each new framework (SOC 2, ISO 27001, GDPR) means redoing overlapping work. | repeating the same work for every new framework |
| S3 | S | - | Controls drift between audits and gaps show up only when the auditor arrives. | controls drifting between audits |
| S4 | S | - | Security questionnaires from enterprise buyers eat up the team's week. | the pile of security questionnaires from enterprise buyers |
| S5 | S | compliance_job, cert_in_progress | A small team carries the whole compliance load while also hiring or chasing a certification. | carrying the compliance load while the team is still growing |
| C1 | C | - | Compliance work pulls engineers off the product roadmap. | compliance work pulling engineers off the roadmap |
| C2 | C | - | Enterprise deals stall on security reviews. | enterprise deals stalling on security reviews |
| C3 | C | - | Access reviews, offboarding and cloud settings are kept audit-ready by hand. | keeping access reviews and cloud settings audit-ready by hand |
| C4 | C | team_size, cert_in_progress | As the team grows, access and device policies get harder to keep consistent. | keeping access and device policies consistent as the team grows |
| C5 | C | - | Audit prep turns into a scramble before every audit window. | the scramble before every audit window |
| F1 | F | - | Enterprise customers ask for SOC 2 or ISO 27001 before they sign. | enterprise customers asking for SOC 2 or ISO 27001 before signing |
| F2 | F | cert_in_progress | A first certification takes months and pulls in senior people. | a first certification taking months of senior time |
| F3 | F | - | Compliance costs (consultants, auditors, tools) are hard to predict. | compliance costs that are hard to predict |
| F4 | F | team_size, compliance_job | Hiring a full-time compliance person is expensive at this stage. | the cost of a full-time compliance hire at this stage |
