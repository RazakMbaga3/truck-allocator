# Prompt: Create Branded User Guide Document
### Instructions for producing the formatted Nyati Cement user guide

---

## How to Use This Prompt

Copy everything inside the **PROMPT** section below and paste it into a new Claude conversation (claude.ai). Paste the full contents of `USER_GUIDE.md` where indicated. Claude will return a complete, formatted, brand-compliant document you can paste into Word, Google Docs, or send to a designer.

---

## PROMPT

---

You are a professional technical writer and document designer for Lake Cement Limited, trading as **Nyati Cement**, based in Tanzania. Your task is to take raw user guide content and transform it into a polished, publication-ready document that follows the Nyati Cement brand guidelines exactly.

---

### BRAND GUIDELINES

**Company:** Lake Cement Limited (Nyati Cement)
**Country:** Tanzania
**Plant:** Kimbiji Plant, Kigamboni, Dar es Salaam
**Language:** Professional English with occasional Swahili terms where natural (e.g. greetings in the cover, "Karibu" on the intro page)
**Tagline:** *Nguvu ya Kujenga Tanzania* ("The Strength to Build Tanzania")

**Colour Palette:**
- Deep Navy: `#173158` — use for headings, headers, borders, and section dividers
- Brand Orange: `#F49545` — use for callout boxes, highlights, key figures, and accent elements
- Brand Green: `#239557` — use for success states, positive KPIs, "confirmed" indicators
- Alert Red: `#dc2626` — use only for warnings and urgent items
- Light Grey Background: `#f9fafb` — use for table zebra rows and info panels
- White: `#ffffff` — page background and card backgrounds
- Body text: `#111827` (near black)
- Secondary text / captions: `#6b7280`

**Typography:**
- Document title: Bold, 28pt, Deep Navy (`#173158`)
- Chapter headings (H2): Bold, 18pt, Deep Navy, with a 3pt left border in Brand Orange
- Section headings (H3): Bold, 13pt, Deep Navy
- Body text: Regular, 11pt, `#111827`, line-height 1.6
- Table headers: Bold, 10pt, white text on Deep Navy background
- Captions and notes: Italic, 9pt, `#6b7280`
- Callout boxes: 10pt, `#854d0e` text on `#fef3cd` amber background for warnings; white text on Deep Navy for tips
- Monospace (URLs, references): Courier New or Consolas, 10pt

**Logo placement:** Top-right of cover page and top-right header on every page. Use text representation "NYATI CEMENT | LAKE CEMENT LIMITED" if the image cannot be embedded.

**Document feel:** Corporate but approachable. This is an internal operational tool guide, not a marketing brochure. Tone is confident, clear, and direct — written for logistics staff who are practical people, not technology specialists.

---

### DOCUMENT STRUCTURE TO PRODUCE

Create a complete document with the following structure. Do not skip any section.

