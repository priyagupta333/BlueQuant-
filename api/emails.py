from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from datetime import datetime
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings
from .models import Purchase
import os
import re


DEFAULT_FROM = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.org')
SUPPORT_EMAIL = getattr(settings, 'SUPPORT_EMAIL', 'support@example.org')
SUPPORT_PHONE = getattr(settings, 'SUPPORT_PHONE', '+00-0000-000-000')
ORG_NAME = getattr(settings, 'ORG_NAME', 'BlueQuant')
SENDER_TITLE = getattr(settings, 'SENDER_TITLE', 'Support Team')
SENDER_NAME = getattr(settings, 'SENDER_NAME', ORG_NAME)
DASHBOARD_URL = getattr(settings, 'DASHBOARD_URL', 'http://127.0.0.1:8080/')


def send_templated_email(subject: str, template_name: str, context: dict, to: list[str]):
    html = render_to_string(template_name, context)
    text = strip_tags(html)
    msg = EmailMultiAlternatives(subject, text, DEFAULT_FROM, to)
    msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=True)


def format_date(dt: datetime | None) -> str:
    if not dt:
        dt = datetime.now()
    return dt.strftime('%d %B %Y')


def render_certificate_pdf(purchase: Purchase) -> str | None:
    """Render a PDF certificate for a purchase and store it.

    Returns the storage path (relative) or None on failure.
    """
    try:
        project = purchase.project
        corporate = purchase.corporate
        ngo = project.ngo

        # Simple CO2e estimate: assume 1 credit = 1 tCO2e unless you have a model
        co2e = float(purchase.credits)

        def format_display_name(value: str) -> str:
            if not value:
                return ''
            # If it's an email, extract the local-part and turn separators into spaces
            if '@' in value:
                local = value.split('@', 1)[0]
                # replace dots/underscores/hyphens with spaces
                cleaned = re.sub(r'[._-]+', ' ', local)
                return cleaned.replace('.', ' ').strip().title()
            # Otherwise title-case the name
            return ' '.join([p.capitalize() for p in value.split()])

        ctx = {
            'credits': purchase.credits,
            'co2e': f"{co2e:.0f}",
            'company_name': format_display_name(corporate.get_full_name() or corporate.username),
            'ngo_name': format_display_name(ngo.get_full_name() or ngo.username),
            'beneficiary_name': getattr(settings, 'BENEFICIARY_NAME', 'Government of India'),
            'issue_date': format_date(purchase.timestamp),
            'certificate_id': f"BC-{purchase.id:06d}",
            'seal_url': getattr(settings, 'CERT_SEAL_URL', ''),
        }

        html = render_to_string('api/certificates/purchase_certificate.html', ctx)

        pdf_bytes = None
        # Try WeasyPrint first
        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html, base_url=getattr(settings, 'BASE_DIR', None)).write_pdf()
        except Exception:
            # Fallback to xhtml2pdf
            try:
                from xhtml2pdf import pisa
                from io import BytesIO
                out = BytesIO()
                pisa.CreatePDF(html, dest=out)
                pdf_bytes = out.getvalue()
            except Exception:
                pdf_bytes = None

        # Final fallback: generate a simple PDF using ReportLab (pure-Python)
        if not pdf_bytes:
            try:
                from reportlab.lib.pagesizes import A4
                from reportlab.pdfgen import canvas
                from reportlab.lib.units import mm
                from io import BytesIO
                buf = BytesIO()
                c = canvas.Canvas(buf, pagesize=A4)
                width, height = A4

                # Attempt to load a decorative frame and seal from static files if present.
                frame_path = os.path.join(getattr(settings, 'BASE_DIR', ''), 'api', 'static', 'api', 'images', 'certificate_frame.png')
                seal_path = os.path.join(getattr(settings, 'BASE_DIR', ''), 'api', 'static', 'api', 'images', 'certificate_seal.png')
                try:
                    if os.path.exists(frame_path):
                        c.drawImage(frame_path, 0, 0, width=width, height=height)
                except Exception:
                    pass

                # Title
                c.setFont("Times-Bold", 36)
                c.drawCentredString(width / 2.0, height - 45 * mm, "Carbon Credit Certificate")

                # Main block
                c.setFont("Times-Roman", 12)
                text_y = height - 70 * mm
                c.setFont("Times-Roman", 14)
                c.drawCentredString(width / 2.0, text_y, f"This certificate confirms that")
                text_y -= 8 * mm
                c.setFont("Times-Bold", 18)
                c.drawCentredString(width / 2.0, text_y, f"{ctx['credits']} carbon credits")
                text_y -= 9 * mm
                c.setFont("Times-Roman", 12)
                c.drawCentredString(width / 2.0, text_y, f"equivalent to {ctx['co2e']} metric tonnes of CO2e")
                text_y -= 12 * mm
                c.setFont("Times-Bold", 16)
                c.drawCentredString(width / 2.0, text_y, ctx['company_name'])

                # From / NGO
                text_y -= 24 * mm
                c.setFont("Times-Roman", 12)
                c.drawString(40 * mm, text_y, "From")
                c.setFont("Times-Bold", 14)
                c.drawCentredString(width / 2.0, text_y, ctx['ngo_name'])

                # On behalf
                text_y -= 12 * mm
                c.setFont("Times-Italic", 14)
                c.drawCentredString(width / 2.0, text_y, ctx['beneficiary_name'])

                # Seal if available
                try:
                    if os.path.exists(seal_path):
                        seal_w = 24 * mm
                        seal_h = 24 * mm
                        c.drawImage(seal_path, (width - seal_w) / 2.0, 45 * mm, width=seal_w, height=seal_h, mask='auto')
                except Exception:
                    pass

                # Footer
                c.setFont("Times-Roman", 10)
                c.drawCentredString(width / 2.0, 30 * mm, f"Purchased through {ORG_NAME}")
                c.drawCentredString(width / 2.0, 25 * mm, f"Date of Issue: {ctx['issue_date']}")
                c.drawCentredString(width / 2.0, 20 * mm, f"Certificate ID: {ctx['certificate_id']}")

                c.showPage()
                c.save()
                buf.seek(0)
                pdf_bytes = buf.getvalue()
            except Exception as e:
                # If even ReportLab isn't available or fails, log for debugging and return None
                try:
                    import logging
                    logging.exception("ReportLab fallback failed: %s", e)
                except Exception:
                    print("ReportLab fallback failed:", e)
                pdf_bytes = None

        if not pdf_bytes:
            return None

        filename = f"certificates/purchase_{purchase.id}.pdf"
        default_storage.save(filename, ContentFile(pdf_bytes))
        # Update model (do not recurse signals; save minimal fields)
        Purchase.objects.filter(pk=purchase.pk).update(certificate=filename)
        return filename
    except Exception:
        return None
