import json
import re
from pydantic import ValidationError
from src.brain2.schemas import InvestigationResultSchema
from src.brain2.selector import SafeIncidentPackage

class HallucinatedEvidenceError(Exception):
    pass

class ValidationCorrectionError(Exception):
    """Raised when validation fails and a correction loop should be attempted."""
    def __init__(self, message: str, correction_prompt: str):
        super().__init__(message)
        self.correction_prompt = correction_prompt

class Brain2Validator:
    """
    Deterministically validates the output of the Brain 2 LLM.
    Guarantees structural containment and evidence grounding.
    """
    def __init__(self):
        self.uuid_pattern = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I)
        self.approved_actions = {
            "COLLECT_PROCESS_TREE", "REVIEW_AUTHENTICATION", "INSPECT_DESTINATION", 
            "RESET_CREDENTIALS", "COLLECT_PCAP", "ISOLATE_HOST", "BLOCK_IP", 
            "DISABLE_USER", "REQUIRE_MFA", "KILL_PROCESS", "INVESTIGATE_USER_ACTIVITY"
        }

    def validate(self, raw_json: str, package: SafeIncidentPackage) -> InvestigationResultSchema:
        # 0. Check for raw UUID leakage
        if self.uuid_pattern.search(raw_json):
            raise ValidationCorrectionError("Output contains raw UUIDs", "Your output leaked internal UUIDs. Use safe aliases only.")
            
        # Clean markdown codeblocks if model wrapped JSON in ```json ... ```
        cleaned_json = raw_json.strip()
        if cleaned_json.startswith("```json"):
            cleaned_json = cleaned_json[7:]
        elif cleaned_json.startswith("```"):
            cleaned_json = cleaned_json[3:]
        if cleaned_json.endswith("```"):
            cleaned_json = cleaned_json[:-3]
        cleaned_json = cleaned_json.strip()

        # 1. Parse JSON and Pydantic Schema
        try:
            data = json.loads(cleaned_json)
            # Normalize action types in next_best_actions if present
            if isinstance(data, dict) and "next_best_actions" in data and isinstance(data["next_best_actions"], list):
                for act in data["next_best_actions"]:
                    if isinstance(act, dict) and "action_type" in act:
                        act["action_type"] = str(act["action_type"]).upper().strip()
            parsed = InvestigationResultSchema(**data)
        except json.JSONDecodeError as e:
            raise ValidationCorrectionError(f"JSON Parse Error: {str(e)}", "Your output was not valid JSON.")
        except ValidationError as e:
            raise ValidationCorrectionError(f"Schema Validation Error: {str(e)}", f"Your output violated the schema: {str(e)}")

        # 2. Extract Valid Aliases
        valid_aliases = {sig["signal_ref"] for sig in package.signals}
        
        # 3. Grounding Validator
        hallucinations = []
        
        # Check supporting evidence
        for ev in parsed.supporting_evidence:
            if ev.evidence_ref not in valid_aliases:
                hallucinations.append(ev.evidence_ref)
                
        # Check contradicting evidence
        for ev in parsed.contradicting_evidence:
            if ev.evidence_ref not in valid_aliases:
                hallucinations.append(ev.evidence_ref)
                
        # Check actions
        for action in parsed.next_best_actions:
            action.action_type = action.action_type.upper().strip()
            if action.action_type not in self.approved_actions:
                raise ValidationCorrectionError(f"Invalid action type: {action.action_type}", f"Action type must be one of {self.approved_actions}")
            for ref in action.supporting_evidence_refs:
                if ref not in valid_aliases:
                    hallucinations.append(ref)
                    
        # Check MITRE
        for attack in parsed.attack_hypotheses:
            for ref in attack.evidence_refs:
                if ref not in valid_aliases:
                    hallucinations.append(ref)
                    
        if hallucinations:
            # We strictly reject hallucinations.
            raise HallucinatedEvidenceError(f"LLM cited unknown/hallucinated evidence references: {set(hallucinations)}")
            
        return parsed
