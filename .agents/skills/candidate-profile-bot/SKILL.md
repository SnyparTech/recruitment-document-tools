---
name: candidate-profile-bot
description: Autonomous recruitment intelligence agent for searching, matching, and ranking candidate profiles (not job postings) across talent portals such as Naukri Resdex.
---

# Candidate Profile Automation Agent Skill

This skill guides agents in performing automated candidate profile search, multi-factor evaluation, and ranking based on natural-language hiring requirements.

## Core Capabilities
- **Candidate Profiles (Not Job Postings)**: Specifically targets candidate resumes and profiles (Candidate Name, Current Title, Total Experience, Organization, Location, Skills, Education, Profile Link).
- **Natural Language Parsing**: Extracts role, required skills (with alias expansion like `ML` -> `Machine Learning`, `GenAI` -> `Generative AI`, `Postgres` -> `PostgreSQL`), experience bounds, location, and education.
- **5-Factor Weighted Matching**:
  - Skills: 40%
  - Role Similarity: 20%
  - Experience: 15%
  - Location: 15%
  - Education: 10% (dynamically redistributed when omitted)
- **Top 10 Candidate Ranking**: Limits results to the top 10 best-matching candidate profiles.

## Execution Workflow

1. Start FastAPI backend (if not running):
   ```bash
   uvicorn app.main:app --reload
   ```

2. Invoke the Profile Search Endpoint:
   ```bash
   curl -X POST http://127.0.0.1:8000/profiles/search \
     -H "Content-Type: application/json" \
     -d '{
       "requirement": "Find AI/ML Engineers in Hyderabad with 1-3 years experience and skills Python, FastAPI, Machine Learning and NLP",
       "portal": "naukri",
       "limit": 10,
       "use_mock": false
     }'
   ```

3. Interpret Response:
   - Check `total_candidates_found` and `top_candidates`.
   - Present candidates ordered by `match_score` with highlighted `matched_skills` and `missing_skills`.
