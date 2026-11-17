# Email settings (Steps 6 and 7)

Status: DRAFT

<!--
HOW THIS FILE IS USED
- The AI does NOT write the email. It only suggests hook quotes from the company's own pages.
  Plain code checks each hook, then fills in the template below. You control every other word.
- Hook rules (in code): copied word for word from a scraped page of the company, 4 to 30 words,
  no funding words, no negative news, no menu / button / image text. Preferred topics when several
  pass: customers, security, compliance, enterprise, hiring, countries, global.
  No hook = no email ("no hook found").
- Aim for about 80-100 words in total. The page shows the word count of every draft.
- TEST ONLY runs get "[TEST ONLY] " in front of the subject automatically.
- Sending: Resend, from onboarding@resend.dev, ONLY to your own TO_EMAIL, plain text, on the exact
  typed command "send <domain>, hook <n>". Never to the contact. Never twice. 3 per day.
- While Status is DRAFT, drafting and sending work only on TEST ONLY runs. Change it to APPROVED
  (and fill in your name below) when you are happy with the wording.

Placeholders you can use in subject and body:
  {first_name}    contact's first name (from Hunter)
  {company}       company name (from the company picture)
  {hook}          the chosen hook quote
  {role_people}   who you talk to, by role group (set below)
  {pain_sentence} built from the pain points (set below)
  {sender_name} {sender_title}
-->

```settings
sender_name: [Your name]
sender_title: Growth, Sprinto
role_people_S: security and compliance leads
role_people_C: engineering leaders
role_people_F: founders
pain_one: one thing comes up a lot: {p1}.
pain_two: two things come up a lot: {p1}, and {p2}.
```

```subject
{company} and audit readiness
```

```body
Hi {first_name},

I was on {company}'s website and this line stood out: "{hook}"

When I talk to {role_people}, {pain_sentence}

Sprinto automates evidence collection and audit prep for SOC 2, ISO 27001 and similar frameworks, so teams stay audit-ready without the scramble.

Is this on your plate this quarter? A one-line reply is plenty.

{sender_name}
{sender_title}
```
