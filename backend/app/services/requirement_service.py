import logging
from typing import Dict, List, Optional, Tuple
from app.agents.requirement_agent import RequirementAgent
from app.schemas.requirement import ValidationResult
from app.schemas.search_plan import SearchPlan
from app.services.validation_service import ValidationService

logger = logging.getLogger(__name__)


class RequirementService:
    """
    Coordinates requirement parsing and validation pipeline.
    """

    def __init__(
        self,
        agent: RequirementAgent = None,
        validator: ValidationService = None,
    ):
        self.agent = agent or RequirementAgent()
        self.validator = validator or ValidationService()

    def process_requirement(self, text: str) -> Tuple[SearchPlan, ValidationResult]:
        """
        Takes raw recruiter requirement text, generates structured SearchPlan via RequirementAgent,
        and validates against resdex_schema.json.
        """
        logger.info(f"Processing requirement: {text[:60]}...")
        plan = self.agent.generate_search_plan(text)
        validation = self.validator.validate(plan)
        return plan, validation

    def chat_edit(
        self,
        current_plan: Optional[SearchPlan],
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[SearchPlan, str]:
        """
        Requirement chat: first turn (no current_plan) parses `message` as a
        JD via process_requirement()'s pipeline; every turn after that applies
        `message` as an edit instruction on top of the existing draft. Never
        validated/stored here — that's the caller's job once the recruiter
        clicks Apply, so mid-conversation drafts can be invalid without
        blocking the chat itself.
        """
        logger.info(f"Chat edit: {message[:60]}...")
        return self.agent.generate_chat_reply(current_plan, message, history)
