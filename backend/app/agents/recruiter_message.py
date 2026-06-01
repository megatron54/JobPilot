"""Recruiter message generator agent - for LinkedIn DMs and emails."""

import json
from typing import AsyncGenerator

from app.core.llm import chat
from app.services.cv_parser import get_cv_content
from app.services.profile_manager import get_profile
from app.services.job_manager import get_job


SYSTEM_PROMPT_ES = """Eres un experto en networking profesional y comunicacion con reclutadores.
Tu objetivo es crear mensajes directos efectivos para contactar reclutadores en LinkedIn o por email.

TIPOS DE MENSAJE:
1. **Primer contacto**: Mensaje breve para presentarte y mostrar interes en una vacante
2. **Follow-up**: Mensaje de seguimiento despues de aplicar
3. **Networking**: Mensaje para conectar sin una vacante especifica

REGLAS:
- Maximo 300 palabras para LinkedIn DM (limite de la plataforma)
- Se directo pero respetuoso del tiempo del reclutador
- Muestra que investigaste sobre la empresa
- Incluye un "hook" que genere interes (logro relevante, conexion)
- Termina con una pregunta o call-to-action claro
- NO seas demasiado formal ni demasiado casual
- NO copies el formato de la carta de presentacion - esto es un mensaje directo"""

SYSTEM_PROMPT_EN = """You are an expert in professional networking and recruiter communication.
Your goal is to create effective direct messages for contacting recruiters on LinkedIn or via email.

MESSAGE TYPES:
1. **First contact**: Brief message to introduce yourself and show interest in a role
2. **Follow-up**: Follow-up message after applying
3. **Networking**: Message to connect without a specific vacancy

RULES:
- Maximum 300 words for LinkedIn DM (platform limit)
- Be direct but respectful of the recruiter's time
- Show you researched the company
- Include a "hook" that generates interest (relevant achievement, connection)
- End with a question or clear call-to-action
- DON'T be too formal or too casual
- DON'T copy the cover letter format - this is a direct message"""


def _get_system_prompt(language: str) -> str:
    if language.startswith("es"):
        return SYSTEM_PROMPT_ES
    return SYSTEM_PROMPT_EN


def _build_prompt(
    cv_content: str,
    job_data: dict,
    profile: dict,
    language: str,
    message_type: str,
    recruiter_name: str = "",
) -> str:
    """Build the prompt for recruiter message generation."""
    lang_label = "Spanish" if language.startswith("es") else "English"
    
    prompt = f"""Generate a {message_type} message for a recruiter in {lang_label}.

--- CANDIDATE INFO ---
Name: {profile.get('name', 'N/A')}
Title: {profile.get('title', 'N/A')}
Key skills: {', '.join(profile.get('key_skills', []))}
Years of experience: {profile.get('years_experience', 'N/A')}

--- CV HIGHLIGHTS ---
{cv_content[:2000]}

--- JOB/COMPANY INFO ---
Company: {job_data.get('company', 'N/A')}
Position: {job_data.get('position', 'N/A')}
Description summary: {job_data.get('raw_description', 'N/A')[:1000]}
"""
    if recruiter_name:
        prompt += f"\nRecruiter name: {recruiter_name}"
    
    prompt += f"""

Message type: {message_type}
Tone: {profile.get('tone', 'professional')} but conversational

Write ONLY the message. No meta-commentary, no subject line unless it's an email."""
    return prompt


async def generate_recruiter_message(
    cv_filename: str,
    job_id: str,
    message_type: str = "first_contact",
    language: str = "es",
    recruiter_name: str = "",
    stream: bool = False,
) -> str | AsyncGenerator[str, None]:
    """Generate a message for a recruiter.
    
    message_type: first_contact, follow_up, networking
    """
    cv_content = get_cv_content(cv_filename)
    job_data = get_job(job_id)
    profile = get_profile()

    system_prompt = _get_system_prompt(language)
    user_prompt = _build_prompt(cv_content, job_data, profile, language, message_type, recruiter_name)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    if stream:
        return _stream_response(messages)
    
    return await chat(messages, stream=False)


async def _stream_response(messages: list[dict]) -> AsyncGenerator[str, None]:
    """Stream the message generation."""
    generator = await chat(messages, stream=True)
    async for token in generator:
        yield json.dumps({"token": token}) + "\n"
    yield json.dumps({"done": True}) + "\n"
