"""
Stage 1 — Title & Abstract Screening
AngioVision Systematic Review (PRISMA)

Backend: ollama Python library  (no separate `ollama serve` required)
         Install:  pip install ollama
         Model:    ollama pull qwen3.8:27b

Two-call architecture per paper:
  Call 1 — Inclusion gate  (I1–I4, ALL must be YES)
  Call 2 — Exclusion gate  (E1–E3, ANY one triggers exclusion)
           Skipped when Call 1 already rejects the paper.

Final decision logic:
  inclusion_pass=False                          → EXCLUDE  (failed_at=inclusion)
  inclusion_pass=True  & exclusion_pass=False   → EXCLUDE  (failed_at=exclusion)
  inclusion_pass=True  & exclusion_pass=True    → INCLUDE
  Either call is UNCERTAIN                      → UNCERTAIN (treated as failed at I1)

Fixes applied (v2):
  - Model kept loaded in VRAM via keep_alive="120m" on every ollama.chat() call
  - _preload_model() warms up the model before the main loop (eliminates cold-start
    empty responses on the first record of each run)
  - RETRY_DELAY reduced 5s → 2s (cold start eliminated; shorter wait is sufficient)
  - Abstract truncated to ABSTRACT_MAX_LEN chars before sending (prevents context overflow
    silently producing empty responses on very long abstracts)

Fixes applied (v3):
  - UNCERTAIN rows (both new and already-processed) are normalised to
    failed_at=inclusion, failed_criteria=["I1"] for consistent downstream counting.
  - Summary now reports # articles that passed ALL inclusion criteria (I1–I4).
  - Criteria summary CSV includes a new "n_passed_all_inclusion" row.

Usage:
    python3 03_stage1_screening.py
    python3 03_stage1_screening.py --input records.csv --output stage1_results.csv

Input CSV columns (all retained in output):
    record_id, source, title, authors, year, journal_venue, doi, url,
    abstract, screen_decision, screen_reason, notes

Added columns (LLM output, merged into input):
    llm_decision, llm_failed_at,
    llm_inclusion_pass, llm_inclusion_criteria, llm_inclusion_reason,
    llm_exclusion_pass, llm_exclusion_criteria, llm_exclusion_reason,
    llm_flag_for_human_review, llm_raw_inclusion, llm_raw_exclusion
"""

# Shared helpers — see slrlib/ (was duplicated inline; slrlib/test_slrlib.py proves parity)
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))
from slrlib import ensure as _ensure, extract_json as _extract_json

# ── Auto-install dependencies ─────────────────────────────────────────────────
import subprocess
import sys

_ensure("ollama")
_ensure("pandas")
_ensure("tqdm")
_ensure("tabulate")

# ── Imports ───────────────────────────────────────────────────────────────────
import os
import re
import json
import time
import argparse
import logging
import pandas as pd
import ollama
from tqdm import tqdm
from tabulate import tabulate
from collections import defaultdict

# ── Config ────────────────────────────────────────────────────────────────────
MODEL            = "qwen3.8:27b"   # the model both full runs used; --model still overrides
TEMPERATURE      = 0
MAX_TOKENS       = 128      # YES/NO map only; was 2048 when a free-text reason was returned
RETRY_LIMIT      = 2
RETRY_DELAY      = 2          # FIX: reduced from 5s — cold start eliminated by keep_alive
REPAIR_LIMIT     = 2
KEEP_ALIVE       = "120m"     # FIX: keep model loaded in VRAM for the full run
THINK            = False      # thinking models: reasoning tokens cost ~5x time, verdict is unaffected
ABSTRACT_MAX_LEN = 5000       # FIX: truncate abstracts to avoid context overflow → empty response

INPUT_COLUMNS = [
    "record_id", "source", "title", "authors", "year",
    "journal_venue", "doi", "url", "abstract",
    "screen_decision", "screen_reason", "notes",
]

LLM_COLUMNS = [
    "llm_decision",
    "llm_failed_at",                # "inclusion" | "exclusion" | "none" | "error"
    "llm_inclusion_pass",           # True / False / UNCERTAIN
    "llm_inclusion_criteria",       # JSON dict {"met": [...], "failed": [...]}
    "llm_inclusion_reason",
    "llm_exclusion_pass",           # True / False / UNCERTAIN / SKIPPED
    "llm_exclusion_criteria",       # JSON list of triggered E-codes
    "llm_exclusion_reason",
    "llm_flag_for_human_review",
    "llm_raw_inclusion",
    "llm_raw_exclusion",
]

CRITERIA_LABELS = {
    "I1": "I1 — Angiographic modality",
    "I2": "I2 — Temporal sequence",
    "I3": "I3 — In-scope computational task",
    "I4": "I4 — Evaluation against data",
    "E1": "E1 — Not a full-length publication",
    "E2": "E2 — Non-research document type",
    "E3": "E3 — Not in English",
}

# Derived from CRITERIA_LABELS so summary tables can never drift from the
# criteria actually in use (they were hard-coded as I1-I4 / E1-E5 before).
INCLUSION_CODES = [c for c in CRITERIA_LABELS if c.startswith("I")]
EXCLUSION_CODES = [c for c in CRITERIA_LABELS if c.startswith("E")]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("stage1.log")],
)
log = logging.getLogger(__name__)


