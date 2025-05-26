# your_project_name/backend/api/views.py

import os # Standard Python library for OS interaction (file paths, deletion)
from dotenv import load_dotenv # For loading environment variables from .env

from django.contrib.auth.models import User # Django's built-in User model
# from django.conf import settings # Not strictly needed here with current os.path usage

from rest_framework import generics, viewsets, permissions, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

import google.generativeai as genai # Gemini API client

from .models import Document # Your Document model
from .serializers import UserSerializer, DocumentSerializer # Your serializers
from .utils import extract_text_from_file # Your text extraction utility

# Load environment variables from .env file located in 'your_project_name/backend/'
# Ensure .env is in your_project_name/backend/
load_dotenv()

# --- Authentication Related Views ---

class RegisterView(generics.CreateAPIView):
    """
    API endpoint for user registration.
    Allows any user (even unauthenticated) to create a new account.
    """
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,) # No authentication required to register
    serializer_class = UserSerializer # Uses UserSerializer to validate and create user

class RefreshTokenSerializer(serializers.Serializer): # Specific serializer for logout payload
    refresh = serializers.CharField()

    def validate_refresh(self, value):
        # Optionally, you could add more validation for the refresh token format if needed
        if not value: # Ensure refresh token is not empty
             raise serializers.ValidationError("Refresh token cannot be empty.")
        return value

