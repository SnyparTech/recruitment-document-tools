import logging
from typing import Tuple
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
