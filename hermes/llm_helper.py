"""
LLM helper module for handling ambiguous form fields using Claude.
"""

import os
from typing import List, Optional, TYPE_CHECKING

from anthropic import Anthropic

from .config import Profile, CustomAnswer

if TYPE_CHECKING:
    from .form_filler import FormField


class LLMHelper:
    """Uses Claude API to help with ambiguous form fields."""

    def __init__(self, profile: Profile):
        self.profile = profile
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize Anthropic client."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            self.client = Anthropic(api_key=api_key)

    def is_available(self) -> bool:
        """Check if LLM is available."""
        return self.client is not None

    def suggest_value(
        self,
        field: "FormField",
        job_title: str = "",
        company_name: str = "",
    ) -> Optional[str]:
        """Get LLM suggestion for an ambiguous field."""
        if not self.client:
            return None

        prompt = self._build_prompt(field, job_title, company_name)

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
            return self._parse_response(response.content[0].text, field)
        except Exception as e:
            print(f"LLM error: {e}")
            return None

    def _build_prompt(
        self,
        field: "FormField",
        job_title: str,
        company_name: str,
    ) -> str:
        """Build prompt for the LLM."""
        profile_summary = self._get_profile_summary()

        prompt = f"""You are helping fill out a job application form. Based on the candidate's profile and the field information, provide the best response.

CANDIDATE PROFILE:
{profile_summary}

JOB DETAILS:
- Position: {job_title or 'Not specified'}
- Company: {company_name or 'Not specified'}

FORM FIELD:
- Label: {field.label}
- Type: {field.input_type}
- Required: {'Yes' if field.is_required else 'No'}
"""

        if field.options:
            prompt += f"- Options: {', '.join(field.options)}\n"

        prompt += """
INSTRUCTIONS:
1. If this is a multiple choice field, respond with EXACTLY one of the provided options.
2. For text fields, provide a concise, professional response.
3. For questions about motivation or interest, write 2-3 sentences.
4. If you cannot determine a good answer, respond with "SKIP".

YOUR RESPONSE (just the value, no explanation):"""

        return prompt

    def _get_profile_summary(self) -> str:
        """Get a summary of the user profile for the prompt."""
        p = self.profile
        return f"""
- Name: {p.personal.full_name}
- Current Role: {p.experience.current_title} at {p.experience.current_company}
- Years of Experience: {p.experience.years_of_experience}
- Education: {p.education.highest_degree} in {p.education.field_of_study} from {p.education.university}
- Location: {p.location.city}, {p.location.state}
- Work Authorization: {'Authorized to work' if p.work_authorization.authorized_to_work else 'Not authorized'}
- Sponsorship Required: {'Yes' if p.work_authorization.require_sponsorship else 'No'}
"""

    def _parse_response(self, response: str, field: "FormField") -> Optional[str]:
        """Parse LLM response and validate it."""
        response = response.strip()

        if response.upper() == "SKIP":
            return None

        # For select fields, validate the response matches an option
        if field.input_type == "select" and field.options:
            response_lower = response.lower()
            for option in field.options:
                if option.lower() == response_lower:
                    return option
                if response_lower in option.lower():
                    return option
            # If no match found, return the response anyway (might be close enough)

        return response

    def generate_cover_letter_snippet(
        self,
        job_title: str,
        company_name: str,
        job_description: str = "",
    ) -> Optional[str]:
        """Generate a brief cover letter or motivation statement."""
        if not self.client:
            return None

        profile_summary = self._get_profile_summary()

        prompt = f"""Write a brief 2-3 sentence cover letter snippet for a job application.

CANDIDATE PROFILE:
{profile_summary}

JOB DETAILS:
- Position: {job_title}
- Company: {company_name}
- Description: {job_description[:500] if job_description else 'Not provided'}

Write a concise, professional statement about why this candidate is interested in and qualified for this role. Focus on relevance and enthusiasm. Do not use generic phrases like "I am excited to apply." Be specific and genuine.

YOUR RESPONSE:"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
            return response.content[0].text.strip()
        except Exception as e:
            print(f"LLM error generating cover letter: {e}")
            return None

    def answer_custom_question(
        self,
        question: str,
        max_length: Optional[int] = None,
        job_title: str = "",
        company_name: str = "",
    ) -> Optional[str]:
        """Answer a custom/open-ended question."""
        if not self.client:
            return None

        profile_summary = self._get_profile_summary()

        length_instruction = ""
        if max_length:
            length_instruction = f"Keep your response under {max_length} characters."

        prompt = f"""You are helping a job candidate answer an application question.