# ── System prompts ────────────────────────────────────────────────────────────

INCLUSION_SYSTEM = """You are a systematic review assistant performing the INCLUSION gate.
Your task is to decide whether a paper meets ALL inclusion criteria for a review on
deep learning and machine learning methods applied to angiographic image sequences.

Answer every criterion YES or NO. There is no uncertain option. Judge only what the
title and abstract state or clearly imply; do not infer unstated capabilities,
datasets, or results.

Every criterion ends with a DEFAULT line stating the answer to give when the text
does not address that criterion. Apply the default rather than guessing. The
defaults are set so that silence keeps a record in the review, because a wrongly
retained record is corrected at full-text screening while a wrongly excluded
record is never seen again.


INCLUSION CRITERIA (ALL four must be YES to pass):

I1. Angiographic modality.
Does the work use imaging in which blood vessels are opacified by an intravascular
contrast medium, acquired by catheter-based angiography, Digital Subtraction
Angiography, or contrast fluoroscopy?
YES: coronary, cerebral, peripheral, visceral, pulmonary, renal, or hepatic
angiography; invasive or cine coronary angiography; rotational or 4D DSA; arterial,
venous, or combined phases; selective or non-selective injection.
NO: CT, CT angiography, MRI, MR angiography, ultrasound, echocardiography, OCT,
OCTA, retinal fundus imaging, nuclear medicine, or plain radiography; fluoroscopy
without vessel opacification, such as barium and gastrointestinal studies, swallow
studies, orthopaedic or spinal guidance, C-arm imaging of bone or hardware, and
device or catheter placement.
This criterion asks only about modality. Do not consider frame count, task, or method.
DEFAULT: if the modality is named only as "angiography" or "angiographic" with no
further detail, answer YES.

I2. Temporal sequence.
Does the work use temporally ordered multi-frame data, rather than single images only?
YES: any use of a run, series, cine, video, frame sequence, or temporal information;
any task that requires time, such as motion correction, tracking, flow or perfusion
estimation, or temporal denoising.
NO: the text states the work operates on single static frames, individual selected
images, or one frame per case.
This criterion asks only about the temporal dimension. Do not consider modality,
task, or method.
DEFAULT: if frame count, temporality, the mention of time, the mention of order, the mention of sequences are not mentioned, answer NO.

I3. In-scope computational task.
Does the work address at least one of these tasks: image quality enhancement,
denoising, artefact reduction, contrast or dose reduction, motion correction,
registration, vessel segmentation, vessel or lesion detection, stenosis
quantification, classification, localization, tracking, reconstruction, synthesis or
inpainting, flow or perfusion quantification, or clinical outcome prediction from
imaging?
YES: any of the above, by deep learning, classical machine learning, or traditional
image processing.
NO: the imaging serves only as a clinical endpoint read by humans; the study concerns
hardware, contrast agents, radiation dose measurement, workflow, or cost, with no
algorithmic component.
This criterion asks only what task is performed. Do not consider who developed the
method or whether it was evaluated.
DEFAULT: if the work is described as automated, AI-based, or computational without
naming a task, answer YES.

I4. Evaluation against data.
Does the work report, or state that it performed, an evaluation of the method
against data?
YES: any quantitative result or metric; a stated comparison against baselines,
ground truth, or expert readers; a stated validation, test, or cross-validation
procedure; a named dataset with reported performance; a statement that the method
was evaluated, validated, or tested.
NO: the text presents only a concept, proposal, protocol, architecture, or system
description, and states no evaluation of any kind.
This criterion asks only whether an evaluation occurred. Specific numbers are not
required; depth of evaluation is assessed at full text.
DEFAULT: if no evaluation is mentioned either way, answer NO.

Decision rules:
- "pass": ALL four criteria are YES.
- "fail": At least one criterion is NO. List the failing criterion/criteria.

Respond ONLY with this JSON object. Every value is exactly "YES" or "NO".
Output nothing else: no preamble, no markdown fences, no explanation, no extra keys.

{"I1":"YES","I2":"YES","I3":"YES","I4":"YES"}

Rules:
- Answer each of I1 to I4 with the single word YES or NO, nothing more.
- Never write a sentence, a reason, or any text outside this JSON object.
- Every criterion has a DEFAULT. Use it. Never answer with anything but YES or NO."""

