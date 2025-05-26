import PyPDF2
import docx # from python-docx
import mimetypes # Standard Python library

def extract_text_from_file(file_obj):
    """
    Extracts text content from an in-memory uploaded file object.
    Supports PDF, DOCX, and TXT files.
    """
    text = ""
    # Ensure file pointer is at the beginning for reading
    if hasattr(file_obj, 'seek') and callable(file_obj.seek):
        file_obj.seek(0)

    # Try to get the filename to guess MIME type; fallback if not available
    file_name = getattr(file_obj, 'name', 'unknown_file_type')
    mime_type, _ = mimetypes.guess_type(file_name)
    # If mimetypes couldn't guess from name (e.g. for InMemoryUploadedFile),
    # check content_type if available
    if not mime_type and hasattr(file_obj, 'content_type'):
        mime_type = file_obj.content_type

    try:
        if mime_type == 'application/pdf' or file_name.lower().endswith('.pdf'):
            reader = PyPDF2.PdfReader(file_obj)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text: # Ensure text was extracted
                    text += page_text + "\n"
        elif mime_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword'] or \
             file_name.lower().endswith('.docx') or file_name.lower().endswith('.doc'):
            # python-docx primarily handles .docx. For .doc, it might be limited or require other tools.
            if file_name.lower().endswith('.docx'):
                doc = docx.Document(file_obj)
                for para in doc.paragraphs:
                    text += para.text + "\n"
            else: # Basic attempt for .doc or if type is 'application/msword'
                try:
                    # This is a very naive attempt for .doc, might not work well
                    text = file_obj.read().decode('latin-1', errors='ignore') # Or 'cp1252'
                except Exception as e_doc:
                    text = f"Could not reliably extract text from .doc file: {e_doc}\n"
        elif mime_type == 'text/plain' or file_name.lower().endswith('.txt'):
            text = file_obj.read().decode('utf-8', errors='ignore') # Be robust with decoding
        else:
            # Fallback: try to read as text if it's an unknown but potentially text-based type
            try:
                possible_text = file_obj.read().decode('utf-8', errors='ignore')
                # A simple check: if it contains many non-printable chars, it's likely not plain text.
                if sum(1 for char in possible_text[:500] if not char.isprintable() and char not in '\n\r\t') < 50:
                    text = possible_text
                else:
                    text = "Unsupported file type or content not recognized as plain text."
            except Exception:
                text = f"Unsupported file type ({mime_type or 'unknown'}). Could not decode as text."

        if not text.strip(): # If no text was extracted, provide a default message
            text = "No text content could be extracted from the document."

    except Exception as e:
        print(f"Error extracting text from '{file_name}' (MIME: {mime_type}): {str(e)}")
        text = f"An error occurred during text extraction: {str(e)}"
    finally:
        # Reset file pointer again so Django can save the file if it needs to
        if hasattr(file_obj, 'seek') and callable(file_obj.seek):
            file_obj.seek(0)
    return text.strip()