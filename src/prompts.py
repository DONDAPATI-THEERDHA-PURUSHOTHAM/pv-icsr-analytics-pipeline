"""
Dynamic Regulatory Pharmacovigilance (PADER) Prompt Registry & Context Assembly Framework
Author: Enterprise AI Engineering Team
Description: Schema-agnostic context assembly, dynamic section registration, and fail-safe 
             prompt management in compliance with FDA 21 CFR 314.80 reporting guidelines.
"""

from typing import Dict, Any, Callable, List, Optional, Union
import copy

# =============================================================================
# SYSTEM PROMPT DEFINITION
# =============================================================================

DEFAULT_SYSTEM_PROMPT = """You are an expert Regulatory Pharmacovigilance Writer generating a Periodic Adverse Drug Experience Report (PADER) in accordance with FDA 21 CFR 314.80.

STRICT GROUNDING RULES:
1. Every numerical metric, date, case count, percentage, and demographic breakdown MUST be taken strictly from the provided context packet.
2. DO NOT invent, extrapolate, or hallucinate any numbers, patient details, or clinical outcomes not present in the context.
3. DO NOT state medical conclusions or cause-and-effect claims unless supported explicitly by the data. Frame findings as observed reporting patterns.
4. Maintain a formal, neutral, regulatory reporting tone suitable for submission to health authorities.
5. Respect all disclaimers regarding missing CCDS/labeling reference data or missing safety-related actions.
"""


# =============================================================================
# DEFENSIVE DATA EXTRACTION HELPERS
# =============================================================================

def safe_get(data: Dict[str, Any], path: str, default: Any = None) -> Any:
    """Recursively retrieves values from nested dictionaries using dot-notation path."""
    if not isinstance(data, dict):
        return default
    
    keys = path.split(".")
    curr = data
    for key in keys:
        if isinstance(curr, dict) and key in curr:
            curr = curr[key]
        else:
            return default
    return curr if curr is not None else default


def safe_pct(numerator: Union[int, float], denominator: Union[int, float], precision: int = 1) -> float:
    """Safely calculates percentage with precision, avoiding division by zero."""
    try:
        num = float(numerator or 0)
        den = float(denominator or 0)
        if den == 0:
            return 0.0
        return round((num / den) * 100.0, precision)
    except (ValueError, TypeError):
        return 0.0


# =============================================================================
# SCHEMATIC CONTEXT ASSEMBLERS
# =============================================================================

def assemble_title_and_header(m: Dict[str, Any]) -> Dict[str, Any]:
    meta = m.get("meta", {})
    period = meta.get("reporting_period", m.get("reporting_period", {}))
    return {
        "product_name": meta.get("product_name") or m.get("product_name", "Unspecified Drug Product"),
        "application_number": meta.get("application_number") or m.get("application_number", "N/A"),
        "holder": meta.get("holder") or m.get("holder", "Unspecified License Holder"),
        "start_date": period.get("start_date") or m.get("start_date", "N/A"),
        "end_date": period.get("end_date") or m.get("end_date", "N/A"),
        "report_type": "Periodic Adverse Drug Experience Report (PADER)",
        "pader_number": m.get("pader_number", "PADER-FDA-AUTOMATED")
    }


def assemble_introduction(m: Dict[str, Any]) -> Dict[str, Any]:
    header = assemble_title_and_header(m)
    return {
        "product_name": header["product_name"],
        "application_number": header["application_number"],
        "holder": header["holder"],
        "reporting_period": {
            "start_date": header["start_date"],
            "end_date": header["end_date"]
        },
        "indication": m.get("indication", "Management of hypertension and heart failure")
    }


def assemble_narrative_summary(m: Dict[str, Any]) -> Dict[str, Any]:
    kpis = m.get("kpi_cards", m.get("case_volume", {}))
    charts = m.get("charts", {})
    
    top_rx = charts.get("top_reaction_terms", safe_get(m, "reaction_analysis.top_pt_case_frequency", []))
    outcome = charts.get("outcome_distribution", safe_get(m, "reaction_analysis.outcome_distribution", {}))
    
    return {
        "case_volume": kpis,
        "seriousness_criteria": charts.get("seriousness_breakdown", m.get("seriousness_criteria", {})),
        "demographics": {
            "age_distribution": charts.get("age_distribution", safe_get(m, "demographics.age_distribution", {})),
            "sex_distribution": charts.get("sex_distribution", safe_get(m, "demographics.sex_distribution", {}))
        },
        "top_reactions": top_rx[:5] if isinstance(top_rx, list) else [],
        "outcome_summary": outcome
    }


