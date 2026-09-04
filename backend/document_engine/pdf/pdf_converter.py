from backend.pdf.pdf_generator import compile_html_to_pdf as playwright_compile_html_to_pdf

def convert_html_to_pdf(html_content):
    """
    Converts pure HTML text string into binary PDF bytes using Playwright.
    """
    # Use standard margins
    margin = {"top": "0.5in", "bottom": "0.5in", "left": "0.6in", "right": "0.6in"}
    return playwright_compile_html_to_pdf(html_content, margin=margin)
