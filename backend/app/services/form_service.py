import logging
from app.core.exceptions import RequirementParsingError
from app.portals.naukri_resdex import NaukriResdexPortal
from app.schemas.requirement import (
    CandidateSearchRequest,
    CandidateSearchResponse,
    ExecutionResult,
)
from app.services.requirement_service import RequirementService

logger = logging.getLogger(__name__)


class FormService:
    """
    Orchestrates the complete candidate search workflow:
    1. Requirement parsing via RequirementAgent
    2. Schema validation via ValidationService
    3. Dry-run or live Selenium form execution via NaukriResdexPortal
    """

    def __init__(
        self,
        requirement_service: RequirementService = None,
        portal: NaukriResdexPortal = None,
    ):
        self.requirement_service = requirement_service or RequirementService()
        self.portal = portal or NaukriResdexPortal()

    def process_search_request(
        self, request: CandidateSearchRequest
    ) -> CandidateSearchResponse:
        """
        Processes candidate search request according to execute and submit_search flags.
        """
        # Step 1 & 2: Parse and Validate
        plan, validation = self.requirement_service.process_requirement(
            request.requirement
        )

        execution_result = ExecutionResult(
            requested=request.execute,
            executed=False,
            form_filled=False,
            search_submitted=False,
            fields_interacted=[],
            message="Dry-run mode: SearchPlan generated and validated without Selenium execution.",
        )

        # If execution is requested and plan is valid, execute via Selenium
        if request.execute:
            if not validation.valid:
                execution_result.message = (
                    f"Execution aborted due to validation errors: {'; '.join(validation.errors)}"
                )
                logger.warning(execution_result.message)
            else:
                logger.info(
                    f"Executing SearchPlan with submit_search={request.submit_search}"
                )
                execution_result = self.portal.execute_plan(
                    plan=plan,
                    submit_search=request.submit_search,
                )

        return CandidateSearchResponse(
            requirement=request.requirement,
            search_plan=plan,
            validation=validation,
            execution=execution_result,
        )