EXCLUSION_SYSTEM = """You are a systematic review assistant performing the EXCLUSION gate.
The paper has already passed the inclusion gate. Your task is to check whether any
exclusion criterion applies and the paper should be rejected.

These criteria test properties of the PUBLICATION itself, not its content. Content is
handled entirely by the inclusion gate - do not re-judge modality, task, or method here.

Answer every criterion YES or NO. There is no uncertain option. Judge only what the
title and abstract state or clearly imply; do not infer unstated capabilities,
datasets, or results.

Every criterion ends with a DEFAULT line stating the answer to give when the text
does not address that criterion. Apply the default rather than guessing. The
defaults are set so that silence keeps a record in the review, because a wrongly
retained record is corrected at full-text screening while a wrongly excluded
record is never seen again.

EXCLUSION CRITERIA (ANY one YES excludes the record):

E1. Not a full-length publication.
Is the record a conference abstract, meeting abstract, poster, or extended abstract
published without a full methods section?
YES: titles beginning "Abstract No."; publication in a meeting supplement; a length
of one to two pages.
NO: full peer-reviewed conference papers, including MICCAI, SPIE Medical Imaging,
ISBI, IPCAI, and CVPR proceedings, which are in scope; journal articles of any length.
DEFAULT: if publication form is not indicated, answer NO.

E2. Non-research document type.
Is the record an editorial, commentary, letter, correspondence, reply, opinion,
viewpoint, perspective, narrative or systematic review, case report, correction,
erratum, retraction notice, or withdrawal notice?
YES: the title or abstract identifies the record as one of these forms.
NO: research articles, methods papers, benchmarking and comparison studies, and
validation studies, including those containing a literature survey.
DEFAULT: if document type is not indicated, answer NO.

E3. Not in English.
Is the full text unavailable in English?
YES: the record states a non-English full text.
NO: an English abstract with a complete English full text; non-English author names,
affiliations, or institutions.
DEFAULT: if language is not indicated, answer NO.

Decision rules:
- "pass": NO exclusion criteria triggered - paper survives the exclusion gate.
- "fail": At least one exclusion criterion is YES. List the triggering criterion/criteria.

Respond ONLY with this JSON object. Every value is exactly "YES" or "NO".
Output nothing else: no preamble, no markdown fences, no explanation, no extra keys.

{"E1":"NO","E2":"NO","E3":"NO"}

Rules:
- Answer each of E1 to E3 with the single word YES or NO, nothing more.
- YES means the exclusion criterion applies and the record is excluded.
- Never write a sentence, a reason, or any text outside this JSON object.
- Every criterion has a DEFAULT. Use it. Never answer with anything but YES or NO."""

REPAIR_SYSTEM = """You are a JSON repair assistant. You will be given a broken or empty response
that was supposed to be a JSON object. Return ONLY the corrected JSON object.
No preamble, no markdown fences, no explanation."""


# ── UNCERTAIN normalisation ───────────────────────────────────────────────────

def _normalise_uncertain_row(row: dict) -> dict:
    """
    If llm_decision == 'UNCERTAIN', rewrite the row so it is treated uniformly
    as: failed at inclusion gate, failed criterion = I1.

    Applied both to freshly-screened rows (in _screen_paper) and to rows
    already persisted in the output CSV (in _reprocess_uncertain_in_existing).
    """
    if str(row.get("llm_decision", "")).upper() != "UNCERTAIN":
        return row

    row = dict(row)  # shallow copy so we don't mutate the caller's dict

    # Parse existing inc_criteria so we can overwrite only the "failed" key
    try:
        existing = json.loads(row.get("llm_inclusion_criteria") or "{}")
        if not isinstance(existing, dict):
            existing = {}
    except (json.JSONDecodeError, TypeError):
        existing = {}

    # Keep whatever was already marked as met, but force failed → ["I1"]
    met = existing.get("met", [])
    # Remove I1 from met if it was mistakenly listed there
    met = [c for c in met if c != "I1"]

    row["llm_decision"]           = "UNCERTAIN"          # keep label for transparency
    row["llm_failed_at"]          = "inclusion"           # normalised
    row["llm_inclusion_pass"]     = "UNCERTAIN"           # keep for human review signal
    row["llm_inclusion_criteria"] = json.dumps({"met": met, "failed": ["I1"]})
    row["llm_flag_for_human_review"] = True

    return row


# ── Helpers ───────────────────────────────────────────────────────────────────

def _repair_json(broken_raw, system_prompt, title, abstract):
    user_content = (
        f"The following response was supposed to be valid JSON but is broken or empty.\n\n"
        f"BROKEN RESPONSE:\n{broken_raw if broken_raw else '(empty)'}\n\n"
        f"ORIGINAL PAPER:\nTitle: {title}\nAbstract: {abstract}\n\n"
        f"Please return the correct JSON object for this paper."
    )
    options = ollama.Options(temperature=0, num_predict=MAX_TOKENS)
    for attempt in range(1, REPAIR_LIMIT + 1):
        try:
            response = ollama.chat(
                model=MODEL,
                messages=[
                    {"role": "system", "content": REPAIR_SYSTEM + "\n\n" + system_prompt},
                    {"role": "user",   "content": user_content},
                ],
                format="json",
                options=options,
                keep_alive=KEEP_ALIVE,
            think=THINK,
            )
            raw = response.message.content.strip()
            parsed = _extract_json(raw)
            if parsed:
                log.info(f"  JSON repair succeeded on attempt {attempt}.")
                return parsed, raw
            log.warning(f"  Repair attempt {attempt}/{REPAIR_LIMIT}: still not valid JSON.")
        except Exception as e:
            log.warning(f"  Repair attempt {attempt}/{REPAIR_LIMIT}: error — {e}")
        time.sleep(RETRY_DELAY)
    return None, ""