CANDIDATE PROFILE:
{profile_summary}

JOB DETAILS:
- Position: {job_title or 'Not specified'}
- Company: {company_name or 'Not specified'}

QUESTION:
{question}

INSTRUCTIONS:
- Answer professionally and authentically from the candidate's perspective.
- Be specific and avoid generic phrases.
- {length_instruction}
- If the question cannot be answered based on the profile, respond with "SKIP".

YOUR ANSWER:"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
            answer = response.content[0].text.strip()
            if answer.upper() == "SKIP":
                return None
            return answer
        except Exception as e:
            print(f"LLM error answering question: {e}")
            return None

    def answer_form_field(
        self,
        field: "FormField",
        custom_answers: List[CustomAnswer],
        job_title: str = "",
        company_name: str = "",
    ) -> Optional[str]:
        """Answer a form field using profile and custom answers as knowledge base.

        This is the main method for LLM-assisted form filling. It provides the LLM with:
        1. User's profile information
        2. Previously answered questions (custom_answers.yaml)
        3. The current field to answer

        Args:
            field: The form field to answer
            custom_answers: List of previously answered Q&A pairs
            job_title: Current job title being applied for
            company_name: Company name

        Returns:
            The suggested answer, or None if unable to answer
        """
        if not self.client:
            return None

        profile_summary = self._get_profile_summary()
        custom_answers_text = self._format_custom_answers(custom_answers)

        # Build the prompt with knowledge base
        prompt = f"""You are helping fill out a job application form. Use the candidate's profile and their previously answered questions to provide the best response.

CANDIDATE PROFILE:
{profile_summary}

PREVIOUSLY ANSWERED QUESTIONS (use these as reference for similar questions):
{custom_answers_text}

JOB DETAILS:
- Position: {job_title or 'Not specified'}
- Company: {company_name or 'Not specified'}

CURRENT FORM FIELD:
- Label/Question: {field.label}
- Type: {field.input_type}
- Required: {'Yes' if field.is_required else 'No'}
"""

        if field.options:
            prompt += f"- Available Options: {field.options}\n"

        prompt += """
INSTRUCTIONS:
1. If this is similar to a previously answered question, use that answer.
2. If this is a dropdown/select field, respond with EXACTLY one of the provided options.
3. For Yes/No questions, respond with just "Yes" or "No".
4. For text fields, provide a concise, professional response.
5. If you truly cannot determine a reasonable answer, respond with "SKIP".

IMPORTANT:
- For "Have you worked at [Company]" questions, answer "No" unless the profile shows employment there.
- For legal questions (non-compete, NDA), default to "No" unless profile indicates otherwise.
- Match your answer to the available options when provided.

YOUR RESPONSE (just the value, no explanation):"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
            answer = response.content[0].text.strip()

            if answer.upper() == "SKIP":
                return None

            # For fields with options, try to match the answer to an option
            if field.options:
                answer = self._match_to_option(answer, field.options)

            print(f"    LLM suggested: '{answer}'")
            return answer

        except Exception as e:
            print(f"    LLM error: {e}")
            return None

    def _format_custom_answers(self, custom_answers: List[CustomAnswer]) -> str:
        """Format custom answers for the prompt."""
        if not custom_answers:
            return "None available"

        lines = []
        for ca in custom_answers[:15]:  # Limit to 15 to avoid token limits
            lines.append(f"Q: {ca.question}")
            lines.append(f"A: {ca.answer}")
            lines.append("")

        return "\n".join(lines)

    def _match_to_option(self, answer: str, options: List[str]) -> str:
        """Try to match the LLM's answer to one of the available options."""
        answer_lower = answer.lower().strip()

        # Exact match
        for opt in options:
            if opt.lower().strip() == answer_lower:
                return opt

        # Starts with match (e.g., "No" matches "No, I do not...")
        for opt in options:
            opt_lower = opt.lower().strip()
            if opt_lower.startswith(answer_lower) or answer_lower.startswith(opt_lower):
                return opt

        # Contains match
        for opt in options:
            if answer_lower in opt.lower() or opt.lower() in answer_lower:
                return opt

        # No match found, return original answer
        return answer
