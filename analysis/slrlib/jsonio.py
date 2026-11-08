"""JSON / JSONL helpers shared by the pipeline scripts."""
import json
import re


def extract_json(text):
    """Pull the first JSON object out of an LLM response.

    Copied verbatim from _extract_json in 03_stage1_screening.py (identical in
    04/05/07). Handles bare JSON, a fenced json block, and a JSON object
    embedded in surrounding prose.
    """
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def load_jsonl(path):
    """Read a .jsonl file into a list, silently skipping unparseable lines.

    Lenient variant (was in 06_claim2024_checklist_graph and
    analysis/07_claim_side_by_side_comparison).
    """
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def iter_jsonl(path):
    """Stream a .jsonl file, raising on a malformed line.

    Strict generator variant (was in analysis/04_task-archi,
    analysis/05_forest_plot_binary_analysis, analysis/d_02_forest_plot).
    Kept separate from load_jsonl: those callers rely on lazy iteration and on
    a bad line being an error, not a silent skip.
    """
    with open(path, "r") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)
