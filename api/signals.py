from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings

from .models import Project, Purchase, Wallet
from .emails import (
    send_templated_email,
    format_date,
    ORG_NAME,
    SENDER_NAME,
    SENDER_TITLE,
    SUPPORT_EMAIL,
    render_certificate_pdf,
    DEFAULT_FROM,
)
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def _user_email(user: User) -> str:
    return user.email or user.username


@receiver(pre_save, sender=Project)
def _capture_prev_status(sender, instance: Project, **kwargs):
    # Store previous status on the instance for comparison in post_save
    if instance.pk:
        try:
            prev = Project.objects.get(pk=instance.pk)
            instance._old_status = prev.status
        except Project.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Project)
def notify_project_approved(sender, instance: Project, created, **kwargs):
    # Trigger only on transition to Verified from a non-Verified state
    if created:
        return
    if not (instance.status == 'Verified' and getattr(instance, '_old_status', None) != 'Verified'):
        return

    try:
        wallet = Wallet.ensure(instance.ngo)
    except Exception:
        wallet = None

    ctx = {
        'ngo_name': instance.ngo.get_full_name() or instance.ngo.username,
        'project_name': instance.title,
        'credits': instance.credits,
        'wallet_id': wallet.address if wallet else 'N/A',
        'issue_date': format_date(instance.updated_at),
        'dashboard_link': settings.DASHBOARD_URL if hasattr(settings, 'DASHBOARD_URL') else 'http://127.0.0.1:8080/',
        'org_name': ORG_NAME,
        'sender_name': SENDER_NAME,
        'sender_title': SENDER_TITLE,
        'support_email': SUPPORT_EMAIL,
    }

    subject = 'Verification: Project Approved — Credits Issued to Your Wallet'
    to = [_user_email(instance.ngo)]
    send_templated_email(subject, 'api/emails/ngo_project_approved.html', ctx, to)


@receiver(post_save, sender=Purchase)
def notify_purchase(sender, instance: Purchase, created, **kwargs):
    if not created:
        return

    # 1) Email buyer (corporate)
    buyer = instance.corporate
    seller = instance.project.ngo

    try:
        buyer_wallet = Wallet.ensure(buyer)
    except Exception:
        buyer_wallet = None

    ctx_buyer = {
        'ngo_name': seller.get_full_name() or seller.username,
        'company_name': buyer.get_full_name() or buyer.username,
        'buyer_wallet_id': buyer_wallet.address if buyer_wallet else 'N/A',
        'credits': instance.credits,
        'transaction_id': instance.id,
        'purchase_date': format_date(instance.timestamp),
        'dashboard_link': settings.DASHBOARD_URL if hasattr(settings, 'DASHBOARD_URL') else 'http://127.0.0.1:8080/',
        'certificate_link': (settings.DASHBOARD_URL if hasattr(settings, 'DASHBOARD_URL') else 'http://127.0.0.1:8080/') + f"corporate/certificate/{instance.id}/download/",
        'org_name': ORG_NAME,
        'sender_name': SENDER_NAME,
        'sender_title': SENDER_TITLE,
    }
    subject_buyer = f"Purchase Confirmation — Credits Purchased from {ctx_buyer['ngo_name']} and Issued to Your Wallet"
    # Send templated purchase confirmation email to buyer (no automatic certificate generation)
    send_templated_email(subject_buyer, 'api/emails/corporate_purchase_confirmation.html', ctx_buyer, [_user_email(buyer)])

    # 2) Email seller (NGO) summary of purchases and remaining
    total_issued = instance.project.credits
    purchased = sum(p.credits for p in Purchase.objects.filter(project=instance.project))
    remaining = max(total_issued - purchased, 0)

    # Build a small recent list (latest 5)
    recent = Purchase.objects.filter(project=instance.project).order_by('-timestamp')[:5]
    recent_list = [
        {
            'id': p.id,
            'buyer': p.corporate.get_full_name() or p.corporate.username,
            'credits': p.credits,
            'date': format_date(p.timestamp),
        }
        for p in recent
    ]

    ctx_ngo = {
        'ngo_name': seller.get_full_name() or seller.username,
        'project_name': instance.project.title,
        'total_issued': total_issued,
        'number_purchased': purchased,
        'remaining': remaining,
        'purchasers': ", ".join([f"{r['buyer']} — {r['credits']} credits" for r in recent_list]) or '—',
        'recent': recent_list,
        'dashboard_link': settings.DASHBOARD_URL if hasattr(settings, 'DASHBOARD_URL') else 'http://127.0.0.1:8080/',
        'org_name': ORG_NAME,
        'sender_name': SENDER_NAME,
        'sender_title': SENDER_TITLE,
        'support_email': SUPPORT_EMAIL,
    }
    subject_ngo = 'Update: Credits Purchased by Companies — Remaining Balance Available for Sale'
    send_templated_email(subject_ngo, 'api/emails/ngo_credits_purchased_summary.html', ctx_ngo, [_user_email(seller)])
