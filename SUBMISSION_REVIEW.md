# Computers in Biology and Medicine submission review

Reviewed against the author-provided `guide.pdf` (saved 26 October 2026). Base manuscript: `6114100` ("re-review left"). The author subsequently approved technical fixes and minimal spelling and grammar corrections in the saved submission questionnaire. The abstract and AI disclosure remain reserved for author revision. This is a submission-format review, not certification of the scientific methods or results.

## Applied changes

- Retained the requested dual affiliations for Khan and Filkov and suppression of the generic preprint footer in PR #11.
- Added the missing `blei2003latent` bibliography entry without editing the citation or surrounding text. Metadata verified at https://www.jmlr.org/papers/v3/blei03a.html.
- Matched the supplementary title to the manuscript title.
- Updated Table S2 to the current objectives (1.3), extraction (2.3.4), limitations (4.3), and conclusion (4.4) sections. Replaced obsolete appendix references with the data availability statement and public repository. Distinguished CLAIM-informed reporting completeness from risk of bias.
- Clarified that human validation used 491 records and that the nearly 90% cardiac/neurologic share describes included studies. All five highlights remain within 85 characters.

## Remaining author revisions

1. **Abstract (`00-main.tex`, abstract):** approximately 265 whitespace-delimited words; the guide sets a maximum of 250. Shorten before submission. The entire paragraph was edited in `6114100`; it has not been changed here.
2. **AI disclosure (`00-main.tex`, final declaration):** the latest author wording mentions Claude assistance but omits OpenAI Codex assistance with manuscript editing and code. The guide requires disclosure of generative AI used in manuscript preparation. Supplement this account accurately before submission; existing author wording has not been changed. The guide's example heading is "Declaration of generative AI and AI-assisted technologies in the manuscript preparation process."
## Follow-up decisions and corrections

- The author selected technical fixes and minimal spelling and grammar corrections by retaining one option per question in the saved editor document.
- Fixed the anatomy figure reference and converted unsupported punctuation in Recurrent Theme Extraction to LaTeX equivalents.
- Corrected spelling, agreement, punctuation, and the limitations sequence (First, Second, Finally), without changing numbers, scientific claims, section structure, or citations.
- Updated Table S2 registration/protocol locations to Section 4.3, where these statements currently appear.
- The author confirmed all authors have approved author order, the dual affiliations for Khan and Filkov, CRediT contributions, funding, and competing-interest details.
- The author will shorten the abstract and revise the AI disclosure personally. Elsevier's declarations document is not yet prepared.

## Files and portal actions

- Upload editable LaTeX sources, bibliography, and all required figure/dependency files; a PDF alone is not an acceptable source submission.
- Upload `highlights.txt` separately (five bullets, each at most 85 characters).
- Upload the compiled supplementary material (`00_supplementary_file.pdf` in the repository root) separately with a concise caption; the guide says supplementary files are published as supplied.
- Complete Elsevier's declarations tool even when there are no competing interests; upload its resulting Word document (.doc or .docx). This is separate from the manuscript declaration.
- Enter the approved author details in the submission portal. Confirm corresponding-author contact details and any required third-party permissions during submission; author approval of the listed metadata and declarations was reported by the author.
- Upload `graphical_abstract.pdf` as the separate graphical abstract (vector PDF); `graphical_abstract.png` is a 3900 x 1500 pixel (13:5) preview. Rebuild with `python3 analysis/11_graphical_abstract.py`. The graphic summarizes 120 studies, 12 gaps, four clusters and 14 mitigation strategies; overlapping circles are schematic, not proportional set sizes.
- An ethics statement now explains that approval and consent were not required for this review of published literature without recruitment or collection of identifiable individual-level data.
- A graphical abstract is encouraged, not mandatory. Double-column LaTeX is permitted. Seven keywords are within the allowed range. A data availability statement and funding statement are already present.

## Verification

Main manuscript and supplement compile successfully with Tectonic. The missing bibliography citation resolves. Title-page rendering and the updated checklist were visually checked. The follow-up builds pass with no duplicate-label, missing-glyph, or undefined citation/reference warnings. The corrected methods/results pages and supplementary checklist were visually checked. Existing box warnings remain elsewhere; compilation success does not mean the manuscript is submission-ready. Complete the remaining author revisions and declarations document before submission.