class LogoutView(generics.GenericAPIView):
    """
    API endpoint for user logout.
    Requires a valid refresh token in the request body to blacklist it.
    """
    permission_classes = (permissions.IsAuthenticated,) # User must be logged in to logout
    serializer_class = RefreshTokenSerializer # Validate the request payload

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True) # Validate presence and basic format of 'refresh' token
            refresh_token = serializer.validated_data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist() # Blacklist the refresh token
            return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)
        except TokenError: # Handles cases like token already blacklisted, expired, or malformed
            return Response({"error": "Invalid or expired refresh token."}, status=status.HTTP_401_UNAUTHORIZED)
        except serializers.ValidationError as e: # Handles if 'refresh' field is missing or invalid based on serializer
            return Response({"error": "Refresh token is required.", "details": e.detail}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e: # Catch-all for other unexpected errors
            print(f"Unexpected error during logout: {str(e)}") # Log for server admin
            return Response({"error": "An unexpected error occurred during logout."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# --- Document Management ViewSet ---

class DocumentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing user documents.
    Provides CRUD operations (List, Create, Retrieve, Update, Destroy)
    and a custom 'ask_ai' action for querying documents.
    """
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated] # All document actions require authentication

    def get_queryset(self):
        """
        Ensures users only see their own documents, ordered by most recently uploaded.
        """
        return Document.objects.filter(user=self.request.user).order_by('-uploaded_at')

    def get_serializer_context(self):
        """
        Passes the request object to the serializer context.
        This is used by DocumentSerializer to generate full URLs for 'file_url'.
        """
        return {'request': self.request}

    def perform_create(self, serializer):
        """
        Called when a new document is being created (POST request).
        - Associates the document with the currently authenticated user.
        - Extracts text from the uploaded file.
        """
        document_file = self.request.FILES.get('file') # Get the uploaded file from the request

        # Serializer should handle 'file' field validation (e.g. if it's required)
        # If file is optional and not provided, handle appropriately
        extracted_text = ""
        if document_file:
            extracted_text = extract_text_from_file(document_file)
        else:
            # If 'file' is optional and not provided, decide on default extracted_text
            # For this app, a document without a file might not make sense for AI Q&A
            # Consider making 'file' required in the serializer or handling this case
            pass # Assuming 'file' is required by the serializer for now

        serializer.save(user=self.request.user, extracted_text=extracted_text)

    def perform_update(self, serializer):
        """
        Called when an existing document is being updated (PUT or PATCH request).
        - If a new file is uploaded, the old physical file is deleted (after successful save).
        - Text is re-extracted from the new file.
        """
        document_instance = serializer.instance # The existing document object before update
        old_file_path = None
        if document_instance.file and hasattr(document_instance.file, 'path'):
            old_file_path = document_instance.file.path # Get path of the current physical file

        # Check if a new file is part of the update data (will be in serializer.validated_data if so)
        new_file_uploaded = 'file' in serializer.validated_data
        extracted_text_to_save = document_instance.extracted_text # Default to old text

        if new_file_uploaded:
            new_file_obj = serializer.validated_data['file'] # The new UploadedFile object
            if new_file_obj: # Check if a new file object actually exists
                 extracted_text_to_save = extract_text_from_file(new_file_obj)
            else: # A 'file': null might have been sent to clear the file
                 extracted_text_to_save = "" # Clear extracted text if file is cleared


        # Save the instance. If a new file was uploaded and validated,
        # serializer.save() will update document_instance.file field automatically.
        # If 'file': null was sent (and model field allows null), it will clear the file field.
        updated_instance = serializer.save(extracted_text=extracted_text_to_save)

        # After successful save, if a new file was uploaded (or file was cleared) and there was an old file, delete the old one
        if (new_file_uploaded or (not updated_instance.file and old_file_path)) and old_file_path:
            # Ensure the file path actually changed or was cleared, and the old file exists
            file_effectively_changed = True
            if updated_instance.file and hasattr(updated_instance.file, 'path'):
                if updated_instance.file.path == old_file_path:
                    file_effectively_changed = False # Same file path, don't delete

            if file_effectively_changed and os.path.isfile(old_file_path):
                try:
                    os.remove(old_file_path)
                except OSError as e:
                    print(f"Error deleting old file {old_file_path} after update: {e}") # Log error


    def perform_destroy(self, instance):
        """
        Called when a document is being deleted (DELETE request).
        - Deletes the associated physical file from storage (after DB record deletion).
        """
        file_path_to_delete = None
        if instance.file and hasattr(instance.file, 'path'):
            file_path_to_delete = instance.file.path

        # First, delete the database record
        instance.delete()

        # After successful DB deletion, delete the physical file
        if file_path_to_delete and os.path.isfile(file_path_to_delete):
            try:
                os.remove(file_path_to_delete)
            except OSError as e:
                print(f"Error deleting physical file {file_path_to_delete} after DB record deletion: {e}")


    @action(detail=True, methods=['post'], url_path='ask-ai', permission_classes=[permissions.IsAuthenticated])
    def ask_ai(self, request, pk=None):
        """
        Custom API action to ask a question about a specific document using the Gemini AI.
        Accessible via POST to /api/documents/{document_id}/ask-ai/
        Expects a JSON payload with a 'question' field.
        """
        document = self.get_object() # Retrieve the specific document by its primary key
        question = request.data.get('question')

        if not question or not isinstance(question, str) or not question.strip():
            return Response({"error": "A non-empty 'question' string is required in the request body."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if extracted text is valid for querying
        unsuitable_text_messages = [
            "No text content could be extracted from the document.",
            "Unsupported file type or content not recognized as plain text.",
            "Unsupported file type (unknown). Could not decode as text.",
            "An error occurred during text extraction", # Check for startswith this
            "Could not reliably extract text from .doc file"
        ]
        if not document.extracted_text or \
           document.extracted_text in unsuitable_text_messages or \
           any(document.extracted_text.startswith(msg_start) for msg_start in ["An error occurred during text extraction", "Unsupported file type"]):
            return Response({
                "error": "Document content is not available or suitable for AI querying.",
                "extracted_text_status": document.extracted_text # Provide status for debugging
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            gemini_api_key = os.getenv("GEMINI_API_KEY")
            if not gemini_api_key:
                print("CRITICAL SERVER ERROR: GEMINI_API_KEY environment variable is not set.") # Server log
                return Response({"error": "AI service is currently unavailable. Please contact support."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            genai.configure(api_key=gemini_api_key)
            model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest") # Allow model override via .env
            model = genai.GenerativeModel(model_name)

            # Enhanced prompt for better AI guidance
            prompt = f"""You are an AI assistant for a Document Management Portal.
Your sole task is to answer the user's question based *strictly and exclusively* on the content of the document text provided below.
- If the answer is found in the document, provide the answer directly.
- If the answer cannot be found in the document text, you MUST respond with the exact phrase: "The answer to your question cannot be found in the provided document."
- Do NOT use any external knowledge, make assumptions, or infer information beyond what is explicitly stated in the document text.
- Do NOT add any conversational fluff or apologies if the answer is not found.

Provided Document Text:
---
{document.extracted_text}
---

User's Question: {question}

Answer:"""

            ai_response = model.generate_content(prompt)
            
            answer_text = "The AI model did not return a text response." # Default if no text
            if hasattr(ai_response, 'text') and ai_response.text:
                answer_text = ai_response.text.strip()
            elif hasattr(ai_response, 'parts'): # Sometimes response is in parts
                full_text_parts = [part.text for part in ai_response.parts if hasattr(part, 'text')]
                if full_text_parts:
                    answer_text = "".join(full_text_parts).strip()
            
            # Fallback if prompt expectations are not met by the model (e.g. model refuses to answer)
            if not answer_text and hasattr(ai_response, 'prompt_feedback') and ai_response.prompt_feedback.block_reason:
                answer_text = f"The AI model blocked the response. Reason: {ai_response.prompt_feedback.block_reason_message or ai_response.prompt_feedback.block_reason}"


            return Response({
                "answer": answer_text,
                "question": question,
                "document_id": document.id
            })

        except Exception as e:
            print(f"AI Query Error (Document ID: {document.id}): {str(e)}") # Detailed server log
            # More specific error handling could be added here for different genai exceptions
            return Response({"error": "An error occurred while processing your question with the AI. Please try again later or contact support if the issue persists."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)