def _call_gate(gate_name, system_prompt, title, abstract):
    """
    Generic LLM call for a single gate (inclusion or exclusion).
    Returns (parsed_dict, raw_str) or (None, last_raw) on total failure.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": f"/no_think\n\nTitle: {title}\n\nAbstract: {abstract}"},
    ]
    options  = ollama.Options(temperature=TEMPERATURE, num_predict=MAX_TOKENS)
    last_raw = ""

    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            response = ollama.chat(
                model=MODEL,
                messages=messages,
                format="json",
                options=options,
                keep_alive=KEEP_ALIVE,
            think=THINK,
            )
            raw = response.message.content.strip()
            if not raw:
                log.warning(f"  [{gate_name}] Attempt {attempt}/{RETRY_LIMIT}: empty response.")
                last_raw = raw
                time.sleep(RETRY_DELAY)
                continue
            parsed = _extract_json(raw)
            if parsed:
                return parsed, raw
            log.warning(f"  [{gate_name}] Attempt {attempt}/{RETRY_LIMIT}: JSON parse error | raw={raw[:120]}")
            last_raw = raw
            time.sleep(RETRY_DELAY)
        except ollama.ResponseError as e:
            log.warning(f"  [{gate_name}] Attempt {attempt}/{RETRY_LIMIT}: ResponseError — {e}")
            last_raw = ""
            time.sleep(RETRY_DELAY)
        except Exception as e:
            log.warning(f"  [{gate_name}] Attempt {attempt}/{RETRY_LIMIT}: Unexpected error — {e}")
            last_raw = ""
            time.sleep(RETRY_DELAY)

    log.warning(f"  [{gate_name}] All {RETRY_LIMIT} attempts failed. Attempting JSON repair...")
    parsed, repair_raw = _repair_json(last_raw, system_prompt, title, abstract)
    if parsed:
        return parsed, f"[REPAIRED] {repair_raw}"

    log.error(f"  [{gate_name}] JSON repair failed.")
    return None, last_raw


# ── Model preload ─────────────────────────────────────────────────────────────

def _preload_model():
    """
    Send a dummy request before the main loop so the model is fully loaded
    into VRAM before the first real record arrives. Eliminates the cold-start
    empty response pattern seen on attempt 1 of each run.
    """
    log.info(f"Preloading model '{MODEL}' into VRAM (keep_alive={KEEP_ALIVE})...")
    try:
        response = ollama.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user",   "content": "Reply with the single word: ok"},
            ],
            options=ollama.Options(temperature=0, num_predict=8),
            keep_alive=KEEP_ALIVE,
            think=THINK,
        )
        raw = response.message.content.strip()
        log.info(f"Model preloaded successfully. Warm-up response: {raw[:60]}")
    except Exception as e:
        log.warning(f"Preload failed (non-fatal, will continue): {e}")


# ── Two-call screening ────────────────────────────────────────────────────────

def _yesno_to_gate(parsed, codes, gate):
    """Convert a flat {"I1":"YES",...} answer into the legacy gate keys.

    The prompts now return only YES/NO per criterion, which cuts output from
    ~800 tokens to ~30 and removes free text entirely. Downstream code still
    reads pass / triggered_criteria / failed_criteria / reason, so they are
    derived here and the rest of the script is unchanged.

    Also resolves the contradiction seen on the 10-record smoke, where a
    criterion came back in both the met and failed lists: an explicit NO always
    wins over a YES for the same code.
    """
    if parsed is None:
        return None
    answers = {}
    for c in codes:
        v = parsed.get(c, parsed.get(c.lower()))
        if isinstance(v, bool):
            answers[c] = v
        elif isinstance(v, str):
            answers[c] = v.strip().upper().startswith("Y")
        else:
            answers[c] = None                 # criterion absent from the reply

    yes = [c for c in codes if answers[c] is True]
    no  = [c for c in codes if answers[c] is False]
    missing = [c for c in codes if answers[c] is None]

    if gate == "inclusion":
        # inclusion passes only when every criterion is YES
        out = {"pass": not no and not missing,
               "triggered_criteria": yes,
               "failed_criteria": no}
    else:
        # exclusion: any YES excludes, so the gate passes when none are YES
        out = {"pass": not yes,
               "triggered_criteria": yes,
               "failed_criteria": []}
    out["uncertain"] = False
    out["reason"] = ""
    # a criterion the model failed to answer is exactly the case a human should see
    out["flag_for_human_review"] = bool(missing)
    if missing:
        out["reason"] = "no answer for: " + ",".join(missing)
    return out


def _screen_paper(title, abstract):
    """
    Run inclusion gate then (conditionally) exclusion gate.
    Abstract is truncated before sending to avoid context overflow.
    Returns a dict with all LLM_COLUMNS fields populated.
    UNCERTAIN results are normalised via _normalise_uncertain_row().
    """
    abstract = abstract[:ABSTRACT_MAX_LEN]

    # ── CALL 1: Inclusion gate ────────────────────────────────────
    log.info(f"  [inclusion] calling model...")
    inc_parsed, inc_raw = _call_gate("inclusion", INCLUSION_SYSTEM, title, abstract)
    inc_parsed = _yesno_to_gate(inc_parsed, INCLUSION_CODES, "inclusion")

    if inc_parsed is None:
        row = {
            "llm_decision":              "ERROR",
            "llm_failed_at":             "inclusion",
            "llm_inclusion_pass":        "ERROR",
            "llm_inclusion_criteria":    "{}",
            "llm_inclusion_reason":      "LLM call failed after all retries",
            "llm_exclusion_pass":        "SKIPPED",
            "llm_exclusion_criteria":    "[]",
            "llm_exclusion_reason":      "",
            "llm_flag_for_human_review": True,
            "llm_raw_inclusion":         inc_raw,
            "llm_raw_exclusion":         "",
        }
        return row  # ERROR rows are not UNCERTAIN — skip normalisation

    inc_pass      = bool(inc_parsed.get("pass", False))
    inc_uncertain = bool(inc_parsed.get("uncertain", False))
    inc_triggered = inc_parsed.get("triggered_criteria", [])
    inc_failed    = inc_parsed.get("failed_criteria", [])
    inc_reason    = inc_parsed.get("reason", "")
    inc_flag      = bool(inc_parsed.get("flag_for_human_review", False))

    inc_criteria_store = json.dumps({
        "met":    inc_triggered,
        "failed": inc_failed,
    })

    # Early exit if inclusion fails or uncertain
    if not inc_pass or inc_uncertain:
        decision  = "UNCERTAIN" if inc_uncertain else "EXCLUDE"
        failed_at = "inclusion (uncertain)" if inc_uncertain else "inclusion"
        log.info(f"  [inclusion] → {decision} | failed: {inc_failed}")
        row = {
            "llm_decision":              decision,
            "llm_failed_at":             failed_at,
            "llm_inclusion_pass":        "UNCERTAIN" if inc_uncertain else False,
            "llm_inclusion_criteria":    inc_criteria_store,
            "llm_inclusion_reason":      inc_reason,
            "llm_exclusion_pass":        "SKIPPED",
            "llm_exclusion_criteria":    "[]",
            "llm_exclusion_reason":      "Skipped — paper did not pass inclusion gate",
            "llm_flag_for_human_review": inc_flag,
            "llm_raw_inclusion":         inc_raw,
            "llm_raw_exclusion":         "",
        }
        # Normalise UNCERTAIN → failed at I1
        return _normalise_uncertain_row(row)

    log.info(f"  [inclusion] → PASS | met: {inc_triggered}")

    # ── CALL 2: Exclusion gate ────────────────────────────────────
    log.info(f"  [exclusion] calling model...")
    exc_parsed, exc_raw = _call_gate("exclusion", EXCLUSION_SYSTEM, title, abstract)
    exc_parsed = _yesno_to_gate(exc_parsed, EXCLUSION_CODES, "exclusion")

    if exc_parsed is None:
        return {
            "llm_decision":              "ERROR",
            "llm_failed_at":             "exclusion",
            "llm_inclusion_pass":        True,
            "llm_inclusion_criteria":    inc_criteria_store,
            "llm_inclusion_reason":      inc_reason,
            "llm_exclusion_pass":        "ERROR",
            "llm_exclusion_criteria":    "[]",
            "llm_exclusion_reason":      "LLM call failed after all retries",
            "llm_flag_for_human_review": True,
            "llm_raw_inclusion":         inc_raw,
            "llm_raw_exclusion":         exc_raw,
        }

    exc_pass      = bool(exc_parsed.get("pass", False))
    exc_uncertain = bool(exc_parsed.get("uncertain", False))
    exc_triggered = exc_parsed.get("triggered_criteria", [])
    exc_reason    = exc_parsed.get("reason", "")
    exc_flag      = bool(exc_parsed.get("flag_for_human_review", False))

    exc_criteria_store = json.dumps(exc_triggered)

    if exc_uncertain:
        log.info(f"  [exclusion] → UNCERTAIN | triggered: {exc_triggered}")
        row = {
            "llm_decision":              "UNCERTAIN",
            "llm_failed_at":             "exclusion (uncertain)",
            "llm_inclusion_pass":        True,
            "llm_inclusion_criteria":    inc_criteria_store,
            "llm_inclusion_reason":      inc_reason,
            "llm_exclusion_pass":        "UNCERTAIN",
            "llm_exclusion_criteria":    exc_criteria_store,
            "llm_exclusion_reason":      exc_reason,
            "llm_flag_for_human_review": True,
            "llm_raw_inclusion":         inc_raw,
            "llm_raw_exclusion":         exc_raw,
        }
        # Exclusion-stage uncertain also normalised to failed at I1
        return _normalise_uncertain_row(row)

    if not exc_pass:
        log.info(f"  [exclusion] → EXCLUDE | triggered: {exc_triggered}")
        return {
            "llm_decision":              "EXCLUDE",
            "llm_failed_at":             "exclusion",
            "llm_inclusion_pass":        True,
            "llm_inclusion_criteria":    inc_criteria_store,
            "llm_inclusion_reason":      inc_reason,
            "llm_exclusion_pass":        False,
            "llm_exclusion_criteria":    exc_criteria_store,
            "llm_exclusion_reason":      exc_reason,
            "llm_flag_for_human_review": exc_flag,
            "llm_raw_inclusion":         inc_raw,
            "llm_raw_exclusion":         exc_raw,
        }

    # Both gates passed → INCLUDE
    log.info(f"  [exclusion] → PASS | no exclusion criteria triggered")
    return {
        "llm_decision":              "INCLUDE",
        "llm_failed_at":             "none",
        "llm_inclusion_pass":        True,
        "llm_inclusion_criteria":    inc_criteria_store,
        "llm_inclusion_reason":      inc_reason,
        "llm_exclusion_pass":        True,
        "llm_exclusion_criteria":    exc_criteria_store,
        "llm_exclusion_reason":      exc_reason,
        "llm_flag_for_human_review": inc_flag or exc_flag,
        "llm_raw_inclusion":         inc_raw,
        "llm_raw_exclusion":         exc_raw,
    }


# ── Reprocess UNCERTAIN rows in an existing output CSV ───────────────────────

def _reprocess_uncertain_in_existing(output_path: str) -> int:
    """
    Read the output CSV, apply _normalise_uncertain_row() to every UNCERTAIN row,
    write back in place, and return the count of rows that were updated.

    Called at the start of screen_records() (before new screening begins) so that
    rows processed in previous runs are also corrected.
    """
    if not os.path.exists(output_path):
        return 0

    df = pd.read_csv(output_path)
    uncertain_mask = df["llm_decision"].astype(str).str.upper() == "UNCERTAIN"
    n_uncertain    = uncertain_mask.sum()

    if n_uncertain == 0:
        return 0

    log.info(f"Normalising {n_uncertain} UNCERTAIN rows in existing output → failed at I1...")
    updated_rows = []
    for _, row in df[uncertain_mask].iterrows():
        updated_rows.append(_normalise_uncertain_row(row.to_dict()))

    updated_df = pd.DataFrame(updated_rows)
    df.loc[uncertain_mask, updated_df.columns.tolist()] = updated_df.values
    df.to_csv(output_path, index=False)
    log.info(f"  {n_uncertain} UNCERTAIN rows normalised and written back to {output_path}.")
    return n_uncertain


# ── Included titles export ────────────────────────────────────────────────────

def _save_included_titles(df, output_path):
    results_dir = os.path.dirname(output_path) or "."
    txt_path    = os.path.join(results_dir, "stage1_included.txt")
    included    = df[df["llm_decision"] == "INCLUDE"].copy()

    if included.empty:
        log.info("  No INCLUDE records found — skipping stage1_included.txt.")
        return

    def _is_flagged(val):
        if isinstance(val, bool): return val
        if isinstance(val, str):  return val.strip().lower() in ("true", "1", "yes")
        try:                      return bool(val)
        except Exception:         return False

    included["_flagged"] = included["llm_flag_for_human_review"].apply(_is_flagged)
    lines = []
    for _, row in included.iterrows():
        title  = str(row.get("title", "")).strip() or "(no title)"
        suffix = "  [Need-to-Check]" if row["_flagged"] else ""
        lines.append(f"{title}{suffix}")

    with open(txt_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    flagged_count = included["_flagged"].sum()
    msg = (f"  Included titles saved to: {txt_path}  "
           f"({len(lines)} total, {flagged_count} flagged [Need-to-Check])")
    log.info(msg)
    print(msg + "\n")


# ── Summary ───────────────────────────────────────────────────────────────────

def _print_summary(output_path):
    df = pd.read_csv(output_path)

    # ── Re-normalise any UNCERTAIN rows in the loaded dataframe ──
    # (guards against a summary-only run on an old CSV that wasn't normalised)
    uncertain_mask = df["llm_decision"].astype(str).str.upper() == "UNCERTAIN"
    if uncertain_mask.any():
        updated_rows = []
        for _, row in df[uncertain_mask].iterrows():
            updated_rows.append(_normalise_uncertain_row(row.to_dict()))
        updated_df = pd.DataFrame(updated_rows)
        df.loc[uncertain_mask, updated_df.columns.tolist()] = updated_df.values

    def _tbl(rows, headers):
        print()
        print(tabulate(rows, headers=headers, tablefmt="simple_outline"))
        print()

    def parse_json_col(val):
        try:
            result = json.loads(val) if pd.notna(val) else []
            return result if isinstance(result, list) else []
        except Exception:
            return []

    def parse_inc_criteria(val):
        try:
            obj = json.loads(val) if pd.notna(val) else {}
            if isinstance(obj, dict):
                return obj.get("met", []), obj.get("failed", [])
            return [], []
        except Exception:
            return [], []

    df["year"] = pd.to_numeric(df["year"], errors="coerce")

    print("\n" + "=" * 60)
    print("  STAGE 1 SUMMARY  (two-gate architecture)")
    print("=" * 60)

    # ── 1. Overall decision counts ────────────────────────────────
    decision_rows = []
    for decision, count in df["llm_decision"].value_counts().items():
        pct = 100 * count / len(df)
        decision_rows.append([decision, count, f"{pct:.1f}%"])
    flags = int(df["llm_flag_for_human_review"].astype(str).str.lower().isin(["true", "1"]).sum())
    decision_rows.append(["Flagged for review", flags, f"{100*flags/len(df):.1f}%"])
    _tbl(decision_rows, ["Decision", "Count", "% of total"])

    # ── 2. Failure stage breakdown ────────────────────────────────
    print("─" * 60)
    print("  WHERE DID EXCLUSIONS FAIL?")
    print("─" * 60)
    excluded = df[df["llm_decision"] == "EXCLUDE"]
    if not excluded.empty:
        fail_rows = []
        for stage, count in excluded["llm_failed_at"].value_counts().items():
            pct = 100 * count / len(excluded)
            fail_rows.append([stage, count, f"{pct:.1f}% of excluded"])
        _tbl(fail_rows, ["Failed at", "Count", "% of excluded"])
    else:
        print("  No EXCLUDE records.\n")

    # ── 3. Inclusion gate — criteria breakdown ────────────────────
    print("─" * 60)
    print("  INCLUSION GATE — CRITERIA BREAKDOWN")
    print("─" * 60)

    inc_met_counts    = defaultdict(int)
    inc_failed_counts = defaultdict(int)

    # Track how many articles had ALL inclusion criteria met
    # (llm_inclusion_pass is True, i.e., not False / UNCERTAIN / ERROR / SKIPPED)
    all_inc_passed_set = set()   # record_ids where ALL I1-I4 were met

    for idx, row in df.iterrows():
        met, failed = parse_inc_criteria(row.get("llm_inclusion_criteria", "{}"))
        for c in met:
            inc_met_counts[c] += 1
        for c in failed:
            inc_failed_counts[c] += 1

        # An article passed ALL inclusion criteria iff llm_inclusion_pass is True
        # (the string "True" from CSV, or boolean True)
        inc_pass_val = str(row.get("llm_inclusion_pass", "")).strip().lower()
        if inc_pass_val in ("true", "1"):
            all_inc_passed_set.add(row.get("record_id", idx))

    n_passed_all_inclusion = len(all_inc_passed_set)
    pct_all_inc = 100 * n_passed_all_inclusion / len(df) if len(df) else 0

    inc_rows = []
    for c in INCLUSION_CODES:
        label = CRITERIA_LABELS.get(c, c).split("—", 1)[-1].strip()
        inc_rows.append([c, label, inc_met_counts[c], inc_failed_counts[c]])
    _tbl(inc_rows, ["ID", "Description", "# Met", "# Failed"])

    # Report articles passing ALL inclusion criteria
    print("─" * 60)
    print("  ARTICLES PASSING ALL FOUR INCLUSION CRITERIA (I1–I4)")
    print("─" * 60)
    _tbl(
        [[n_passed_all_inclusion, f"{pct_all_inc:.1f}%", len(df)]],
        ["# Passed All Inclusion", "% of total", "Total records"],
    )

    # ── 4. Exclusion gate — criteria breakdown ────────────────────
    print("─" * 60)
    print("  EXCLUSION GATE — TRIGGERED CRITERIA BREAKDOWN")
    print("─" * 60)

    exc_triggered_counts = defaultdict(int)
    exc_gate_df = df[df["llm_exclusion_pass"].astype(str).str.upper() != "SKIPPED"]

    for _, row in exc_gate_df.iterrows():
        for c in parse_json_col(row.get("llm_exclusion_criteria", "[]")):
            exc_triggered_counts[c] += 1

    exc_rows = []
    for c in EXCLUSION_CODES:
        label = CRITERIA_LABELS.get(c, c).split("—", 1)[-1].strip()
        exc_rows.append([c, label, exc_triggered_counts[c]])
    _tbl(exc_rows, ["ID", "Description", "# Triggered"])

    # ── 5. Year range by decision ─────────────────────────────────
    print("─" * 60)
    print("  YEAR RANGE BY DECISION")
    print("─" * 60)
    year_valid = df["year"].dropna()
    if year_valid.empty:
        print("  No year data available.\n")
    else:
        year_rows = [["ALL", int(year_valid.min()), int(year_valid.max()),
                      int(year_valid.median()), len(year_valid)]]
        for decision in ["INCLUDE", "EXCLUDE", "UNCERTAIN", "ERROR"]:
            subset = df[df["llm_decision"] == decision]["year"].dropna()
            if not subset.empty:
                year_rows.append([decision, int(subset.min()), int(subset.max()),
                                  int(subset.median()), len(subset)])
        _tbl(year_rows, ["Decision", "Min year", "Max year", "Median", "n"])

    print("=" * 60)

    # ── 6. Criteria summary CSV ───────────────────────────────────
    criteria_rows = []

    # Inclusion criteria rows
    for c in INCLUSION_CODES:
        criteria_rows.append({
            "criterion":                 c,
            "description":               CRITERIA_LABELS[c],
            "type":                      "inclusion",
            "n_met":                     inc_met_counts[c],
            "n_failed":                  inc_failed_counts[c],
            "n_triggered":               "",
            "n_passed_all_inclusion":    "",
        })

    # Summary row: articles that passed ALL inclusion criteria
    criteria_rows.append({
        "criterion":                 "I1-I4 (ALL)",
        "description":               "Articles passing ALL inclusion criteria",
        "type":                      "inclusion_summary",
        "n_met":                     "",
        "n_failed":                  "",
        "n_triggered":               "",
        "n_passed_all_inclusion":    n_passed_all_inclusion,
    })

    # Exclusion criteria rows
    for c in EXCLUSION_CODES:
        criteria_rows.append({
            "criterion":                 c,
            "description":               CRITERIA_LABELS[c],
            "type":                      "exclusion",
            "n_met":                     "",
            "n_failed":                  "",
            "n_triggered":               exc_triggered_counts[c],
            "n_passed_all_inclusion":    "",
        })

    criteria_path = output_path.replace(".csv", "_criteria_summary.csv")
    pd.DataFrame(criteria_rows).to_csv(criteria_path, index=False)
    print(f"  Criteria summary CSV saved to: {criteria_path}\n")

    _save_included_titles(df, output_path)


# ── Main screening loop ───────────────────────────────────────────────────────

def screen_records(input_path, output_path, resume=True):
    df = pd.read_csv(input_path)

    required = {"record_id", "title", "abstract"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(f"Input CSV is missing required columns: {missing}")

    for col in INPUT_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    done_ids = set()
    if resume and os.path.exists(output_path):
        # Normalise any UNCERTAIN rows from previous runs before continuing
        n_normalised = _reprocess_uncertain_in_existing(output_path)
        if n_normalised:
            log.info(f"  Normalised {n_normalised} pre-existing UNCERTAIN rows → failed at I1.")

        done_df  = pd.read_csv(output_path)
        done_ids = set(done_df["record_id"].astype(str))
        log.info(f"Resuming: {len(done_ids)} records already processed.")
    else:
        done_df = pd.DataFrame(columns=INPUT_COLUMNS + LLM_COLUMNS)

    pending  = df[~df["record_id"].astype(str).isin(done_ids)]
    new_rows = []

    # Warm up the model before the loop so the first record never hits a cold model
    _preload_model()

    with tqdm(total=len(pending), desc="Screening", unit="record",
              bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]") as pbar:

        for _, row in pending.iterrows():
            rec_id   = str(row["record_id"])
            # NaN must become "" — str(nan) is "nan", which was being sent to the
            # model as the abstract text for every record that has none.
            title    = "" if pd.isna(row.get("title"))    else str(row.get("title",    "")).strip()
            abstract = "" if pd.isna(row.get("abstract")) else str(row.get("abstract", "")).strip()

            if not title and not abstract:
                log.warning(f"record_id={rec_id}: empty title & abstract — skipping.")
                pbar.update(1)
                continue

            pbar.set_postfix_str(title[:55], refresh=True)

            llm_out   = _screen_paper(title, abstract)
            # judged from the title alone: exactly the case a human should re-check
            if not abstract:
                llm_out["llm_flag_for_human_review"] = True
            decision  = llm_out.get("llm_decision", "?")
            failed_at = llm_out.get("llm_failed_at", "?")

            status_str = decision
            if decision == "EXCLUDE":
                status_str = f"EXCLUDE [{failed_at}]"
            pbar.set_postfix_str(f"{title[:40]}… → {status_str}", refresh=True)

            out_row = {col: row.get(col, pd.NA) for col in INPUT_COLUMNS}
            out_row.update(llm_out)
            new_rows.append(out_row)

            batch_df = pd.DataFrame(new_rows, columns=INPUT_COLUMNS + LLM_COLUMNS)
            combined = pd.concat([done_df, batch_df], ignore_index=True)
            combined.to_csv(output_path, index=False)

            pbar.update(1)

    log.info(f"\nDone. Results written to: {output_path}")
    _print_summary(output_path)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    global MODEL

    parser = argparse.ArgumentParser(
        description="Stage 1 — Title & Abstract Screening (two-gate: inclusion then exclusion)"
    )
    parser.add_argument("--input",        default="results/slr_stage1_screening.csv",
                        help="Path to input CSV")
    parser.add_argument("--output",       default="results/stage1_results.csv",
                        help="Path to output CSV")
    parser.add_argument("--model",        default=MODEL,
                        help=f"Ollama model name (default: {MODEL})")
    parser.add_argument("--no-resume",    action="store_true",
                        help="Start fresh, ignore existing output")
    parser.add_argument("--summary-only", action="store_true",
                        help="Skip screening, just re-print summary from existing output")
    args = parser.parse_args()

    MODEL = args.model

    if args.summary_only:
        if not os.path.exists(args.output):
            print(f"Error: output file '{args.output}' not found.")
            sys.exit(1)
        _print_summary(args.output)
    else:
        screen_records(args.input, args.output, resume=not args.no_resume)


if __name__ == "__main__":
    main()