from fastapi import APIRouter, status
from app.core.exceptions import PortalNotSupportedException
from app.models.candidate import ProfileSearchResponse
from app.models.requirement import SearchRequest
from app.portals.naukri import NaukriPortal
from app.services.matching_service import MatchingService
from app.services.query_generator import SearchQueryGenerator
from app.services.ranking_service import RankingService
from app.services.requirement_parser import RequirementParser

router = APIRouter(prefix="/profiles", tags=["Profiles"])

# Instantiate service singletons
requirement_parser = RequirementParser()
query_generator = SearchQueryGenerator()
matching_service = MatchingService()
ranking_service = RankingService(matcher=matching_service)
naukri_portal = NaukriPortal()

PORTALS = {
    "naukri": naukri_portal,
}


@router.post(
    "/search",
    response_model=ProfileSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search, Match, and Rank Candidates",
    description=(
        "Ingests a natural-language recruitment requirement, extracts structured search criteria "
        "(role, required skills, experience bounds, location), generates clean search keywords, "
        "searches the target job portal (Naukri via mock or Selenium), calculates multi-factor "
        "match scores (0-100), and returns the top 10 best-matching candidate profiles."
    ),
    response_description="Parsed requirement, search queries, candidate counts, and ranked top matching candidates.",
)
async def search_profiles(request: SearchRequest) -> ProfileSearchResponse:
    """
    Candidate search, matching, and ranking workflow.

    - **requirement**: Natural language job requirement text.
    - **portal**: Target portal (default: 'naukri').
    - **limit**: Maximum candidates to return (default: 10, max: 10).
    - **use_mock**: Whether to use safe mock data layer (default: true).
    """
    portal_key = request.portal.lower().strip()
    if portal_key not in PORTALS:
        raise PortalNotSupportedException(portal=request.portal)

    target_portal = PORTALS[portal_key]

    # Step 1: Parse requirement into structured parameters
    parsed_req = requirement_parser.parse(request.requirement)

    # Step 2: Generate search keywords and query terms
    search_query = query_generator.generate(parsed_req)

    # Step 3: Fetch candidates from portal adapter (mock or Selenium)
    raw_candidates = target_portal.search_candidates(
        requirement=parsed_req,
        query=search_query,
        use_mock=request.use_mock,
    )

    # Step 4: Calculate multi-factor match scores & rank candidates
    top_candidates, total_found = ranking_service.rank_candidates(
        candidates=raw_candidates,
        requirement=parsed_req,
        limit=request.limit,
    )

    mode_label = "mock" if request.use_mock else "live_selenium"

    return ProfileSearchResponse(
        requirement=request.requirement,
        parsed_requirement=parsed_req,
        search_query=search_query,
        portal=request.portal,
        mode=mode_label,
        total_candidates_found=total_found,
        returned_candidates=len(top_candidates),
        top_candidates=top_candidates,
    )
