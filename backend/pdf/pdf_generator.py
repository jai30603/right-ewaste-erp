import os
from flask import render_template
from backend.pdf.playwright_service import playwright_service

def prepare_html_for_playwright(html_content):
    """
    Translates relative static paths (like images, CSS, and fonts) in HTML 
    to absolute local file:/// paths so Chromium can render them offline.
    """
    # Get absolute path to the backend directory
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    backend_dir_url = backend_dir.replace('\\', '/')
    if not backend_dir_url.endswith('/'):
        backend_dir_url += '/'
        
    prepared_html = html_content
    # Replace standard /static/ references with file:/// absolute paths
    prepared_html = prepared_html.replace('href="/static/', f'href="file:///{backend_dir_url}static/')
    prepared_html = prepared_html.replace('src="/static/', f'src="file:///{backend_dir_url}static/')
    prepared_html = prepared_html.replace('url(\'/static/', f'url(\'file:///{backend_dir_url}static/')
    prepared_html = prepared_html.replace('url("/static/', f'url("file:///{backend_dir_url}static/')
    
    # Replace relative static/ references just in case
    prepared_html = prepared_html.replace('href="static/', f'href="file:///{backend_dir_url}static/')
    prepared_html = prepared_html.replace('src="static/', f'src="file:///{backend_dir_url}static/')
    prepared_html = prepared_html.replace('url(\'static/', f'url(\'file:///{backend_dir_url}static/')
    prepared_html = prepared_html.replace('url("static/', f'url("file:///{backend_dir_url}static/')
    
    return prepared_html

def compile_html_to_pdf(html_content, margin=None, format="A4", landscape=False):
    """
    Directly compiles any HTML content string to PDF bytes using Playwright.
    """
    prepared_html = prepare_html_for_playwright(html_content)
    return playwright_service.html_to_pdf(prepared_html, margin=margin, format=format, landscape=landscape)

def number_to_words(number):
    try:
        number = float(number)
    except (TypeError, ValueError):
        return ""
        
    if number == 0:
        return "Zero Rupees Only"
        
    # Split into Rupees and Paise
    rupees = int(number)
    paise = int(round((number - rupees) * 100))
    
    def _convert_below_thousand(num):
        ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
                "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
                "Seventeen", "Eighteen", "Nineteen"]
        tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
        
        words = ""
        if num >= 100:
            words += ones[num // 100] + " Hundred "
            num %= 100
        if num >= 20 or num >= 20: # Keep standard checks
            words += tens[num // 10] + " "
            num %= 10
        if num > 0 and num < 20:
            words += ones[num] + " "
        elif num > 0:
            words += ones[num] + " "
        return words.strip()

    def _convert_to_indian_words(num):
        if num == 0:
            return ""
            
        chunks = [
            (10000000, "Crore"),
            (100000, "Lakh"),
            (1000, "Thousand"),
            (1, "")
        ]
        
        words = ""
        temp = num
        for divisor, label in chunks:
            part = temp // divisor
            if part > 0:
                words += _convert_below_thousand(part) + " " + label + " "
                temp %= divisor
        return words.strip()

    rupee_words = _convert_to_indian_words(rupees)
    paise_words = _convert_below_thousand(paise)
    
    result = ""
    if rupee_words:
        result += "Rupees " + rupee_words
    if paise_words:
        if result:
            result += " and "
        result += paise_words + " Paise"
    result += " Only"
    return result.strip().replace("  ", " ")

def render_to_pdf(template_name, context, margin=None, format="A4", landscape=False):
    """
    Renders a Jinja2 template and compiles it into PDF bytes using Playwright.
    """
    context["number_to_words"] = number_to_words
    html_content = render_template(template_name, **context)
    return compile_html_to_pdf(html_content, margin=margin, format=format, landscape=landscape)

def render_url_to_pdf(url, landscape=False):
    """
    Instructs Playwright to navigate directly to the print URL and generate PDF.
    """
    return playwright_service.url_to_pdf(url, landscape=landscape)
