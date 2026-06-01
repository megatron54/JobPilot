"""Job analyzer agent - extracts structured info from job postings."""

import json

from app.core.llm import chat


SYSTEM_PROMPT = """You are a job posting analyzer. Extract structured information from job postings.
Always respond with valid JSON only, no additional text."""


async def analyze_job_posting(raw_text: str) -> dict:
    """Use AI to extract structured data from a raw job posting."""
    prompt = f"""Analyze this job posting and extract the following information as JSON:

{{
    "company": "company name",
    "position": "job title",
    "location": "location (remote/hybrid/onsite + city if available)",
    "salary_range": "salary if mentioned, otherwise null",
    "contract_type": "full-time/part-time/contract/freelance",
    "experience_required": "years or level required",
    "requirements": ["list", "of", "key", "requirements"],
    "responsibilities": ["list", "of", "main", "responsibilities"],
    "nice_to_have": ["list", "of", "nice", "to", "have"],
    "benefits": ["list", "of", "benefits"],
    "tech_stack": ["technologies", "mentioned"],
    "language_requirements": ["languages", "needed"],
    "key_keywords": ["important", "keywords", "for", "application"]
}}

--- JOB POSTING ---
{raw_text}

Respond ONLY with the JSON, no other text."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    response = await chat(messages, stream=False)
    
    # Try to parse JSON from response
    try:
        # Handle potential markdown code blocks
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1]
            clean = clean.rsplit("```", 1)[0]
        return json.loads(clean)
    except json.JSONDecodeError:
        # If AI didn't return valid JSON, return raw with basic structure
        return {
            "raw_description": raw_text,
            "company": "",
            "position": "",
            "ai_analysis": response,
        }
