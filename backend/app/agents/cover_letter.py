"""Cover letter generator agent."""

import json
from typing import AsyncGenerator

from app.core.llm import chat
from app.services.cv_parser import get_cv_content
from app.services.profile_manager import get_profile
from app.services.job_manager import get_job


SYSTEM_PROMPT_ES = """Eres un experto redactor de cartas de presentacion profesionales. 
Tu objetivo es crear cartas de presentacion personalizadas y efectivas que destaquen al candidato.

ESTRUCTURA de la carta de presentacion:
1. **Saludo personalizado**: Dirigirse al reclutador por nombre si es posible
2. **Breve resumen de perfil**: Quien eres, tu experiencia y especialidad
3. **Conexion con la vacante**: Por que te interesa esta empresa y puesto especifico
4. **Valor que aportas**: Que puedes ofrecer a la empresa, basado en tu experiencia
5. **Cierre profesional**: Disponibilidad para entrevista y agradecimiento

REGLAS:
- NUNCA uses un tono generico. Siempre personaliza para la empresa y puesto
- Menciona la empresa por nombre y el puesto especifico
- Destaca habilidades relevantes del CV que coincidan con los requisitos
- Se conciso pero impactante (maximo 4 parrafos)
- Adapta el tono segun se indique (profesional, cercano, formal)
- NO inventes experiencia que no este en el CV
- Incluye datos concretos cuando sea posible (anos de experiencia, logros)"""

SYSTEM_PROMPT_EN = """You are an expert professional cover letter writer.
Your goal is to create personalized and effective cover letters that make candidates stand out.

STRUCTURE:
1. **Personalized greeting**: Address the recruiter by name if possible
2. **Brief profile summary**: Who you are, your experience and specialty
3. **Connection to the role**: Why you're interested in this specific company and position
4. **Value proposition**: What you can offer the company based on your experience
5. **Professional closing**: Availability for interview and gratitude

RULES:
- NEVER use a generic tone. Always personalize for the company and role
- Mention the company by name and the specific position
- Highlight relevant CV skills that match the requirements
- Be concise but impactful (maximum 4 paragraphs)
- Adapt tone as indicated (professional, friendly, formal)
- DO NOT invent experience not in the CV
- Include concrete data when possible (years of experience, achievements)"""


def _get_system_prompt(language: str) -> str:
    if language.startswith("es"):
        return SYSTEM_PROMPT_ES
    return SYSTEM_PROMPT_EN


def _build_prompt(cv_content: str, job_data: dict, profile: dict, language: str, recruiter_name: str = "") -> str:
    """Build the generation prompt with all context."""
    lang_label = "Spanish" if language.startswith("es") else "English"
    
    prompt = f"""Generate a cover letter in {lang_label} based on the following information:

--- CV CONTENT ---
{cv_content}

--- JOB OFFER ---
Company: {job_data.get('company', 'N/A')}
Position: {job_data.get('position', 'N/A')}
Location: {job_data.get('location', 'N/A')}
Description: {job_data.get('raw_description', 'N/A')}

--- CANDIDATE PROFILE ---
Name: {profile.get('name', 'N/A')}
Title: {profile.get('title', 'N/A')}
Years of experience: {profile.get('years_experience', 'N/A')}
Key skills: {', '.join(profile.get('key_skills', []))}
Preferred tone: {profile.get('tone', 'professional')}
"""
    if recruiter_name:
        prompt += f"\nRecruiter name: {recruiter_name}"
    
    prompt += "\n\nWrite the cover letter now. Do NOT include any meta-commentary, just the letter itself."
    return prompt


async def generate_cover_letter(
    cv_filename: str,
    job_id: str,
    language: str = "es",
    recruiter_name: str = "",
    stream: bool = False,
) -> str | AsyncGenerator[str, None]:
    """Generate a personalized cover letter."""
    cv_content = get_cv_content(cv_filename)
    job_data = get_job(job_id)
    profile = get_profile()

    system_prompt = _get_system_prompt(language)
    user_prompt = _build_prompt(cv_content, job_data, profile, language, recruiter_name)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    if stream:
        return _stream_response(messages)
    
    return await chat(messages, stream=False)


async def _stream_response(messages: list[dict]) -> AsyncGenerator[str, None]:
    """Stream the cover letter generation."""
    generator = await chat(messages, stream=True)
    async for token in generator:
        yield json.dumps({"token": token}) + "\n"
    yield json.dumps({"done": True}) + "\n"