**1. COVER PAGE**
- Title: "Smart Return Truck Allocator"
- Subtitle: "User Guide for Logistics Operations"
- Company: Lake Cement Limited (Nyati Cement)
- Location: Kimbiji Plant · Kigamboni, Dar es Salaam, Tanzania
- Document version: May 2026 · Version 1.0
- Classification: Internal Use Only
- Visual: A horizontal rule in Brand Orange (#F49545) separating the title block from the footer
- Footer: "Nguvu ya Kujenga Tanzania"

**2. DOCUMENT INFORMATION PAGE**
Include a small table:
| Field | Detail |
|-------|--------|
| Document Title | Smart Return Truck Allocator — User Guide |
| Prepared For | Logistics Dispatchers, Transport Management Team |
| Prepared By | Digital Team, Lake Cement Limited |
| Review Date | May 2026 |
| Classification | Internal Use Only |
| Version | 1.0 |

Add a one-paragraph "About This Document" note explaining that this guide covers the daily use of the Smart Return Truck Allocator system, which is accessed via a web browser at the plant. It does not cover system administration or Odoo configuration.

**3. TABLE OF CONTENTS**
Numbered chapters matching the guide sections below.

**4. CHAPTER 1 — INTRODUCTION**
- What the system does (business context)
- The financial benefit explained simply
- Who uses it (role table)
- How to access the system (URL, browser requirements)

**5. CHAPTER 2 — SCHEDULE PAGE**
Full explanation of the Schedule tab — KPI cards, truck table columns, all status codes (two separate tables: Truck Status and Allocation Status), and all actions (sync Odoo, mark arrived, add truck details).

**6. CHAPTER 3 — PROPOSALS PAGE**
Full explanation of proposals — the three variants with a visual description of their colour coding, the AI advisory panel, how to confirm, how to reject, force re-match.

**7. CHAPTER 4 — CONFIRMED ALLOCATIONS PAGE**
KPI cards, the allocation table, month selector, and CSV export.

**8. CHAPTER 5 — HOW THE MATCHING WORKS**
The four scoring factors in plain language (table format). The corridor reference table. The rules for when an order is eligible.

**9. CHAPTER 6 — DAILY WORKFLOW**
The dispatcher cheat sheet formatted as a step-by-step numbered list, split into Morning / During the Day / End of Day. Put this in a visually distinct callout box with a Deep Navy header.

**10. CHAPTER 7 — TROUBLESHOOTING**
All common situations formatted as a two-column table: "Situation" and "What to Do".

**11. QUICK REFERENCE CARD (last page)**
A single-page summary designed to be printed and kept at the dispatcher's desk. Include:
- The three proposal variants and what they optimise
- All status codes (brief)
- The daily workflow steps (condensed)
- System URL and support contact
- Nyati Cement brand footer

---

### FORMATTING RULES

1. Every chapter must start with a one-sentence chapter summary in italics under the heading, in Brand Orange (#F49545), before the body text begins.
2. All tables must have Deep Navy (#173158) header rows with white bold text.
3. Alternate table rows should use #f9fafb light grey for readability.
4. Status code values (EXPECTED, PRE_CONFIRMED, etc.) must be styled in monospace, bold, surrounded by a subtle grey box — like a code badge.
5. Important notes must be in a yellow callout box (background #fef3cd, border-left 4px solid #f5c842).
6. Tips and best practices must be in a navy callout box (background #eef2f8, border-left 4px solid #173158).
7. Financial figures (TZS amounts) must always be in Brand Orange (#F49545) and bold.
8. The Quick Reference Card chapter must be clearly demarcated with a full-width horizontal rule and a note "This page is designed for printing."
9. Page numbers in footer: "Page X of Y · Smart Return Truck Allocator · Internal Use Only"
10. Chapter numbers must appear in Brand Orange in the heading, e.g. "**01** Introduction"

---

### SOURCE CONTENT

Transform the following raw user guide content into the structured, formatted document described above. Preserve all factual information exactly — do not invent features or change any numbers. You may rephrase for clarity and professionalism, but every table, workflow step, and technical detail from the source must appear somewhere in the output.

[PASTE THE FULL CONTENTS OF USER_GUIDE.md HERE]

---

### OUTPUT FORMAT

Produce the document in one of these formats — ask the user which they prefer before generating:

**Option A — Rich Markdown**
Full Markdown with HTML colour tags where needed for brand colours. Suitable for pasting into Notion, GitHub, or a Markdown-to-PDF converter.

**Option B — HTML**
A self-contained HTML file with embedded CSS using the exact brand colours. Can be opened in any browser and printed to PDF directly. Recommended for best visual fidelity.

**Option C — Word-ready structured text**
Clean structured text with explicit formatting instructions in brackets (e.g. `[HEADING 2 — Deep Navy]`) that a Word user can apply with styles. Suitable for teams who work in Microsoft Word.

---

*End of prompt.*

---

## Tips for Best Results

- **For a PDF:** Choose Option B (HTML), open in Chrome, then File → Print → Save as PDF. Set margins to 2 cm all around.
- **For Word:** Choose Option C, paste into Word, then apply the Nyati heading styles. Use the colour codes above to set up custom styles once.
- **For Notion or Confluence:** Choose Option A. The HTML colour tags (`<span style="color:#F49545">`) will render in most rich-text editors.
- **To update the guide later:** Edit `USER_GUIDE.md` first, then re-run this prompt with the updated content. The document structure stays the same.
- **Adding screenshots:** After generating the document, take screenshots of the live dashboard (http://localhost:8001) and insert them into the relevant chapters. Recommended shots: the Schedule table with trucks visible, one Proposals page showing all three variant cards, the Confirmed page KPI cards, and the Quick Reference Card printed view.
