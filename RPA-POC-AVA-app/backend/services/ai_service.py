from openai import AzureOpenAI
import os
from typing import List, Dict, Any, Optional

class AIService:
    """
    Azure OpenAI integration for SF-424 form analysis and chat.
    Based on C# AIServiceHelper.cs
    """
    
    def __init__(self):
        """Initialize Azure OpenAI client with environment variables"""
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        
        # Debug logging
        print(f"DEBUG - API Key loaded: {api_key[:10]}...{api_key[-4:] if api_key else 'None'}")
        print(f"DEBUG - Endpoint loaded: {endpoint}")
        
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
                max_completion_tokens=2000
            )
            
            ai_response = response.choices[0].message.content
            print(f"Received response: {len(ai_response)} characters")
            
            return ai_response
            
        except Exception as e:
            print(f"Error in chat completion: {str(e)}")
            return f"I'm having trouble connecting to my AI service. Error: {str(e)}"
    
    def _build_system_prompt(self, form_context: Optional[Dict[str, Any]] = None) -> str:
        """Build system prompt with instructions for AVA."""
        prompt = """You are AVA (Application Validation Assistant), a helpful assistant that validates SF-424 application forms. Your role is to review the PDF form data, inform users whether their form is ready for submission, and help troubleshoot issues with the form data.

YOUR SCOPE:
- Review form fields and validation results
- Identify which fields have errors (UEI, EIN, Organization, etc.)
- Confirm if the form is ready for submission or needs corrections
- Answer questions about what's on the form
- Provide troubleshooting guidance focused on the FORM DATA (e.g., check for typos, verify field matches, ensure format is correct)
- DO NOT provide guidance about external systems (SAM.gov, Grants.gov, etc.)
- DO NOT offer to help with registration processes outside the form
- Keep advice focused on what the user can verify or correct in their form

CRITICAL FORMATTING REQUIREMENTS:
1. Keep responses SHORT - aim for 100-150 words maximum
2. Use HTML line breaks: <br><br> for paragraph breaks (NOT \\n)
3. Use <br> for single line breaks within lists
4. Format lists as: <br>• Item one<br>• Item two<br>• Item three
5. Add <br><br> between major sections
6. Be direct and actionable
7. Use <strong>bold</strong> for field names and status

EXAMPLE RESPONSES:

For FAILED validation:
<strong>Form Status: Not Ready for Submission</strong><br><br>Validation issues found:<br>• <strong>UEI:</strong> E9358A5CI103 - Not found in system<br>• <strong>Organization:</strong> Testing INC - Does not match records<br><br><strong>What to check:</strong><br>• Verify the UEI is entered correctly (no typos or extra spaces)<br>• Ensure organization name matches exactly as registered<br>• Check that all required fields are filled out

For PASSED validation:
<strong>Form Status: Ready for Submission</strong> ✅<br><br>All validation checks passed:<br>• UEI verified<br>• EIN verified<br>• Organization verified<br><br>Your SF-424 form is complete and ready for submission.

For follow-up questions:
Keep answers brief and specific to the form data. Example:<br><br>The <strong>Project Title</strong> in your form is: "Community Health Initiative"<br><br>This appears in Section 11 of the SF-424 form."""

        return prompt
    
    def _build_form_context_summary(
        self, 
        form_data: Dict[str, Any], 
        validation_errors: List[str]
    ) -> str:
        """Build concise form context summary for AI analysis."""
        lines = []
        lines.append("Form data to confirm:")
        lines.append(f"• UEI: {form_data.get('samuei') or 'Not provided'}")
        lines.append(f"• Organization: {form_data.get('organization_name') or 'Not provided'}")
        
        if form_data.get('funding_opportunity_number'):
            lines.append(f"• Funding Opportunity: {form_data.get('funding_opportunity_number')}")
        
        if form_data.get('submission_type'):
            submission_map = {'1': 'New', '2': 'Changed/Corrected'}
            submission_text = submission_map.get(form_data.get('submission_type'), form_data.get('submission_type'))
            lines.append(f"• Submission Type: {submission_text}")
        
        if form_data.get('application_type'):
            app_type_map = {'1': 'New', '2': 'Continuation', '3': 'Revision'}
            app_type_text = app_type_map.get(form_data.get('application_type'), form_data.get('application_type'))
            lines.append(f"• Application Type: {app_type_text}")
        
        lines.append("")
        
        if validation_errors:
            lines.append("Validation Status: FAILED")
            lines.append("Errors:")
            for i, error in enumerate(validation_errors, 1):
                lines.append(f"{i}. {error}")
        else:
            lines.append("Validation Status: PASSED")
            lines.append("All validation checks passed successfully.")
        
        lines.append("")
        lines.append("What to check:")
        lines.append("• Verify the funding opportunity code exactly matches the announcement (case, hyphens, spaces — no trailing spaces)")
        lines.append("• Ensure you entered the announcement/code field (not only the title) or re-select the opportunity from the form's list/dropdown if available")
        lines.append("• If the code is correct and still fails, confirm you're using the current solicitation number with your program contact or support channel")
        
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
            'funding': lambda: f"Federal Funding: ${form_data.get('federal_estimated_funding') or 0:,.2f}, Total: ${form_data.get('total_estimated_funding') or 0:,.2f}",
            'budget': lambda: f"Total Budget: ${form_data.get('total_estimated_funding') or 0:,.2f}",
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
                except:
                    pass
        
        return "\n".join(relevant_fields) if relevant_fields else ""
    
    def _build_fallback_analysis(self, form_data: Dict[str, Any], validation_errors: List[str]) -> str:
        """Build basic analysis when AI service is not available."""
        if validation_errors:
            status = "FAILED"
            status_icon = "❌"
            error_list = "<br>".join([f"• {error}" for error in validation_errors])
            message = f"<strong>Form Status: Not Ready for Submission</strong> {status_icon}<br><br>Validation issues found:<br>{error_list}<br><br>Please correct these errors before submitting."
        else:
            status = "PASSED"
            status_icon = "✅"
            message = f"<strong>Form Status: Ready for Submission</strong> {status_icon}<br><br>All validation checks passed successfully.<br><br>Your SF-424 form is complete and ready for submission."
        
        return message