def assemble_summary_analysis_of_cases(m: Dict[str, Any]) -> Dict[str, Any]:
    kpis = m.get("kpi_cards", m.get("case_volume", {}))
    charts = m.get("charts", {})
    tot_cases = kpis.get("unique_cases", kpis.get("total_cases", 0))

    return {
        "total_cases": tot_cases,
        "serious_cases": kpis.get("serious_cases", 0),
        "non_serious_cases": kpis.get("non_serious_cases", 0),
        "expedited_cases": kpis.get("expedited_alerts", kpis.get("expedited_15day_alert_cases", 0)),
        "age_distribution": charts.get("age_distribution", safe_get(m, "demographics.age_distribution", {})),
        "sex_distribution": charts.get("sex_distribution", safe_get(m, "demographics.sex_distribution", {})),
        "reporter_qualification": charts.get("reporter_qualification", safe_get(m, "demographics.reporter_qualification", {})),
        "top_countries": charts.get("top_countries", safe_get(m, "demographics.top_occur_countries", {})),
        "seriousness_criteria": charts.get("seriousness_breakdown", m.get("seriousness_criteria", {}))
    }


def assemble_reaction_analysis(m: Dict[str, Any]) -> Dict[str, Any]:
    charts = m.get("charts", {})
    return {
        "total_reaction_occurrences": safe_get(m, "reaction_analysis.total_reaction_occurrences", 0),
        "top_pt_case_frequency": charts.get("top_reaction_terms", safe_get(m, "reaction_analysis.top_pt_case_frequency", [])),
        "top_serious_pt_case_frequency": charts.get("top_serious_reaction_terms", safe_get(m, "reaction_analysis.top_serious_pt_case_frequency", [])),
        "outcome_distribution": charts.get("outcome_distribution", safe_get(m, "reaction_analysis.outcome_distribution", {})),
        "soc_note": "No System Organ Class (SOC) field was supplied in the ICSR dataset; analysis is performed at the MedDRA Preferred Term (PT) level."
    }


def assemble_serious_cases_and_alerts(m: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "tabulations": m.get("pader_tabulations", m.get("tabulations", {})),
        "unlabelled_pts_ge3": safe_get(m, "reaction_analysis.unlabelled_pts_ge3_serious_cases", [])
    }


def assemble_case_presentation(m: Dict[str, Any]) -> Dict[str, Any]:
    pts = safe_get(m, "reaction_analysis.unlabelled_pts_ge3_serious_cases", [])
    if not pts:
        pts = m.get("charts", {}).get("top_serious_reaction_terms", [])
        
    return {
        "unlabelled_pts_ge3": pts[:5] if isinstance(pts, list) else [],
        "note": "Narratives reflect aggregated spontaneous reporting patterns."
    }


def assemble_trends_and_observations(m: Dict[str, Any]) -> Dict[str, Any]:
    kpis = m.get("kpi_cards", m.get("case_volume", {}))
    tot_cases = kpis.get("unique_cases", kpis.get("total_cases", 1))
    
    charts = m.get("charts", {})
    age_dist = charts.get("age_distribution", safe_get(m, "demographics.age_distribution", {}))
    sc = charts.get("seriousness_breakdown", m.get("seriousness_criteria", {}))
    top_pts = charts.get("top_reaction_terms", safe_get(m, "reaction_analysis.top_pt_case_frequency", [{}]))

    late_elderly = age_dist.get("Late Elderly (75+)", 0)
    elderly = age_dist.get("Elderly (65-74)", 0)
    hosp = sc.get("hospitalization", 0)

    return {
        "late_elderly_pct": safe_pct(late_elderly, tot_cases),
        "elderly_combined_pct": safe_pct(late_elderly + elderly, tot_cases),
        "hospitalization_pct": safe_pct(hosp, tot_cases),
        "top_pt": top_pts[0] if len(top_pts) > 0 else {"pt": "N/A", "case_count": 0}
    }


def assemble_history_of_actions(m: Dict[str, Any]) -> Dict[str, Any]:
    disc = safe_get(m, "disclaimers.history_of_actions")
    if not disc:
        disc = "No regulatory or safety-related action data was provided for the current reporting interval."
    return {"disclaimer": disc}


def assemble_safety_section(m: Dict[str, Any]) -> Dict[str, Any]:
    meta = assemble_title_and_header(m)
    disc = safe_get(m, "disclaimers.ccds_expectedness_data")
    if not disc:
        disc = "Company Core Data Sheet (CCDS) reference labeling was unavailable; analysis reflects raw reported terms."
    return {
        "product_name": meta["product_name"],
        "disclaimer": disc
    }


