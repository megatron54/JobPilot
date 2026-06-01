"""Interview Q&A agent - generates answers to common selection process questions."""

import json
from typing import AsyncGenerator

from app.core.llm import chat
from app.services.cv_parser import get_cv_content
from app.services.profile_manager import get_profile
from app.services.job_manager import get_job


SYSTEM_PROMPT_ES = """Eres un coach de entrevistas laborales experto.
Tu objetivo es ayudar al candidato a preparar respuestas efectivas para preguntas de seleccion.

METODOLOGIA:
- Usa el metodo STAR (Situacion, Tarea, Accion, Resultado) cuando aplique
- Basa las respuestas en la experiencia REAL del candidato (del CV)
- Adapta las respuestas al puesto y empresa especificos
- Se honesto pero estrategico - destaca fortalezas relevantes
- Para preguntas sobre debilidades, usa el enfoque de "area de mejora activa"

REGLAS:
- NO inventes experiencias que no esten en el CV
- Si no hay informacion suficiente, sugiere como podria responder de forma general
- Incluye tips adicionales despues de cada respuesta
- Las respuestas deben ser naturales, no roboticas"""

SYSTEM_PROMPT_EN = """You are an expert job interview coach.
Your goal is to help candidates prepare effective answers for selection process questions.

METHODOLOGY:
- Use the STAR method (Situation, Task, Action, Result) when applicable
- Base answers on the candidate's REAL experience (from CV)
- Adapt answers to the specific role and company
- Be honest but strategic - highlight relevant strengths
- For weakness questions, use the "active improvement area" approach

RULES:
- DO NOT invent experiences not in the CV
- If there's not enough information, suggest a general approach
- Include additional tips after each answer
- Answers should be natural, not robotic"""


def _get_system_prompt(language: str) -> str:
    if language.startswith("es"):
        return SYSTEM_PROMPT_ES
    return SYSTEM_PROMPT_EN


def _build_prompt(
    question: str,
    cv_content: str,
    job_data: dict,
    profile: dict,
    language: str,
) -> str:
    """Build the prompt for interview answer generation."""
    lang_label = "Spanish" if language.startswith("es") else "English"
    
    prompt = f"""Generate an answer to this interview question in {lang_label}:

QUESTION: "{question}"

--- CANDIDATE CV ---
{cv_content[:3000]}

--- CANDIDATE PROFILE ---
Name: {profile.get('name', 'N/A')}
Title: {profile.get('title', 'N/A')}
Key skills: {', '.join(profile.get('key_skills', []))}
Years of experience: {profile.get('years_experience', 'N/A')}
Summary: {profile.get('summary', 'N/A')}

--- TARGET POSITION ---
Company: {job_data.get('company', 'N/A')}
Position: {job_data.get('position', 'N/A')}
Requirements: {job_data.get('raw_description', 'N/A')[:1500]}

Provide:
1. A well-structured answer the candidate can use
2. Brief tips on delivery (tone, body language, what to emphasize)
"""
    return prompt


async def generate_answer(
    question: str,
    cv_filename: str,
    job_id: str,
    language: str = "es",
    stream: bool = False,
) -> str | AsyncGenerator[str, None]:
    """Generate an answer to an interview question."""
    cv_content = get_cv_content(cv_filename)
    job_data = get_job(job_id)
    profile = get_profile()

    system_prompt = _get_system_prompt(language)
    user_prompt = _build_prompt(question, cv_content, job_data, profile, language)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    if stream:
        return _stream_response(messages)
    
    return await chat(messages, stream=False)


async def generate_common_questions(
    cv_filename: str,
    job_id: str,
    language: str = "es",
) -> str:
    """Generate a list of likely interview questions for this position."""
    cv_content = get_cv_content(cv_filename)
    job_data = get_job(job_id)
    profile = get_profile()
    
    lang_label = "Spanish" if language.startswith("es") else "English"
    
    prompt = f"""Based on this job offer and candidate profile, generate 10 likely interview questions in {lang_label}.

--- JOB ---
Company: {job_data.get('company', 'N/A')}
Position: {job_data.get('position', 'N/A')}
Description: {job_data.get('raw_description', 'N/A')[:2000]}

--- CANDIDATE ---
Title: {profile.get('title', 'N/A')}
Experience: {profile.get('years_experience', 'N/A')} years

Include:
- 3 technical/skills questions
- 3 behavioral questions (STAR method)
- 2 motivation/culture fit questions
- 2 challenging/tricky questions

Format each as a numbered list. After each question, add a brief note on why they might ask it."""

    messages = [
        {"role": "system", "content": _get_system_prompt(language)},
        {"role": "user", "content": prompt},
    ]
    
    return await chat(messages, stream=False)


async def _stream_response(messages: list[dict]) -> AsyncGenerator[str, None]:
    """Stream the answer generation."""
    generator = await chat(messages, stream=True)
    async for token in generator:
        yield json.dumps({"token": token}) + "\n"
    yield json.dumps({"done": True}) + "\n"
