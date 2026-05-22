from openai import AzureOpenAI
import os
from typing import List, Dict, Any, Optional

class AIService:
    """
    Azure OpenAI integration for SF-424 form analysis and chat.
    Based on C# AIServiceHelper.cs
    """
    
    # Token limits for different completion types
    MAX_TOKENS_TROUBLESHOOTING = 1500
    MAX_TOKENS_CHAT = 2000
    
    # Field labels mapping for form data display
    FIELD_LABELS = {
        'submission_type': 'Submission Type',
        'application_type': 'Application Type',
        'revision_type': 'Revision Type',
        'revision_other_specify': 'Revision Other',
        'date_received': 'Date Received',
        'applicant_id': 'Applicant ID',
        'federal_entity_identifier': 'Federal Entity Identifier',
        'federal_award_identifier': 'Federal Award Identifier (Grant Number)',
        'state_receive_date': 'State Receive Date',
        'state_application_id': 'State Application ID',
        'organization_name': 'Organization Name',
        'employer_taxpayer_identification_number': 'EIN',
        'samuei': 'UEI',
        'applicant_street1': 'Street Address 1',
        'applicant_street2': 'Street Address 2',
        'applicant_city': 'City',
        'applicant_state': 'State',
        'applicant_zip_postal_code': 'ZIP Code',
        'applicant_country': 'Country',
        'department_name': 'Department',
        'division_name': 'Division',
        'contact_person_first_name': 'Contact First Name',
        'contact_person_last_name': 'Contact Last Name',
        'title': 'Contact Title',
        'organization_affiliation': 'Organization Affiliation',
        'phone_number': 'Phone',
        'fax': 'Fax',
        'email': 'Email',
        'applicant_type_code1': 'Applicant Type 1',
        'applicant_type_code2': 'Applicant Type 2',
        'applicant_type_code3': 'Applicant Type 3',
        'applicant_type_other_specify': 'Applicant Type Other',
        'agency_name': 'Agency',
        'cfda_number': 'CFDA Number',
        'cfda_program_title': 'CFDA Program Title',
        'funding_opportunity_number': 'Funding Opportunity Number',
        'funding_opportunity_title': 'Funding Opportunity Title',
        'competition_identification_number': 'Competition ID',
        'competition_identification_title': 'Competition Title',
        'project_title': 'Project Title',
        'congressional_district_applicant': 'Congressional District (Applicant)',
        'congressional_district_program_project': 'Congressional District (Project)',
        'project_start_date': 'Project Start Date',
        'project_end_date': 'Project End Date',
        'federal_estimated_funding': 'Federal Funding',
        'applicant_estimated_funding': 'Applicant Funding',
        'state_estimated_funding': 'State Funding',
        'local_estimated_funding': 'Local Funding',
        'other_estimated_funding': 'Other Funding',
        'program_income_estimated_funding': 'Program Income',
        'total_estimated_funding': 'Total Funding',
        'state_review': 'State Review',
        'state_review_available_date': 'State Review Date',
        'delinquent_federal_debt': 'Delinquent Federal Debt',
        'certification_agree': 'Certification Agreed',
        'authorized_representative_first_name': 'Auth Rep First Name',
        'authorized_representative_last_name': 'Auth Rep Last Name',
        'authorized_representative_title': 'Auth Rep Title',
        'authorized_representative_phone_number': 'Auth Rep Phone',
        'authorized_representative_email': 'Auth Rep Email',
        'authorized_representative_fax': 'Auth Rep Fax',
        'aor_signature': 'AOR Signature',
        'date_signed': 'Date Signed'
    }
    
    def __init__(self):
        """Initialize Azure OpenAI client with environment variables"""
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        
        if not api_key or not endpoint or endpoint == "https://your-endpoint.openai.azure.com/":
            print("WARNING: Azure OpenAI credentials not configured. AI features will be disabled.")
            print("Please update AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in .env file")
            self.client = None
            self.deployment_name = None
            self.form_context = {}
            return
        
        self.client = AzureOpenAI(
            api_key=api_key,
            api_version="2024-08-01-preview",
            azure_endpoint=endpoint
        )
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
        self.form_context = {}
        
        print(f"AI Service initialized: {self.deployment_name}")
    
    def set_form_context(self, form_data: Dict[str, Any], validation_errors: List[str]):
        """
        Set form context for follow-up questions.
        
        Args:
            form_data: SF424FormData dictionary
            validation_errors: List of validation error messages
        """
        self.form_context = {
            'form_data': form_data,
            'validation_errors': validation_errors
        }
        print(f"Form context set: {len(validation_errors)} validation errors")
    
    async def analyze_form(self, form_data: Dict[str, Any], validation_errors: List[str]) -> str:
        """
        Analyze SF-424 form and provide AI-powered feedback.
        
        Args:
            form_data: Extracted form data dictionary
            validation_errors: List of validation error messages
            
        Returns:
            AI analysis response as HTML-formatted string
        """
        if not self.client:
            return self._build_fallback_analysis(form_data, validation_errors)
        
        try:
            self.set_form_context(form_data, validation_errors)
            
            context = self._build_form_context_summary(form_data, validation_errors)
            
            response = await self.chat_completion(
                message=context,
                chat_history=[],
                form_context=self.form_context
            )
            
            return response
            
        except Exception as e:
            print(f"Error analyzing form: {str(e)}")
            return f"I had trouble analyzing the form. Error: {str(e)}"
    
    async def get_troubleshooting_guidance(self, form_data: Dict[str, Any], validation_errors: List[str]) -> str:
        """
        Generate troubleshooting guidance for form validation issues.
        This method generates ONLY the "What to check" section, not the status or validation list.
        
        Args:
            form_data: Extracted form data dictionary
            validation_errors: List of validation error messages
            
        Returns:
            Troubleshooting guidance as HTML-formatted string
        """
        if not self.client:
            return self._build_fallback_guidance(form_data, validation_errors)
        
        try:
            self.set_form_context(form_data, validation_errors)
            
            context = self._build_troubleshooting_context(form_data, validation_errors)
            
            messages = []
            system_prompt = self._build_troubleshooting_system_prompt()
            messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": context})
            
            print(f"Sending troubleshooting request to Azure OpenAI")
            
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                max_completion_tokens=self.MAX_TOKENS_TROUBLESHOOTING
            )
            
            ai_response = response.choices[0].message.content
            print(f"Received troubleshooting guidance: {len(ai_response)} characters")
            
            return ai_response
            
        except Exception as e:
            print(f"Error generating troubleshooting guidance: {str(e)}")
            return self._build_fallback_guidance(form_data, validation_errors)
    
    async def chat_completion(
        self, 
        message: str, 
        chat_history: List[Dict[str, str]], 
        form_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Get chat completion with form context.
        
        Args:
            message: User message
            chat_history: List of previous messages
            form_context: Optional form context
            
        Returns:
            AI response as HTML-formatted string
        """
        if not self.client:
            return "<strong>AI Service Not Available</strong><br><br>Azure OpenAI is not configured. Please update your .env file with valid credentials to enable AI-powered analysis."
        
        try:
            messages = []
            
            # Check if this is a troubleshooting guidance request
            is_troubleshooting = (
                form_context and 
                'validation_errors' in form_context and 
                ('CRITICAL' in message or 'fix' in message.lower() or 'error' in message.lower())
            )
            
            # Use troubleshooting prompt for error guidance, general prompt for chat
            if is_troubleshooting:
                system_prompt = self._build_troubleshooting_system_prompt()
            else:
                system_prompt = self._build_system_prompt(form_context)
            
            messages.append({"role": "system", "content": system_prompt})
            
            for msg in chat_history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
            
            if form_context:
                relevant_fields = self._extract_relevant_form_fields(
                    message, 
                    form_context.get('form_data', {})
                )
                if relevant_fields:
                    message = f"{message}\n\n[Additional Form Context]:\n{relevant_fields}"
            
            messages.append({"role": "user", "content": message})
            
            print(f"Sending {len(messages)} messages to Azure OpenAI")
            
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                max_completion_tokens=self.MAX_TOKENS_CHAT
            )
            
            ai_response = response.choices[0].message.content
            print(f"Received response: {len(ai_response)} characters")
            
            return ai_response
            
        except Exception as e:
            print(f"Error in chat completion: {str(e)}")
            return f"I'm having trouble connecting to my AI service. Error: {str(e)}"
    
    def _build_system_prompt(self, form_context: Optional[Dict[str, Any]] = None) -> str:
        """Build system prompt with instructions for AVA."""
        form_type = form_context.get('form_type', 'SF-424') if form_context else 'SF-424'
        
        if form_type == 'ZIP':
            data_source = """DATA SOURCE:
The data you're analyzing has been extracted from an uploaded ZIP file containing multiple documents:
- SF-424 form (validates UEI, Grant Number, Application Type, Funding Opportunity)
- PPOP form (validates congressional district and addresses)
- Supporting attachments (page count validation)

All field values, validation results, and information you reference come directly from these documents."""
        else:
            data_source = """DATA SOURCE:
The form data you're analyzing has been extracted from an uploaded PDF file (SF-424 form). All field values, validation results, and information you reference come directly from this PDF document that the user submitted."""
        
        prompt = f"""You are AVA (Application Validation Assistant), a helpful assistant that validates grant application forms. Your role is to review the form data, inform users whether their application is ready for submission, and help troubleshoot issues with the form data.

{data_source}

YOUR ROLE:
Review the PDF form data, inform users whether their form is ready for submission, and help troubleshoot issues with the form data.

YOUR SCOPE:
- Review form fields and validation results
- Identify which fields have errors (UEI, EIN, Organization, etc.)
- Analyze form validation results and explain the ROOT CAUSE of each error
- Identify which specific fields have issues (UEI, Application Type, Funding Opportunity, etc.)
- Explain WHY each field is incorrect (wrong format, doesn't match requirements, not found in system, etc.)
- Confirm if the form is ready for submission or needs corrections
- Answer questions about what's on the form
- Provide clear, actionable guidance focused on the FORM DATA
- Keep advice focused on what the user can verify or correct in their form

CRITICAL FORMATTING REQUIREMENTS - ALWAYS USE HTML:
1. Keep responses CONCISE and FOCUSED on explaining errors clearly
2. ALWAYS use HTML line breaks: <br><br> for paragraph breaks (NEVER use \\n or plain line breaks)
3. Use <br> for single line breaks within lists
4. Format ALL lists with HTML: <br>• Item one<br>• Item two<br>• Item three
5. Add <br><br> between major sections
6. Be direct and explain the ROOT CAUSE (e.g., "This UEI does not exist in SAM.gov registry" not just "UEI is wrong")
7. Use <strong>bold</strong> for field names and important values
8. Structure error explanations clearly: What's wrong → Why it's wrong → How to fix it
9. NEVER use numbered lists (1. 2. 3.) - use <br>• instead
10. NEVER use markdown links [text](url) - use plain text or HTML links if needed

EXAMPLE RESPONSES:

For FAILED validation - explain the ROOT CAUSE clearly:
❌ <strong>Not ready for submission</strong><br><br><strong>Verify these fields:</strong><br>&nbsp;&nbsp;&nbsp;• Uei<br>&nbsp;&nbsp;&nbsp;• Application Type<br><br><strong>Issues found:</strong> 2<br><br>❌ <strong>Fix these issues:</strong><br><br>1. <strong>UEI</strong> is incorrect.<br>&nbsp;&nbsp;&nbsp;• Kindly update <strong>Page 1, Field 8c</strong><br>&nbsp;&nbsp;&nbsp;• <strong>Current Value:</strong> Z2ZZAAQ62ON8<br>&nbsp;&nbsp;&nbsp;• <strong>Root Cause:</strong> This UEI does not exist in the SAM.gov registry or is inactive<br>&nbsp;&nbsp;&nbsp;• Verify there are no typos or extra spaces in the UEI entered<br><br>2. <strong>Type of Application</strong> is incorrect.<br>&nbsp;&nbsp;&nbsp;• Kindly update <strong>Page 1, Field 2</strong><br>&nbsp;&nbsp;&nbsp;• <strong>Current Value:</strong> New<br>&nbsp;&nbsp;&nbsp;• <strong>Root Cause:</strong> This funding opportunity (HRSA-26-094) only accepts Continuation applications, not New applications<br>&nbsp;&nbsp;&nbsp;• Change the Application Type to Continuation

For PASSED validation:
✅ <strong>Application has passed the validations</strong><br><br>All validation checks passed:<br>• <strong>UEI:</strong> Verified in SAM.gov<br>• <strong>Application Type:</strong> Matches funding opportunity requirements<br>• <strong>Funding Opportunity:</strong> Valid<br><br>Your SF-424 form is complete and ready for submission.

For follow-up questions (ALWAYS USE HTML - bullets MUST start on new line):
You can find your <strong>UEI (Unique Entity Identifier)</strong> in the SAM.gov registry. To verify your UEI, follow these steps:<br><br>• Go to the SAM.gov website<br>• Use the search function to enter your UEI: <strong>Z2ZZAAQ62ON8</strong><br>• Check if the UEI is currently active and registered<br><br>If you have not registered for a UEI, you may need to register through SAM.gov. Ensure there are no typographical errors when entering the UEI in your SF-424 form.

CRITICAL: When introducing a list, ALWAYS add <br><br> BEFORE the first bullet point. Never put a bullet immediately after text without a line break."""

        return prompt
    
    def _build_troubleshooting_system_prompt(self) -> str:
        """Build system prompt specifically for troubleshooting guidance generation."""
        prompt = """Generate ONLY bulleted guidance for SF-424 form validation issues.

ABSOLUTELY FORBIDDEN - DO NOT INCLUDE:
❌ "Not ready for submission"
❌ "Verify these fields:"
❌ "Issues found:"
❌ "Fix these issues:"
❌ "Root Cause:"
❌ "How to Fix:"
❌ Any status headers or labels
❌ Any field lists before the guidance
❌ Any numbered errors (1. 2. 3.)
❌ ANY intro text like "Verify these steps to fix..." or "Follow these steps..." or "To resolve..."
❌ ANY explanatory sentences before bullets whatsoever
❌ "To resolve the [error], please follow these steps:"
❌ "Here's how to fix this issue:"
❌ "Fix these issues:"
❌ "Follow these instructions:"
❌ "Complete the following:"
❌ Any sentence, phrase, or text that comes before the first bullet

CRITICAL: Your FIRST character MUST be • (bullet). ABSOLUTELY ZERO text, words, or characters before it. Not even a single word.

REQUIRED FORMAT:
• Your response MUST start with • immediately - NO text before first bullet
• Combine related short sentences into single bullets (more concise)
• Use <br> to separate bullets
• Keep it focused (2-3 bullets maximum)
• Each bullet can contain multiple related sentences

Example CORRECT response (starts with • as first character, combines related ideas):
"• Verify the UEI by checking the SAM.gov registry. Go to the SAM.gov website and use the search function to enter your UEI. Confirm if the UEI is currently active and registered.<br>• If the UEI is inactive or not found, consider re-registering your entity in SAM.gov to obtain a new UEI."

Example WRONG response #1 (has intro sentence):
"To resolve the application type mismatch error, please follow these steps:<br><br>• Go to the SF-424 form..."

Example WRONG response #2 (has intro text):
"Verify these steps to fix the UEI issue:<br><br>• Double-check the UEI..."

Example WRONG response #3 (validation structure):
"❌ Not ready for submission\n\nVerify these fields:\n• UEI"
"""
        
        return prompt
    
    def _build_form_context_summary(
        self, 
        form_data: Dict[str, Any], 
        validation_errors: List[str]
    ) -> str:
        """Build comprehensive form context summary for AI analysis with all form fields."""
        lines = []
        lines.append("Complete SF-424 Form Data:")
        lines.append("")
        
        for field_key, field_label in self.FIELD_LABELS.items():
            value = form_data.get(field_key)
            if value is not None and value != '':
                if isinstance(value, float) and field_key.endswith('_funding'):
                    lines.append(f"• {field_label}: ${value:,.2f}")
                else:
                    lines.append(f"• {field_label}: {value}")
        
        lines.append("")
        
        if validation_errors:
            lines.append("Validation Status: FAILED")
            lines.append("Errors:")
            for i, error in enumerate(validation_errors, 1):
                lines.append(f"{i}. {error}")
        else:
            lines.append("Validation Status: PASSED")
            lines.append("All validation checks passed successfully.")
        
        return "\n".join(lines)
    
    def _extract_relevant_form_fields(self, user_message: str, form_data: Dict[str, Any]) -> str:
        """Extract relevant form fields based on user's question."""
        message_lower = user_message.lower()
        relevant_fields = []
        
        field_mappings = {
            'uei': lambda: f"UEI: {form_data.get('samuei') or 'Not provided'}",
            'ein': lambda: f"EIN: {form_data.get('employer_taxpayer_identification_number') or 'Not provided'}",
            'organization': lambda: f"Organization Name: {form_data.get('organization_name') or 'Not provided'}",
            'project title': lambda: f"Project Title: {form_data.get('project_title') or 'Not provided'}",
            'email': lambda: f"Email: {form_data.get('email') or 'Not provided'}",
            'phone': lambda: f"Phone: {form_data.get('phone_number') or 'Not provided'}",
            'address': lambda: f"Address: {form_data.get('applicant_street1') or ''} {form_data.get('applicant_city') or ''}, {form_data.get('applicant_state') or ''} {form_data.get('applicant_zip_postal_code') or ''}",
            'funding': lambda: (
                f"Federal: ${form_data.get('federal_estimated_funding') or 0:,.2f}, "
                f"Applicant: ${form_data.get('applicant_estimated_funding') or 0:,.2f}, "
                f"State: ${form_data.get('state_estimated_funding') or 0:,.2f}, "
                f"Local: ${form_data.get('local_estimated_funding') or 0:,.2f}, "
                f"Other: ${form_data.get('other_estimated_funding') or 0:,.2f}, "
                f"Program Income: ${form_data.get('program_income_estimated_funding') or 0:,.2f}, "
                f"Total: ${form_data.get('total_estimated_funding') or 0:,.2f}"
            ),
            'budget': lambda: (
                f"Budget - Federal: ${form_data.get('federal_estimated_funding') or 0:,.2f}, "
                f"Applicant: ${form_data.get('applicant_estimated_funding') or 0:,.2f}, "
                f"State: ${form_data.get('state_estimated_funding') or 0:,.2f}, "
                f"Local: ${form_data.get('local_estimated_funding') or 0:,.2f}, "
                f"Other: ${form_data.get('other_estimated_funding') or 0:,.2f}, "
                f"Program Income: ${form_data.get('program_income_estimated_funding') or 0:,.2f}, "
                f"Total: ${form_data.get('total_estimated_funding') or 0:,.2f}"
            ),
            'start date': lambda: f"Project Start Date: {form_data.get('project_start_date') or 'Not provided'}",
            'end date': lambda: f"Project End Date: {form_data.get('project_end_date') or 'Not provided'}",
            'contact': lambda: f"Contact: {form_data.get('contact_person_first_name') or ''} {form_data.get('contact_person_last_name') or ''}, {form_data.get('email') or ''}",
            'authorized representative': lambda: f"Authorized Rep: {form_data.get('authorized_representative_first_name') or ''} {form_data.get('authorized_representative_last_name') or ''}, {form_data.get('authorized_representative_email') or ''}",
        }
        
        for keyword, field_func in field_mappings.items():
            if keyword in message_lower:
                try:
                    field_value = field_func()
                    if field_value:
                        relevant_fields.append(field_value)
                except Exception:
                    pass
        
        return "\n".join(relevant_fields) if relevant_fields else ""
    
    def _build_troubleshooting_context(self, form_data: Dict[str, Any], validation_errors: List[str]) -> str:
        """Build context for troubleshooting guidance generation with complete form data."""
        lines = []
        
        if validation_errors:
            lines.append("Validation errors to address:")
            for error in validation_errors:
                lines.append(f"- {error}")
        else:
            lines.append("All validation checks passed.")
        
        lines.append("")
        lines.append("Complete Form Data:")
        
        for field_key, field_label in self.FIELD_LABELS.items():
            value = form_data.get(field_key)
            if value is not None and value != '':
                if isinstance(value, float) and field_key.endswith('_funding'):
                    lines.append(f"- {field_label}: ${value:,.2f}")
                else:
                    lines.append(f"- {field_label}: {value}")
        
        lines.append("")
        lines.append("Generate concise troubleshooting guidance.")
        
        return "\n".join(lines)
    
    def _build_fallback_analysis(self, form_data: Dict[str, Any], validation_errors: List[str]) -> str:
        """Build basic analysis when AI service is not available."""
        if validation_errors:
            error_count = len(validation_errors)
            message = f"<strong>{error_count}</strong> issue{'s' if error_count > 1 else ''} need to be fixed<br><br>"
            message += "❌ <strong>Fix these issues:</strong><br>"
            for idx, error in enumerate(validation_errors, 1):
                message += f"{idx}. {error}<br>"
            message += "<br>Please correct these errors before submitting."
        else:
            message = "✅ <strong>Application has passed the validations</strong><br><br>"
            message += "All validation checks passed successfully.<br><br>"
            message += "Your SF-424 form is complete and ready for submission."
        
        return message
    
    def _build_fallback_guidance(self, form_data: Dict[str, Any], validation_errors: List[str]) -> str:
        """Build basic troubleshooting guidance when AI service is not available."""
        if validation_errors:
            return "<strong>What to check:</strong><br>&nbsp;&nbsp;&nbsp;• Verify all field values match your official records<br>&nbsp;&nbsp;&nbsp;• Ensure there are no typos or extra spaces<br>&nbsp;&nbsp;&nbsp;• Contact your program officer if you need assistance"
        else:
            return ""