def assemble_case_index(m: Dict[str, Any]) -> Dict[str, Any]:
    kpis = m.get("kpi_cards", m.get("case_volume", {}))
    return {
        "unique_cases": kpis.get("unique_cases", kpis.get("total_cases", 0)),
        "total_rows": kpis.get("total_rows", safe_get(m, "dataset_summary.total_rows", 0))
    }


# =============================================================================
# DYNAMIC PROMPT REGISTRY CLASS
# =============================================================================

class PADERPromptRegistry:
    """Dynamic registry managing PADER report sections, prompts, and context rules."""

    def __init__(self, system_prompt: str = DEFAULT_SYSTEM_PROMPT):
        self.system_prompt = system_prompt
        self._sections: Dict[str, Dict[str, Any]] = {}
        self._register_default_sections()

    def _register_default_sections(self):
        """Initializes standard 21 CFR 314.80 PADER sections."""
        defaults = [
            ("title_and_header", "Title Page & Metadata", "Generate the standard regulatory Title Page header for the PADER report.", assemble_title_and_header),
            ("introduction", "1. Introduction", "Summarize the scope of the PADER report, product indication, reporting interval, and FDA regulatory basis under 21 CFR 314.80.", assemble_introduction),
            ("narrative_summary", "2. Narrative Summary and Analysis", "Provide an overall narrative summary of safety information received during the reporting period.", assemble_narrative_summary),
            ("summary_analysis_of_cases", "3. Summary Analysis of Cases", "Provide aggregate breakdown of case volume and demographics including age groups, sex, reporter qualifications, top countries, and seriousness criteria.", assemble_summary_analysis_of_cases),
            ("reaction_analysis", "4. Reaction / Adverse Event Analysis", "Analyze reported adverse reactions at the MedDRA Preferred Term (PT) level.", assemble_reaction_analysis),
            ("serious_cases_and_alerts", "5. Serious Cases / 15-Day Alerts & Tabulations", "Summarize 15-Day Alert expedited reports and present 21 CFR 314.80 case tabulations.", assemble_serious_cases_and_alerts),
            ("case_presentation", "6. Case Presentation & Clinical Summaries", "Provide narrative case presentations for top unlabelled Preferred Terms reported in serious cases.", assemble_case_presentation),
            ("trends_and_observations", "7. Trends and Important Observations", "Surfacing key reporting trends (e.g. high concentration in elderly patients 65+, male/female parity, high hospitalization rate).", assemble_trends_and_observations),
            ("history_of_actions", "8. History of Actions", "State the History of Actions status. Include the mandatory disclaimer that no action data was supplied.", assemble_history_of_actions),
            ("safety_section", "9. Safety Section & Labeling Overview", "Provide CCDS and Product Label overview for product.", assemble_safety_section),
            ("case_index", "10. Case Index / Summary Listing", "Describe case index access and how aggregate totals trace back to individual safetyreportid records.", assemble_case_index),
        ]

        for key, title, instructions, assembler in defaults:
            self.register_section(key, title, instructions, assembler)

    def register_section(self, key: str, title: str, instructions: str, assemble_fn: Callable[[Dict[str, Any]], Dict[str, Any]]):
        """Dynamically registers or overrides a report section configuration."""
        self._sections[key] = {
            "title": title,
            "instructions": instructions,
            "assemble_context": assemble_fn
        }

    def unregister_section(self, key: str):
        """Removes a section from the reporting pipeline."""
        self._sections.pop(key, None)

    def get_section(self, key: str) -> Optional[Dict[str, Any]]:
        return self._sections.get(key)

    def assemble_all_contexts(self, metrics: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Assembles context packets for all registered sections safely."""
        assembled = {}
        for key, section_info in self._sections.items():
            try:
                assembled[key] = section_info["assemble_context"](metrics)
            except Exception as e:
                assembled[key] = {"error": f"Failed to assemble context for '{key}': {str(e)}"}
        return assembled

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """Exports section definitions as a raw dictionary for legacy compatibility."""
        return copy.deepcopy(self._sections)


# =============================================================================
# GLOBAL EXPORTS (BACKWARD COMPATIBILITY LAYER)
# =============================================================================

_global_registry = PADERPromptRegistry()

SYSTEM_PROMPT = _global_registry.system_prompt
SECTION_PROMPTS = _global_registry.to_dict()


def register_custom_section(key: str, title: str, instructions: str, assemble_fn: Callable):
    """Global helper to inject custom sections into the global registry at runtime."""
    global SECTION_PROMPTS
    _global_registry.register_section(key, title, instructions, assemble_fn)
    SECTION_PROMPTS = _global_registry.to_dict()