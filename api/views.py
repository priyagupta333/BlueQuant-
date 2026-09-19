from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import User, Group
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, FileResponse, HttpResponseForbidden
from django.db import models
from django.db.models import Q
from .models import (
    Project, Purchase, NGOLogin, CorporateLogin, AdminLogin, Wallet, 
    Tender, TenderApplication, UserProfile, FieldDataSubmission, 
    FieldImage, SatelliteImageSubmission, SatelliteImage
)
from .forms import NGORegisterForm, CorporateRegisterForm, TenderForm, TenderApplicationForm, TenderV2Form, ProposalV2Form
from .blockchain import get_chain
from .blockchain_service import BlockchainService
from .forms import ProjectForm
import joblib
import os
import logging

logger = logging.getLogger(__name__)
from PIL import Image
import numpy as np
import json
import secrets
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# --------------------
# Role helpers
# --------------------
def is_ngo(user):
    return user.groups.filter(name="NGO").exists()

def is_admin(user):
    return user.groups.filter(name="Admin").exists() or user.is_superuser

def is_corporate(user):
    return user.groups.filter(name="Corporate").exists()


# --------------------
# Role mapping helpers
# --------------------
def get_user_role(user: User) -> str | None:
    """Return canonical role string for a user.
    Priority: explicit profile.role -> group membership -> superuser/staff.
    Returns one of: 'admin','corporate','ngo','field_officer','isro_admin' or None.
    """
    # If profile exists and has role, trust it
    try:
        if hasattr(user, "profile") and user.profile.role:
            return user.profile.role
    except Exception:
        pass

    # Fallback to groups
    if user.is_superuser or user.groups.filter(name="Admin").exists():
        return "admin"
    if user.groups.filter(name="Corporate").exists():
        return "corporate"
    if user.groups.filter(name="NGO").exists():
        return "ngo"
    # Unknown
    return None


def ensure_user_profile(user: User) -> UserProfile:
    """Ensure a UserProfile exists; if created, infer role from groups/superuser."""
    try:
        return user.profile
    except Exception:
        pass
    role = get_user_role(user) or ("admin" if (user.is_superuser or user.is_staff) else "ngo")
    return UserProfile.objects.create(user=user, role=role)


# --------------------
# ML Model Setup
# --------------------
MODEL_PATH = os.path.join(settings.BASE_DIR, "dataset", "agbm_model.joblib")
_model = None  # cache for lazy loading

def get_model():
    """Lazy-load ML model to avoid startup crash."""
    global _model
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"ML model not found at {MODEL_PATH}")
        # The saved file may be a dict payload {"model": model_obj, "feature_cols": [...]}
        # or a plain sklearn estimator. Keep the raw payload so callers can handle both.
        _model = joblib.load(MODEL_PATH)
    return _model

def preprocess_image(image_path):
    """Load and preprocess image for ML model."""
    img = Image.open(image_path).convert("RGB")
    img = img.resize((128, 128))  # match training size for legacy models
    arr = np.asarray(img, dtype=np.float32)
    arr = arr.flatten() / 255.0        # normalize
    return arr


def extract_simple_features_from_image(image_path):
    """Extract simple mean-R/G/B and a vegetation index from an RGB image.

    Returns a dict with keys: mean_red, mean_green, mean_blue, vegetation_index
    This mirrors the lightweight extractor used when the model was trained.
    """
    try:
        img = Image.open(image_path).convert("RGB")
    except FileNotFoundError:
        raise FileNotFoundError(f"Image not found at {image_path}")

    arr = np.asarray(img, dtype=np.float32)
    # Pillow loads RGB by default
    mean_r = float(arr[:, :, 0].mean())
    mean_g = float(arr[:, :, 1].mean())
    mean_b = float(arr[:, :, 2].mean())
    vi = float((mean_g - mean_r) / (mean_g + mean_r + 1e-6))
    return {
        "mean_red": mean_r,
        "mean_green": mean_g,
        "mean_blue": mean_b,
        "vegetation_index": vi,
    }

def predict_credits(area, image_path):
    """Backward-compatible wrapper: return integer credits from detailed prediction."""
    details = predict_details(area, image_path)
    if details is None:
        return 0
    return int(round(details.get("credits", 0)))


def predict_details(area, image_path):
    """Return full prediction details dict for a given area and image_path.

    Keys returned: biomass_t_per_ha, area_ha, biomass_total_t, carbon_t, co2e_t, credits
    Returns None on error.
    """
    try:
        payload = get_model()

        if isinstance(payload, dict):
            model = payload.get("model")
            feature_cols = payload.get("feature_cols")
        else:
            model = payload
            feature_cols = None

        area_f = float(area)

        if feature_cols:
            feats = extract_simple_features_from_image(image_path)
            feature_row = {
                "red": feats.get("mean_red"),
                "green": feats.get("mean_green"),
                "blue": feats.get("mean_blue"),
                "vi": feats.get("vegetation_index"),
            }
            ordered = [feature_row.get(c, 0.0) for c in feature_cols]
            x = np.array(ordered, dtype=float).reshape(1, -1)
            agbm_pred = float(model.predict(x)[0])
        else:
            img_features = preprocess_image(image_path)
            x = np.hstack([img_features]).reshape(1, -1)
            agbm_pred = float(model.predict(x)[0])

        biomass_t_per_ha = float(agbm_pred)
        biomass_total = biomass_t_per_ha * area_f
        carbon_t = biomass_total * 0.5
        co2e_t = carbon_t * 44.0 / 12.0
        credits = float(co2e_t)

        return {
            "biomass_t_per_ha": biomass_t_per_ha,
            "area_ha": area_f,
            "biomass_total_t": biomass_total,
            "carbon_t": carbon_t,
            "co2e_t": co2e_t,
            "credits": credits,
        }
    except Exception:
        return None


# --------------------
# Public Views
# --------------------
def home(request):
    return render(request, "api/home/index.html")


def about(request):
    """Render About page with leaderboards: top NGOs by credits generated and
    top companies by credits purchased.
    """
    from django.db.models import Sum

    # Top NGOs by credits generated (only count Verified projects)
    ngo_agg = (
        Project.objects.filter(status="approved")
        .values("ngo__id", "ngo__username", "ngo__email")
        .annotate(total_credits=Sum("credits"))
        .order_by("-total_credits")
    )
    top_ngos = []
    for row in ngo_agg[:10]:
        top_ngos.append({
            "id": row.get("ngo__id"),
            "username": row.get("ngo__username"),
            "email": row.get("ngo__email"),
            "credits": int(row.get("total_credits") or 0),
        })

    # Top 5 companies by credits purchased
    corp_agg = (
        Purchase.objects.values("corporate__id", "corporate__username", "corporate__email")
        .annotate(total_purchased=Sum("credits"))
        .order_by("-total_purchased")
    )
    top_companies = []
    for row in corp_agg[:5]:
        top_companies.append({
            "id": row.get("corporate__id"),
            "username": row.get("corporate__username"),
            "email": row.get("corporate__email"),
            "purchased": int(row.get("total_purchased") or 0),
        })

    return render(request, "api/about.html", {"top_ngos": top_ngos, "top_companies": top_companies})

def register_ngo(request):
    if request.method == "POST":
        form = NGORegisterForm(request.POST, request.FILES, request=request)
        if form.is_valid():
            user = form.save()
            group, _ = Group.objects.get_or_create(name="NGO")
            user.groups.add(group)
            # Ensure profile with NGO role
            try:
                UserProfile.objects.get_or_create(user=user, defaults={"role": "ngo"})
            except Exception:
                pass
            # Clear OTP flags to avoid reuse
            try:
                for k in [
                    "otp_email_code",
                    "otp_email_verified",
                    "otp_verified_email_value",
                    "otp_phone_code",
                    "otp_phone_verified",
                    "otp_verified_phone_value",
                ]:
                    if k in request.session:
                        del request.session[k]
            except Exception:
                pass
            # Email generated password if we created one
            try:
                generated = getattr(form, "generated_password", None)
                if generated:
                    from django.core.mail import send_mail
                    subject = "Your BlueQuant Account Password"
                    body = (
                        "Welcome to BlueQuant!\n\n"
                        f"Your account has been created for {user.email}.\n"
                        f"Temporary Password: {generated}\n\n"
                        "For security, please log in and change your password immediately.\n"
                        f"Login: {getattr(settings, 'DASHBOARD_URL', request.build_absolute_uri('/login/'))}\n\n"
                        "Thank you."
                    )
                    send_mail(subject, body, getattr(settings, 'DEFAULT_FROM_EMAIL', None), [user.email], fail_silently=True)
            except Exception:
                logger.exception("Failed to send generated password email")
            messages.success(request, "Contributor registered. Please login.")
            # Redirect to login and preselect contributor role so the login page shows the right register link
            from django.urls import reverse
            return redirect(reverse('login') + '?role=contributor')
    else:
        form = NGORegisterForm(request=request)
    return render(request, "api/auth/register_ngo.html", {"form": form})


# --------------------
# OTP APIs for registration
# --------------------
from django.views.decorators.http import require_POST
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


def _generate_otp():
    return f"{secrets.randbelow(1000000):06d}"


@require_POST
def send_email_otp(request):
    email = request.POST.get("email", "").strip()
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"ok": False, "error": "Invalid email address"}, status=400)
    code = _generate_otp()
    request.session["otp_email_code"] = code
    request.session["otp_email_verified"] = False
    request.session["otp_verified_email_value"] = email
    # send email
    try:
        from django.core.mail import send_mail
        send_mail(
            subject="Your Email OTP",
            message=f"Your verification code is {code}. It expires in 10 minutes.",
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            recipient_list=[email],
            fail_silently=True,
        )
    except Exception:
        logger.exception("Failed to send email OTP")
    return JsonResponse({"ok": True})


@require_POST
def verify_email_otp(request):
    code = request.POST.get("code", "").strip()
    email = request.POST.get("email", "").strip()
    stored = request.session.get("otp_email_code")
    stored_email = request.session.get("otp_verified_email_value")
    if stored and stored_email == email and code == stored:
        request.session["otp_email_verified"] = True
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False, "error": "Invalid code"}, status=400)


@require_POST
def send_phone_otp(request):
    phone = request.POST.get("phone", "").strip()
    if not phone:
        return JsonResponse({"ok": False, "error": "Phone is required"}, status=400)
    code = _generate_otp()
    request.session["otp_phone_code"] = code
    request.session["otp_phone_verified"] = False
    request.session["otp_verified_phone_value"] = phone
    # For this environment, we log the SMS instead of integrating an SMS provider
    logger.info("Phone OTP for %s is %s", phone, code)
    return JsonResponse({"ok": True})


@require_POST
def verify_phone_otp(request):
    code = request.POST.get("code", "").strip()
    phone = request.POST.get("phone", "").strip()
    stored = request.session.get("otp_phone_code")
    stored_phone = request.session.get("otp_verified_phone_value")
    if stored and stored_phone == phone and code == stored:
        request.session["otp_phone_verified"] = True
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False, "error": "Invalid code"}, status=400)


def register_corporate(request):
    if request.method == "POST":
        form = CorporateRegisterForm(request.POST, request.FILES, request=request)
        if form.is_valid():
            user = form.save()
            group, _ = Group.objects.get_or_create(name="Corporate")
            user.groups.add(group)
            # Ensure profile with Corporate role
            try:
                UserProfile.objects.get_or_create(user=user, defaults={"role": "corporate"})
            except Exception:
                pass
            messages.success(request, "Corporate registered. Please login.")
            from django.urls import reverse
            return redirect(reverse('login') + '?role=corporate')
    else:
        form = CorporateRegisterForm(request=request)
    return render(request, "api/auth/register_corporate.html", {"form": form})


from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User, Group
from django.contrib import messages
from .models import NGOLogin, CorporateLogin, AdminLogin, FieldOfficerLogin, IsroAdminLogin
from django.urls import reverse
import logging


def user_login(request):
    # Determine selected role from querystring or POST to tailor registration links
    role = request.GET.get("role", "").lower()
    if request.method == "POST":
        role = request.POST.get("role", role)
        email = request.POST.get("email")   
        password = request.POST.get("password")

        # First try to authenticate directly (if user already exists in Django)
        user = authenticate(request, username=email, password=password)
        # If that fails, try resolving the user by email and authenticating with their actual username
        if not user:
            try:
                existing = User.objects.filter(email=email).first()
                if existing:
                    user = authenticate(request, username=existing.username, password=password)
            except Exception:
                pass

        if not user:
            # If user not found, check custom login tables
            def provision_user(group_name: str, explicit_role: str | None = None):
                group, _ = Group.objects.get_or_create(name=group_name)
                dj_user, created = User.objects.get_or_create(username=email, email=email)
                dj_user.set_password(password)
                if group_name == "Admin":
                    dj_user.is_staff = True
                dj_user.save()
                dj_user.groups.add(group)
                # Ensure a corresponding UserProfile role
                try:
                    role_map = {"Admin": "admin", "Corporate": "corporate", "NGO": "ngo", "FieldOfficer": "field_officer", "ISRO": "isro_admin"}
                    role_value = explicit_role or role_map.get(group_name, "ngo")
                    UserProfile.objects.get_or_create(user=dj_user, defaults={"role": role_value})
                except Exception:
                    pass
                return dj_user

            if NGOLogin.objects.filter(email=email, password=password).exists():
                provision_user("NGO")
                user = authenticate(request, username=email, password=password)

            elif CorporateLogin.objects.filter(email=email, password=password).exists():
                provision_user("Corporate")
                user = authenticate(request, username=email, password=password)

            elif AdminLogin.objects.filter(email=email, password=password).exists():
                provision_user("Admin")
                user = authenticate(request, username=email, password=password)

            elif FieldOfficerLogin.objects.filter(email=email, password=password).exists():
                # Use a group name that won't clash with existing ones but still creates a Group for potential permissions
                provision_user("FieldOfficer", explicit_role="field_officer")
                user = authenticate(request, username=email, password=password)

            elif IsroAdminLogin.objects.filter(email=email, password=password).exists():
                provision_user("ISRO", explicit_role="isro_admin")
                user = authenticate(request, username=email, password=password)

        if user:
            login(request, user)
            # Ensure a profile exists and get role
            profile = ensure_user_profile(user)
            role = profile.role or get_user_role(user)
            # Redirect based on role
            if role == "ngo":
                return redirect("ngo_dashboard")
            if role == "corporate":
                return redirect("corporate_dashboard")
            if role == "admin":
                return redirect("admin_dashboard")
            if role == "field_officer":
                return redirect("field_officer_dashboard")
            if role == "isro_admin":
                return redirect("isro_admin_dashboard")

            messages.error(request, "Your account doesn't have a recognized role. Please contact support.")
            logout(request)
        else:
            messages.error(request, "Invalid email or password.")

    return render(request, "api/auth/login.html", {"role": role})


def user_logout(request):
    logout(request)
    return redirect("home")


@login_required
@user_passes_test(is_corporate)
def request_certificate(request, purchase_id):
    """On-demand certificate generation and email sending for a purchase.

    POST only. Ensures the logged-in corporate user owns the purchase.
    Calls render_certificate_pdf (from api.emails) to produce and save PDF and
    then emails it to the buyer.
    """
    if request.method != "POST":
        return HttpResponseForbidden("POST required")

    purchase = get_object_or_404(Purchase, pk=purchase_id)
    if purchase.corporate != request.user:
        return HttpResponseForbidden("Not allowed")

    # Lazy import to avoid circular imports at module import time
    from .emails import render_certificate_pdf, DEFAULT_FROM
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags
    from django.core.files.storage import default_storage

    cert_path = render_certificate_pdf(purchase)
    if not cert_path:
        logging.exception("Certificate generation failed for purchase %s", purchase_id)
        return JsonResponse({"ok": False, "error": "Certificate generation failed"}, status=500)

    # Build and send email with attachment
    try:
        ctx = {
            'ngo_name': purchase.project.ngo.get_full_name() or purchase.project.ngo.username,
            'company_name': purchase.corporate.get_full_name() or purchase.corporate.username,
            'credits': purchase.credits,
            'transaction_id': purchase.id,
            'purchase_date': purchase.timestamp,
            'dashboard_link': settings.DASHBOARD_URL if hasattr(settings, 'DASHBOARD_URL') else 'http://127.0.0.1:8080/',
            'org_name': getattr(settings, 'ORG_NAME', 'BlueQuant'),
        }
        subject = f"Your Certificate for Purchase #{purchase.id}"
        html = render_to_string('api/emails/corporate_purchase_confirmation.html', ctx)
        text = strip_tags(html)
        buyer_email = purchase.corporate.email or purchase.corporate.username
        msg = EmailMultiAlternatives(subject, text, DEFAULT_FROM, [buyer_email])
        msg.attach_alternative(html, 'text/html')
        with default_storage.open(cert_path, 'rb') as f:
            msg.attach(f'certificate_{purchase.id}.pdf', f.read(), 'application/pdf')

        # Propagate SMTP/send errors so we can report back
        sent = msg.send(fail_silently=False)
        if not sent:
            logging.error('Email sent returned 0 for purchase %s to %s', purchase_id, buyer_email)
            return JsonResponse({"ok": False, "error": "Email not sent"}, status=500)

    except Exception as exc:
        logging.exception("Failed sending certificate email for purchase %s: %s", purchase_id, exc)
        return JsonResponse({"ok": False, "error": "Failed to send email"}, status=500)

    download_url = reverse('download_certificate', args=[purchase.id])
    return JsonResponse({"ok": True, "message": "Certificate generated and emailed", "download_url": download_url})


# --------------------
# NGO Views
# --------------------
@login_required
@user_passes_test(is_ngo)
def ngo_dashboard(request):
    projects = Project.objects.filter(ngo=request.user)
    # Recent tender application updates
    recent_apps = TenderApplication.objects.filter(ngo=request.user).order_by('-created_at')[:5]
    form = ProjectForm()
    stats = {
        "total": projects.count(),
        "pending": projects.filter(status="pending").count(),
        "verified": projects.filter(status="approved").count(),
        "credits": sum(p.credits for p in projects),
    }
    # Attach prediction details for display (non-blocking)
    for p in projects:
        p.pred_details = None
        if p.document:
            try:
                p.pred_details = predict_details(p.area, p.document.path)
            except Exception:
                p.pred_details = None
    return render(
        request,
        "api/dashboards/ngo_dashboard.html",
        {"projects": projects, "form": form, "stats": stats, "recent_apps": recent_apps},
    )


@login_required
@user_passes_test(is_ngo)
def upload_project(request):
    if request.method == "POST":
        form = ProjectForm(request.POST, request.FILES)
        if form.is_valid():
            project = form.save(commit=False)
            project.ngo = request.user
            project.status = "Pending"
            # Do NOT assign final credits at upload time. Keep credits at 0 so
            # the admin review flow issues credits on approval (see `review_project`).
            project.credits = 0
            project.save()
            messages.success(request, "Project submitted successfully!")
            return redirect("ngo_dashboard")
        else:
            projects = Project.objects.filter(ngo=request.user)
            return render(
                request,
                "api/dashboards/ngo_dashboard.html",
                {"projects": projects, "form": form},
            )
    return redirect("ngo_dashboard")


# --------------------
# Admin Views
# --------------------
@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    pending = Project.objects.filter(status="under_review")
    # Attach a preview attribute so admins can see estimated credits before approving
    for pr in pending:
        pr.preview_credits = 0
        if pr.document:
            try:
                pr.preview_credits = predict_credits(pr.area, pr.document.path)
                pr.preview_details = predict_details(pr.area, pr.document.path)
            except Exception:
                pr.preview_credits = 0
                pr.preview_details = None
    total = Project.objects.count()
    verified = Project.objects.filter(status="approved")
    stats = {
        "total": total,
        "pending": pending.count(),
        "approved": verified.count(),
        "credits": sum(p.credits for p in verified),
    }
    return render(
        request,
        "api/dashboards/admin_dashboard.html",
        {"pending": pending, "stats": stats},
    )


@login_required
@user_passes_test(is_admin)
def reports_data(request):
    """Return JSON lists of approved and rejected projects for reports modal.

    Response: { approved: [ {id,name,location,credits}... ], rejected: [ {id,name,location,reason?}... ] }
    """
    from django.http import JsonResponse

    approved_qs = Project.objects.filter(status="approved")
    rejected_qs = Project.objects.filter(status="rejected")

    approved = [
        {
            "id": p.id,
            "name": getattr(p, "title", None) or getattr(p, "name", ""),
            "location": p.location or "",
            "credits": int(p.credits or 0),
        }
        for p in approved_qs
    ]

    # For rejected projects we do not store an explicit rejection reason in the model.
    # Use a placeholder if a reason field doesn't exist; admins can add rejection comments later.
    rejected = [
        {
            "id": p.id,
            "name": getattr(p, "title", None) or getattr(p, "name", ""),
            "location": p.location or "",
            "reason": getattr(p, "rejection_reason", "Administrator rejected the submission"),
        }
        for p in rejected_qs
    ]

    return JsonResponse({"approved": approved, "rejected": rejected})




@login_required
@user_passes_test(is_admin)
def review_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)

    if request.method == "POST":
        action = request.POST.get("action")
        # Enforce that both data sets (field + satellite) must be present before any admin action
        # This matches the UI where buttons are disabled until data is complete.
        if not (project.has_field_data and project.has_satellite_data):
            messages.error(request, "Pending data: Field Officer and ISRO submissions are required before reviewing.")
            return redirect("admin_dashboard")
        if action == "approve":
            project.status = "approved"
            if project.document: 
                project.credits = predict_credits(project.area, project.document.path)
            else:
                project.credits = 0
            project.save()
            # Mint credits on blockchain exactly once
            if hasattr(project, 'chain_issued') and not project.chain_issued:
                # Use BlockchainService to ensure proper transaction recording
                try:
                    from .blockchain_service import BlockchainService
                    tx_hash = BlockchainService.mint_credits_for_project(project)
                    if tx_hash:
                        logger.info(f"Credits minted for project {project.id}: {tx_hash}")
                        messages.success(request, f"Project verified and {project.credits} credits minted on blockchain!")
                    else:
                        logger.error(f"Failed to mint credits for project {project.id}")
                        messages.error(request, "Project approved but blockchain minting failed")
                except Exception as e:
                    logger.error(f"Blockchain error for project {project.id}: {e}")
                    messages.error(request, f"Project approved but blockchain error: {str(e)}")
                    # Don't mark as chain_issued if blockchain failed
                    project.chain_issued = False
                    project.save(update_fields=['chain_issued'])

            messages.success(
                request, f"Project verified and {project.credits} credits issued!"
            )

        elif action == "reject":
            # Keep rejection consistent with normalized statuses
            project.status = "rejected"
            project.save()

            messages.warning(request, "Project rejected.")
        return redirect("admin_dashboard")

    return redirect("admin_dashboard")


@login_required
def project_detail_modal(request, project_id):
    """Return a small HTML fragment with project details for modal display.

    This view is intentionally permission-light: NGOs can view their own projects,
    admins can view any pending project, and corporates can view verified projects
    via marketplace flow. It returns a fragment rendered by
    `api/projects/project_modal.html`.
    """
    project = get_object_or_404(Project, id=project_id)

    # Permission guard: 
    # - Staff/superuser: can view all
    # - NGO (contributor): can view own projects
    # - Field Officer / ISRO Admin: can view all (for verification work)
    # - Corporate: may view only approved projects (marketplace)
    # - Otherwise: forbidden
    user = request.user
    allow = False
    if user.is_staff or user.is_superuser:
        allow = True
    else:
        role = None
        try:
            role = getattr(user, 'profile', None) and user.profile.role
        except Exception:
            role = None
        if role == 'ngo' and project.ngo_id == user.id:
            allow = True
        elif role in ('field_officer', 'isro_admin'):
            allow = True
        elif role == 'corporate' and (project.status in ('approved',)):
            allow = True
    if not allow:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("You don't have permission to view this project.")

    # attach prediction details if available
    project.pred_details = None
    if project.document:
        try:
            project.pred_details = predict_details(project.area, project.document.path)
        except Exception:
            project.pred_details = None

    # Fetch related field and satellite submissions
    from .models import FieldDataSubmission, SatelliteImageSubmission
    field_submissions = FieldDataSubmission.objects.filter(project=project).prefetch_related('images').order_by('-created_at')
    satellite_submissions = SatelliteImageSubmission.objects.filter(project=project).prefetch_related('images').order_by('-created_at')

    # --- Build timeline events for this project ---
    # Events: SUBMITTED, VERIFIED, PURCHASE, SOLD_OUT, CHAIN_<kind>
    events = []
    try:
        from .models import Purchase, ChainTransaction, Wallet
        # Ensure NGO wallet (for display only)
        ngo_wallet_addr = getattr(getattr(project.ngo, 'wallet', None), 'address', None)
        if not ngo_wallet_addr:
            # Wallet.ensure may create if missing; wrap in try to avoid DB errors
            try:
                ngo_wallet_addr = Wallet.ensure(project.ngo).address
            except Exception:
                ngo_wallet_addr = None

        events.append({
            "timestamp": project.submitted_at,
            "kind": "SUBMITTED",
            "label": "Project Submitted",
            "meta": {"ngo_wallet": ngo_wallet_addr}
        })

        if project.status and str(project.status).lower() in ('verified', 'approved'):
            events.append({
                "timestamp": project.updated_at or project.submitted_at,
                "kind": "VERIFIED",
                "label": "Project Verified & Credits Issued",
                "meta": {"credits": project.credits, "ngo_wallet": ngo_wallet_addr}
            })

        # Purchases timeline
        total_sold = 0
        import hashlib
        try:
            project_purchases = Purchase.objects.filter(project=project).select_related("corporate").order_by("timestamp")
        except Exception:
            project_purchases = []
        for pur in project_purchases:
            corp_wallet = getattr(getattr(pur.corporate, 'wallet', None), 'address', None)
            if not corp_wallet:
                try:
                    corp_wallet = Wallet.ensure(pur.corporate).address
                except Exception:
                    corp_wallet = None
            corp_wallet_hash = hashlib.sha256(str(corp_wallet).encode()).hexdigest()[:12] if corp_wallet else None
            total_sold += pur.credits
            corp_email = getattr(pur.corporate, 'email', None) or getattr(pur.corporate, 'username', '')
            corp_display = corp_email.split('@')[0] if corp_email else getattr(pur.corporate, 'username', '')
            events.append({
                "timestamp": pur.timestamp,
                "kind": "PURCHASE",
                "label": f"{corp_display} purchased {pur.credits} credits",
                "meta": {
                    "credits": pur.credits,
                    "cumulative_sold": total_sold,
                    "corporate_wallet_hash": corp_wallet_hash,
                    "corporate_username": corp_display,
                    "ngo_wallet": ngo_wallet_addr,
                }
            })
        if hasattr(project_purchases, 'exists') and project_purchases.exists() and project.credits == 0:
            last_purchase = project_purchases.last()
            if last_purchase:
                events.append({
                    "timestamp": last_purchase.timestamp,
                    "kind": "SOLD_OUT",
                    "label": "Credits Fully Sold Out",
                    "meta": {"total_sold": total_sold, "ngo_wallet": ngo_wallet_addr}
                })

        # Chain transactions
        try:
            chain_txs = ChainTransaction.objects.filter(project_id=project.id).order_by('timestamp')[:50]
        except Exception:
            chain_txs = []
        for tx in chain_txs:
            kind = (tx.kind or '').upper()
            events.append({
                "timestamp": tx.timestamp,
                "kind": f"CHAIN_{kind}",
                "label": f"On-chain {tx.kind} {tx.amount} credits",
                "meta": {
                    "amount": tx.amount,
                    "sender": tx.sender,
                    "recipient": tx.recipient,
                    "block_hash": getattr(tx.block, 'hash', None),
                }
            })

        # Sort chronologically (ignore None values safely)
        try:
            events.sort(key=lambda e: (e["timestamp"] is None, e["timestamp"]))
        except Exception:
            pass

        # Normalize meta dicts for template
        for ev in events:
            meta = ev.get("meta") or {}
            items = []
            for k, v in meta.items():
                lbl = k.replace("_", " ").capitalize()
                items.append((k, lbl, v))
            ev["meta_items"] = items
    except Exception:
        # If anything fails, render without timeline
        events = []

    try:
        return render(request, "api/projects/project_modal.html", {
            "project": project, 
            "timeline_events": events,
            "field_submissions": field_submissions,
            "satellite_submissions": satellite_submissions,
        })
    except Exception as e:
        logger.exception("Failed to render project modal for project_id=%s", project_id)
        from django.http import HttpResponse
        html = f"""
        <div class='bg-white p-8 border border-red-200 shadow-md'>
            <div class='text-red-700 font-semibold mb-2'>Render Error</div>
            <div class='text-sm text-red-600'>An error occurred while rendering the project details. Please try again later.</div>
        </div>
        """
        return HttpResponse(html, status=200)


def _token_from_request(request):
    """Return a User for a valid MobileToken header 'X-API-KEY' or None."""
    key = request.META.get("HTTP_X_API_KEY") or request.POST.get("api_key") or request.GET.get("api_key")
    if not key:
        return None
    from .models import MobileToken

    try:
        mt = MobileToken.objects.select_related("user").get(key=key)
        return mt.user
    except Exception:
        return None


@csrf_exempt
def mobile_login(request):
    """Mobile JSON login that returns/creates a MobileToken.

    Accepts POST with JSON or form fields: email, password.
    If credentials match a Django User they are authenticated.
    If not, the legacy NGO/Corporate/Admin tables are checked and a
    Django user is provisioned for the matching role.
    On success returns JSON: {"token": "<key>", "role": "NGO|Admin|Corporate"}
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    # parse JSON body or form-encoded
    data = {}
    try:
        if request.content_type and "application/json" in request.content_type:
            data = json.loads(request.body.decode() or "{}")
        else:
            data = request.POST
    except Exception:
        data = request.POST

    # Accept both 'email' and legacy 'username' field from mobile client
    email = data.get("email") or data.get("username")
    password = data.get("password")
    if not email or not password:
        return JsonResponse({"error": "Missing email or password"}, status=400)

    user = authenticate(request, username=email, password=password)

    # Provision user from legacy tables if not yet a Django user
    if not user:
        def provision_user(group_name: str):
            group, _ = Group.objects.get_or_create(name=group_name)
            dj_user, created = User.objects.get_or_create(username=email, email=email)
            dj_user.set_password(password)
            if group_name == "Admin":
                dj_user.is_staff = True
            dj_user.save()
            dj_user.groups.add(group)
            return dj_user

        if NGOLogin.objects.filter(email=email, password=password).exists():
            provision_user("NGO")
            user = authenticate(request, username=email, password=password)
        elif CorporateLogin.objects.filter(email=email, password=password).exists():
            provision_user("Corporate")
            user = authenticate(request, username=email, password=password)
        elif AdminLogin.objects.filter(email=email, password=password).exists():
            provision_user("Admin")
            user = authenticate(request, username=email, password=password)

    if not user:
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    # create or return existing mobile token
    from .models import MobileToken

    token_obj, created = MobileToken.objects.get_or_create(
        user=user, defaults={"key": secrets.token_hex(32)}
    )

    role = None
    if user.groups.filter(name="NGO").exists():
        role = "NGO"
    elif user.groups.filter(name="Admin").exists() or user.is_superuser:
        role = "Admin"
    elif user.groups.filter(name="Corporate").exists():
        role = "Corporate"

    return JsonResponse({"token": token_obj.key, "role": role})


@csrf_exempt
def mobile_upload_project(request):
    """Accept multipart/form-data POST from mobile clients to create a Project.

    Expected fields: api_key (header X-API-KEY), name, location, species, area, latitude, longitude, document (file)
    Returns JSON with created project id and status.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    user = _token_from_request(request)
    if not user:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    # Basic validation
    name = request.POST.get("name")
    location = request.POST.get("location", "")
    species = request.POST.get("species", "")
    area = request.POST.get("area")
    latitude = request.POST.get("latitude")
    longitude = request.POST.get("longitude")
    document = request.FILES.get("document")

    if not name or not area:
        return JsonResponse({"error": "Missing required fields: name and area"}, status=400)

    try:
        area_val = float(area)
    except Exception:
        return JsonResponse({"error": "Invalid area value"}, status=400)

    proj = Project(
        ngo=user,
        name=name,
        location=location,
        species=species,
        area=area_val,
        status="Pending",
        credits=0,
    )
    if latitude:
        try:
            proj.latitude = float(latitude)
        except Exception:
            pass
    if longitude:
        try:
            proj.longitude = float(longitude)
        except Exception:
            pass

    if document:
        proj.document = document

    proj.save()

    return JsonResponse({"id": proj.id, "status": proj.status})


@csrf_exempt
def mobile_ngo_projects(request):
    """Return JSON list of the authenticated NGO's projects (dashboard data)."""
    if request.method != "GET":
        return JsonResponse({"error": "GET required"}, status=405)

    user = _token_from_request(request)
    if not user:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    qs = Project.objects.filter(ngo=user).order_by("-submitted_at")
    projects = []
    for p in qs:
        pred = None
        if p.document:
            try:
                pred = predict_details(p.area, p.document.path)
            except Exception:
                pred = None
        projects.append({
            "id": p.id,
            "name": getattr(p, "title", None) or getattr(p, "name", ""),
            "status": p.status,
            "credits": int(p.credits),
            "area": float(p.area),
            "location": p.location,
            "species": p.species,
            "latitude": float(p.latitude) if p.latitude is not None else None,
            "longitude": float(p.longitude) if p.longitude is not None else None,
            "submitted_at": p.submitted_at.isoformat(),
            "prediction": pred,
        })
    # Compute stats mirroring the web dashboard
    stats = {
        "total": len(projects),
        "pending": sum(1 for p in projects if p["status"] == "Pending"),
        "verified": sum(1 for p in projects if p["status"] == "Verified"),
        "credits": sum(p["credits"] for p in projects),
    }
    return JsonResponse({"projects": projects, "stats": stats})


@csrf_exempt
def mobile_project_detail(request, project_id):
    """Return JSON detail for a single project owned by the NGO user."""
    if request.method != "GET":
        return JsonResponse({"error": "GET required"}, status=405)

    user = _token_from_request(request)
    if not user:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    project = get_object_or_404(Project, id=project_id, ngo=user)
    pred = None
    if project.document:
        try:
            pred = predict_details(project.area, project.document.path)
        except Exception:
            pred = None

    # Build absolute document URL if available
    doc_url = None
    try:
        if project.document and hasattr(project.document, 'url'):
            from django.http import HttpRequest
            # Build absolute URI using request if possible
            doc_url = request.build_absolute_uri(project.document.url)
    except Exception:
        doc_url = None

    data = {
        "id": project.id,
    "name": project.title,
        "status": project.status,
        "credits": int(project.credits),
        "area": float(project.area),
        "location": project.location,
        "species": project.species,
        "latitude": float(project.latitude) if project.latitude is not None else None,
        "longitude": float(project.longitude) if project.longitude is not None else None,
        "submitted_at": project.submitted_at.isoformat(),
        "created": project.submitted_at.isoformat(),
        "updated": project.updated_at.isoformat() if project.updated_at else None,
        "prediction": pred,
        "document": doc_url,
        "chain_issued": bool(getattr(project, 'chain_issued', False)),
    }
    return JsonResponse(data)


@csrf_exempt
def mobile_profile(request):
    """Return minimal profile info for the authenticated mobile user.

    Response example: {"email": ..., "username": ..., "role": "NGO|Corporate|Admin"}
    """
    if request.method != "GET":
        return JsonResponse({"error": "GET required"}, status=405)

    user = _token_from_request(request)
    if not user:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    role = None
    if user.groups.filter(name="NGO").exists():
        role = "NGO"
    elif user.groups.filter(name="Corporate").exists():
        role = "Corporate"
    elif user.groups.filter(name="Admin").exists() or user.is_superuser:
        role = "Admin"

    data = {
        "email": user.email or user.username,
        "username": user.username,
        "first_name": getattr(user, 'first_name', '') or '',
        "last_name": getattr(user, 'last_name', '') or '',
        "role": role,
    }
    return JsonResponse(data)


# --------------------
# Corporate Views
# --------------------
@login_required
@user_passes_test(is_corporate)
def corporate_dashboard(request):
    # Use case-insensitive match for the canonical status value 'approved'
    verified = Project.objects.filter(status__iexact="approved")
    purchases = Purchase.objects.filter(corporate=request.user).select_related("project")
    # Metrics for corporate dashboard
    from django.db.models import Sum
    # Count projects that are verified and have credits available
    total_projects_available = Project.objects.filter(status__iexact="approved", credits__gt=0).count()
    # Sum of credits purchased by this corporate
    total_credits_agg = purchases.aggregate(total=Sum('credits'))
    total_credits_purchased = int(total_credits_agg.get('total') or 0)
    # Build timeline events combining project lifecycle + purchases
    # Each event: {timestamp, label, project_id, project_name, kind, meta}
    events = []
    from .models import Wallet, ChainTransaction
    # Project submission & verification
    for proj in verified:
        events.append({
            "timestamp": proj.submitted_at,
            "kind": "SUBMITTED",
            "project_id": proj.id,
            "project_name": proj.title,
            "meta": {
                "status": proj.status,
                "ngo_wallet": getattr(getattr(proj.ngo, 'wallet', None), 'address', None)
            }
        })
        # Verification time approximated by updated_at if different
        if proj.updated_at and proj.updated_at != proj.submitted_at:
            events.append({
                "timestamp": proj.updated_at,
                "kind": "VERIFIED",
                "project_id": proj.id,
                "project_name": proj.title,
                "meta": {
                    "credits_available": proj.credits,
                    "ngo_wallet": getattr(getattr(proj.ngo, 'wallet', None), 'address', None)
                }
            })
    # Purchases by this corporate
    for pur in purchases:
        events.append({
            "timestamp": pur.timestamp,
            "kind": "PURCHASE",
            "project_id": pur.project_id,
            "project_name": pur.project.title,
            "meta": {
                "credits": pur.credits,
                "corporate_wallet": getattr(getattr(pur.corporate, 'wallet', None), 'address', None),
                "ngo_wallet": getattr(getattr(pur.project.ngo, 'wallet', None), 'address', None)
            }
        })
    # Sold out events (project credits now zero)
    for proj in verified:
        if proj.credits == 0:
            # Find last purchase time for that project by querying purchases across all corporates
            last_pur = Purchase.objects.filter(project=proj).order_by('-timestamp').first()
            if last_pur:
                events.append({
                    "timestamp": last_pur.timestamp,
                    "kind": "SOLD_OUT",
                    "project_id": proj.id,
                    "project_name": proj.title,
                    "meta": {
                        "total_credits_sold": sum(Purchase.objects.filter(project=proj).values_list('credits', flat=True)),
                        "ngo_wallet": getattr(getattr(proj.ngo, 'wallet', None), 'address', None)
                    }
                })
    # Blockchain transactions for these projects (issue + transfer) limited for performance
    chain_txs = ChainTransaction.objects.filter(project_id__in=[p.id for p in verified]).order_by('timestamp')[:200]
    for tx in chain_txs:
        events.append({
            "timestamp": tx.timestamp,
            "kind": f"CHAIN_{tx.kind}",
            "project_id": tx.project_id,
            "project_name": next((p.title for p in verified if p.id == tx.project_id), None),
            "meta": {
                "amount": tx.amount,
                "sender": tx.sender,
                "recipient": tx.recipient,
            }
        })
    # Sort events chronologically
    events.sort(key=lambda e: e['timestamp'])
    return render(
        request,
        "api/dashboards/corporate_dashboards.html",
        {
            "verified": verified,
            "purchases": purchases,
            "timeline_events": events,
            "total_projects_available": total_projects_available,
            "total_credits_purchased": total_credits_purchased,
            "tenders_open": Tender.objects.filter(corporate=request.user).order_by('-created_at')[:5],
        },
    )


@login_required
@user_passes_test(is_corporate)
def purchase_credits(request, project_id):
    project = get_object_or_404(Project, id=project_id)

    # attach prediction breakdown for corporate view
    project.pred_details = None
    if project.document:
        try:
            project.pred_details = predict_details(project.area, project.document.path)
        except Exception:
            project.pred_details = None

    if request.method == "POST":
        credits = int(request.POST.get("credits", 0))

        if credits <= 0:
            messages.error(request, "Please enter a valid credit amount.")
        elif credits > project.credits:
            messages.error(request, "Not enough credits available.")
        else:
            Purchase.objects.create(corporate=request.user, project=project, credits=credits)
            project.credits -= credits
            project.save(update_fields=["credits"])
            # Chain transfer (buyer -> seller)
            # Use BlockchainService to ensure proper transaction recording
            from .blockchain_service import BlockchainService
            tx_hash = BlockchainService.transfer_credits(project.ngo, request.user, credits, project.id)
            if tx_hash:
                logger.info(f"Credits purchased: {tx_hash}")
            else:
                logger.error("Failed to transfer credits on blockchain")
            messages.success(
                request,
                f"Purchased {credits} credits from project '{project.title}'."
            )
            return redirect("corporate_dashboard")

    return render(request, "api/marketplace/purchase_modal.html", {"project": project})


# --------------------
# Corporate Tenders
# --------------------
@login_required
@user_passes_test(is_corporate)
def tenders_list(request):
    tenders = Tender.objects.filter(corporate=request.user).order_by('-created_at')
    return render(request, "api/tenders/corporate_list.html", {"tenders": tenders})


@login_required
@user_passes_test(is_corporate)
def tender_create(request):
    if request.method == "POST":
        form = TenderForm(request.POST)
        if form.is_valid():
            t = form.save(commit=False)
            t.corporate = request.user
            t.save()
            messages.success(request, "Tender posted successfully")
            return redirect('tenders_list')
    else:
        form = TenderForm()
    return render(request, "api/tenders/corporate_create.html", {"form": form})


@login_required
@user_passes_test(is_corporate)
def tender_review(request, tender_id):
    tender = get_object_or_404(Tender, id=tender_id, corporate=request.user)
    applications = tender.applications.select_related('ngo', 'project').all()
    return render(request, "api/tenders/corporate_review.html", {"tender": tender, "applications": applications})


@login_required
@user_passes_test(is_corporate)
def tender_allot(request, tender_id, application_id):
    # Backward-compatible: redirect to accept flow for consistency
    return redirect('tender_accept', tender_id=tender_id, application_id=application_id)


@login_required
@user_passes_test(is_corporate)
def tender_accept(request, tender_id, application_id):
    tender = get_object_or_404(Tender, id=tender_id, corporate=request.user)
    app = get_object_or_404(TenderApplication, id=application_id, tender=tender)
    if request.method != "POST":
        return HttpResponseForbidden("POST required")
    if tender.status != "Open":
        messages.error(request, "Tender is not open for acceptance.")
        return redirect('tender_review', tender_id=tender.id)
    # Close tender and update proposal statuses
    tender.status = "Allotted"
    tender.allotted_to = app.ngo
    tender.allotted_project = app.project
    tender.save(update_fields=["status", "allotted_to", "allotted_project"])

    TenderApplication.objects.filter(tender=tender).exclude(id=app.id).update(status="Rejected")
    app.status = "Accepted"
    # Optional blockchain transaction (demo): corporate -> ngo for offered_credits
    try:
        from .models import Wallet
        corp_wallet = Wallet.ensure(request.user)
        ngo_wallet = Wallet.ensure(app.ngo)
        # Use BlockchainService to ensure proper transaction recording
        from .blockchain_service import BlockchainService
        amount = float(app.offered_credits or 0)
        if amount > 0:
            tx_hash = BlockchainService.transfer_credits(request.user, app.ngo, int(amount), project_id=None)
            if tx_hash:
                logger.info(f"Tender credits transferred: {tx_hash}")
            else:
                logger.error("Failed to transfer tender credits on blockchain")
            chain = get_chain()
            # store surrogate hash only if ChainTransaction exists for v1? We skip storing on app to keep schema clean
    except Exception:
        pass
    app.save(update_fields=["status"]) 
    # Notify NGO (email)
    try:
        from .emails import send_templated_email, ORG_NAME
        send_templated_email(
            subject=f"Your proposal for '{tender.title}' was accepted",
            template_name='api/emails/proposal_accepted.html',
            context={"tender": type('obj', (), {"tender_title": tender.title, "status": tender.status})(), "proposal": app, "org": ORG_NAME},
            to=[app.ngo.email or app.ngo.username],
        )
    except Exception:
        pass
    messages.success(request, "Proposal accepted and tender closed.")
    return redirect('tender_review', tender_id=tender.id)


@login_required
@user_passes_test(is_corporate)
def tender_reject(request, tender_id, application_id):
    tender = get_object_or_404(Tender, id=tender_id, corporate=request.user)
    app = get_object_or_404(TenderApplication, id=application_id, tender=tender)
    if request.method != "POST":
        return HttpResponseForbidden("POST required")
    if app.status == "Accepted":
        messages.error(request, "Cannot reject an already accepted proposal.")
        return redirect('tender_review', tender_id=tender.id)
    app.status = "Rejected"
    app.save(update_fields=["status"]) 
    try:
        from .emails import send_templated_email, ORG_NAME
        send_templated_email(
            subject=f"Your proposal for '{tender.title}' was not selected",
            template_name='api/emails/proposal_rejected.html',
            context={"tender": type('obj', (), {"tender_title": tender.title, "status": tender.status})(), "proposal": app, "org": ORG_NAME},
            to=[app.ngo.email or app.ngo.username],
        )
    except Exception:
        pass
    messages.info(request, "Proposal rejected.")
    return redirect('tender_review', tender_id=tender.id)


# --------------------
# NGO Tender Views
# --------------------
@login_required
@user_passes_test(is_ngo)
def tenders_browse(request):
    open_tenders = Tender.objects.filter(status__in=["Open", "Under Review"]).order_by('-created_at')
    my_applied_ids = set(TenderApplication.objects.filter(ngo=request.user).values_list('tender_id', flat=True))
    return render(request, "api/tenders/ngo_browse.html", {"tenders": open_tenders, "my_applied_ids": my_applied_ids})


@login_required
@user_passes_test(is_ngo)
def tender_apply(request, tender_id):
    tender = get_object_or_404(Tender, id=tender_id, status__in=["Open", "Under Review"])
    if request.method == "POST":
        form = TenderApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            app = form.save(commit=False)
            app.ngo = request.user
            app.tender = tender
            # Ensure default status Pending for new proposals
            if not app.status:
                app.status = "Pending"
            try:
                app.save()
                # Move tender to Under Review when first proposal arrives
                if tender.status == "Open":
                    tender.status = "Under Review"
                    tender.save(update_fields=["status"])            
                messages.success(request, "Applied successfully")
            except Exception:
                messages.error(request, "You have already applied for this tender.")
            return redirect('tenders_browse')
    return redirect('tenders_browse')


# --------------------
# Collaboration Hub
# --------------------
@login_required
def collaboration_hub(request):
    # Show all allotted tenders as collaborations
    collaborations = Tender.objects.filter(status="Allotted").select_related('corporate', 'allotted_to', 'allotted_project').order_by('-updated_at')
    return render(request, "api/tenders/collaboration_hub.html", {"collaborations": collaborations})


# --------------------
# Tender System v2 (parallel, non-breaking)
# --------------------
@login_required
@user_passes_test(is_corporate)
def tenders_v2_list(request):
    from .models import TenderV2
    tenders = TenderV2.objects.filter(corporate=request.user).order_by('-created_at')
    return render(request, "api/tenders_v2/corporate_list.html", {"tenders": tenders})


@login_required
@user_passes_test(is_corporate)
def tender_v2_create(request):
    from .models import TenderV2
    if request.method == "POST":
        form = TenderV2Form(request.POST)
        if form.is_valid():
            t = form.save(commit=False)
            t.corporate = request.user
            t.save()
            messages.success(request, "Tender created")
            return redirect('tenders_v2_list')
    else:
        form = TenderV2Form(initial={
            "tender_title": "Carbon Credit Purchase – Mangrove Restoration",
            "required_credits": 10000,
            "location_preference": "Optional - India (Coastal)",
            "budget_range": "Optional - $8 to $12 per credit",
            "description": "CSR initiative to offset 10,000 tons of CO2 through verified mangrove restoration projects.",
        })
    return render(request, "api/tenders_v2/corporate_create.html", {"form": form})


@login_required
@user_passes_test(is_corporate)
def tender_v2_review(request, tender_id):
    from .models import TenderV2
    tender = get_object_or_404(TenderV2, id=tender_id, corporate=request.user)
    proposals = tender.proposals.select_related('contributor').all()
    return render(request, "api/tenders_v2/corporate_review.html", {"tender": tender, "proposals": proposals})


@login_required
@user_passes_test(is_corporate)
def tender_v2_accept(request, tender_id, proposal_id):
    from .models import TenderV2, ProposalV2, Wallet
    if request.method != "POST":
        return HttpResponseForbidden("POST required")
    tender = get_object_or_404(TenderV2, id=tender_id, corporate=request.user)
    proposal = get_object_or_404(ProposalV2, id=proposal_id, tender=tender)
    if tender.status not in ("Open", "Under Review"):
        messages.error(request, "Tender is not open for acceptance.")
        return redirect('tender_v2_review', tender_id=tender.id)
    # Update statuses
    tender.status = "Closed"
    tender.save(update_fields=["status"])
    tender.proposals.exclude(id=proposal.id).update(status="Rejected")
    proposal.status = "Accepted"
    # Trigger on-chain transfer (demo): corporate -> contributor wallet amount = offered_credits
    try:
        # Use BlockchainService to ensure proper transaction recording
        from .blockchain_service import BlockchainService
        tx_hash = BlockchainService.transfer_credits(request.user, proposal.contributor, int(proposal.offered_credits), project_id=None)
        if tx_hash:
            logger.info(f"Tender v2 credits transferred: {tx_hash}")
        else:
            logger.error("Failed to transfer tender v2 credits on blockchain")
        # attempt to fetch last block hash as tx hash surrogate
        chain = get_chain()
        last_hash = chain[-1].get('hash') if chain else ''
        proposal.chain_tx_hash = last_hash or ''
    except Exception:
        proposal.chain_tx_hash = ''
    proposal.save(update_fields=["status", "chain_tx_hash"])
    # Notifications (optional email placeholders)
    try:
        from .emails import send_templated_email, ORG_NAME
        send_templated_email(
            subject=f"Your proposal for '{tender.tender_title}' was accepted",
            template_name='api/emails/proposal_accepted.html',
            context={"tender": tender, "proposal": proposal, "org": ORG_NAME},
            to=[proposal.contributor.email or proposal.contributor.username],
        )
    except Exception:
        pass
    messages.success(request, "Proposal accepted and tender closed.")
    return redirect('tender_v2_review', tender_id=tender.id)


@login_required
@user_passes_test(is_corporate)
def tender_v2_reject(request, tender_id, proposal_id):
    from .models import TenderV2, ProposalV2
    if request.method != "POST":
        return HttpResponseForbidden("POST required")
    tender = get_object_or_404(TenderV2, id=tender_id, corporate=request.user)
    proposal = get_object_or_404(ProposalV2, id=proposal_id, tender=tender)
    if proposal.status == "Accepted":
        messages.error(request, "Cannot reject an already accepted proposal.")
        return redirect('tender_v2_review', tender_id=tender.id)
    proposal.status = "Rejected"
    proposal.save(update_fields=["status"])
    try:
        from .emails import send_templated_email, ORG_NAME
        send_templated_email(
            subject=f"Your proposal for '{tender.tender_title}' was not selected",
            template_name='api/emails/proposal_rejected.html',
            context={"tender": tender, "proposal": proposal, "org": ORG_NAME},
            to=[proposal.contributor.email or proposal.contributor.username],
        )
    except Exception:
        pass
    messages.info(request, "Proposal rejected.")
    return redirect('tender_v2_review', tender_id=tender.id)


@login_required
@user_passes_test(is_ngo)
def tenders_v2_browse(request):
    from .models import TenderV2
    tenders = TenderV2.objects.filter(status__in=["Open", "Under Review"]).order_by('-created_at')
    my_ids = set(request.user.proposals_v2.values_list('tender_id', flat=True))
    return render(request, "api/tenders_v2/ngo_browse.html", {"tenders": tenders, "my_ids": my_ids})


@login_required
@user_passes_test(is_ngo)
def tender_v2_apply(request, tender_id):
    from .models import TenderV2, ProposalV2
    tender = get_object_or_404(TenderV2, id=tender_id, status__in=["Open", "Under Review"]) 
    if request.method == "POST":
        form = ProposalV2Form(request.POST, request.FILES)
        if form.is_valid():
            p = form.save(commit=False)
            p.tender = tender
            p.contributor = request.user
            # Avoid duplicate applications
            if ProposalV2.objects.filter(tender=tender, contributor=request.user).exists():
                messages.error(request, "You have already applied to this tender.")
                return redirect('tenders_v2_browse')
            p.save()
            messages.success(request, "Proposal submitted")
            return redirect('tenders_v2_browse')
    return redirect('tenders_v2_browse')


# --------------------
# Blockchain Explorer
# --------------------
@login_required
@login_required
@user_passes_test(is_admin)
def blockchain_explorer(request):
    """Blockchain explorer showing real blockchain transactions only"""
    
    # Import blockchain service for status
    from .blockchain_service import BlockchainService
    
    # Get blockchain status
    blockchain_status = BlockchainService.get_blockchain_status()
    
    enriched_chain = []
    
    try:
        # Import models lazily to avoid app registry issues
        from .models import ChainTransaction, Wallet, Project, Purchase
        
        # Get only real blockchain transactions (those with tx_hash)
        real_blockchain_txs = ChainTransaction.objects.filter(
            tx_hash__isnull=False, 
            tx_hash__gt=''
        ).order_by('-timestamp')
        
        # Create "blocks" from real blockchain transactions
        for i, tx in enumerate(real_blockchain_txs):
            real_block = {
                "index": f"TX-{i+1}",
                "timestamp": tx.timestamp.timestamp() if tx.timestamp else 0,
                "previous_hash": "Real Blockchain Network",
                "nonce": 0,
                "hash": tx.tx_hash or "N/A",
                "transactions": [_enrich_transaction(tx)],
                "total_credits": float(tx.amount or 0),
                "block_type": "real_blockchain",
                "block_number": tx.block_number,
                "gas_used": tx.gas_used
            }
            enriched_chain.append(real_block)
        
        # Get comprehensive statistics for real blockchain only
        total_credits_issued = sum(tx.amount for tx in real_blockchain_txs.filter(kind__in=['MINT']))
        total_credits_transferred = sum(tx.amount for tx in real_blockchain_txs.filter(kind='TRANSFER'))
        unique_wallets = Wallet.objects.count()
        total_projects = Project.objects.count()
        
        data = {
            "length": len(enriched_chain),
            "pending_transactions": [],
            "chain": enriched_chain,
            "blockchain_status": blockchain_status,
            "statistics": {
                "total_credits_issued": float(total_credits_issued or 0),
                "total_credits_transferred": float(total_credits_transferred or 0),
                "total_transactions": real_blockchain_txs.count(),
                "real_blockchain_transactions": real_blockchain_txs.count(),
                "simple_blockchain_transactions": 0,  # No simple blockchain transactions shown
                "unique_wallets": unique_wallets,
                "total_projects": total_projects
            }
        }

    except Exception as e:
        # Error fallback
        import logging
        logging.error(f"Error in blockchain explorer: {e}")
        
        data = {
            "length": 0,
            "pending_transactions": [],
            "chain": [],
            "blockchain_status": blockchain_status,
            "statistics": {
                "total_credits_issued": 0,
                "total_credits_transferred": 0,
                "total_transactions": 0,
                "real_blockchain_transactions": 0,
                "simple_blockchain_transactions": 0,
                "unique_wallets": 0,
                "total_projects": 0
            },
            "error": str(e)
        }

    # If user requested HTML view, render admin explorer page
    if request.headers.get("accept", "").find("text/html") != -1 or request.GET.get("format") == "html":
        return render(request, "api/blockchain/explorer.html", {"data": data})

    return JsonResponse(data, safe=False)


def _enrich_transaction(tx):
    """Enrich a ChainTransaction object with user and project information"""
    from .models import Wallet, Project, Purchase
    from django.contrib.auth.models import User
    from django.db.models import Sum
    
    # Resolve sender/recipient users via Wallet table
    sender_user = None
    recipient_user = None
    sender_location = None
    recipient_location = None
    
    try:
        sw = Wallet.objects.select_related("user").filter(address=tx.sender).first()
        if sw:
            sender_user = {
                "username": sw.user.username, 
                "email": sw.user.email, 
                "id": sw.user.id,
                "role": getattr(sw.user.profile, 'role', 'unknown') if hasattr(sw.user, 'profile') else 'unknown'
            }
            # Try to get location from user profile
            if hasattr(sw.user, 'profile'):
                sender_location = getattr(sw.user.profile, 'organization', None)
    except Exception:
        pass

    try:
        rw = Wallet.objects.select_related("user").filter(address=tx.recipient).first()
        if rw:
            recipient_user = {
                "username": rw.user.username, 
                "email": rw.user.email, 
                "id": rw.user.id,
                "role": getattr(rw.user.profile, 'role', 'unknown') if hasattr(rw.user, 'profile') else 'unknown'
            }
            # Try to get location from user profile
            if hasattr(rw.user, 'profile'):
                recipient_location = getattr(rw.user.profile, 'organization', None)
    except Exception:
        pass

    # Resolve project information
    project = None
    if tx.project_id:
        try:
            p = Project.objects.filter(id=tx.project_id).first()
            if p:
                project = {
                    "id": p.id, 
                    "title": getattr(p, "title", None) or getattr(p, "name", ""),
                    "location": p.location,
                    "status": p.status,
                    "ngo": p.ngo.username if p.ngo else None
                }
        except Exception:
            pass

    # Calculate corporate total purchased (if applicable)
    corporate_total = None
    try:
        if sender_user and tx.project_id:
            cu = User.objects.filter(id=sender_user.get("id")).first()
            if cu:
                total = Purchase.objects.filter(corporate=cu, project__id=tx.project_id).aggregate(total=Sum('credits'))
                corporate_total = float(total.get('total') or 0)
    except Exception:
        pass

    return {
        "id": getattr(tx, 'id', None),
        "kind": tx.kind,
        "amount": float(tx.amount),
        "project_id": tx.project_id,
        "project": project,
        "sender": tx.sender,
        "recipient": tx.recipient,
        "sender_user": sender_user,
        "recipient_user": recipient_user,
        "sender_location": sender_location,
        "recipient_location": recipient_location,
        "corporate_total_purchased": corporate_total,
        "meta": tx.meta,
        "timestamp": tx.timestamp.isoformat() if getattr(tx, "timestamp", None) else None,
        "tx_hash": getattr(tx, 'tx_hash', None),
        "block_number": getattr(tx, 'block_number', None),
        "gas_used": getattr(tx, 'gas_used', None),
        "transaction_type": "real_blockchain" if getattr(tx, 'tx_hash', None) else "simple_blockchain"
    }


def _enrich_simple_transaction(tx_dict):
    """Enrich a simple blockchain transaction dictionary"""
    from .models import Wallet, Project, Purchase
    from django.contrib.auth.models import User
    from django.db.models import Sum
    
    sender_user = None
    recipient_user = None
    sender_location = None
    recipient_location = None
    
    try:
        sw = Wallet.objects.select_related("user").filter(address=tx_dict.get("sender")).first()
        if sw:
            sender_user = {
                "username": sw.user.username, 
                "email": sw.user.email, 
                "id": sw.user.id,
                "role": getattr(sw.user.profile, 'role', 'unknown') if hasattr(sw.user, 'profile') else 'unknown'
            }
            if hasattr(sw.user, 'profile'):
                sender_location = getattr(sw.user.profile, 'organization', None)
    except Exception:
        pass

    try:
        rw = Wallet.objects.select_related("user").filter(address=tx_dict.get("recipient")).first()
        if rw:
            recipient_user = {
                "username": rw.user.username, 
                "email": rw.user.email, 
                "id": rw.user.id,
                "role": getattr(rw.user.profile, 'role', 'unknown') if hasattr(rw.user, 'profile') else 'unknown'
            }
            if hasattr(rw.user, 'profile'):
                recipient_location = getattr(rw.user.profile, 'organization', None)
    except Exception:
        pass

    project = None
    if tx_dict.get("project_id"):
        try:
            p = Project.objects.filter(id=tx_dict.get("project_id")).first()
            if p:
                project = {
                    "id": p.id, 
                    "title": getattr(p, "title", None) or getattr(p, "name", ""),
                    "location": p.location,
                    "status": p.status,
                    "ngo": p.ngo.username if p.ngo else None
                }
        except Exception:
            pass

    corporate_total = None
    try:
        if sender_user and tx_dict.get("project_id"):
            cu = User.objects.filter(id=sender_user.get('id')).first()
            if cu:
                total = Purchase.objects.filter(corporate=cu, project__id=tx_dict.get('project_id')).aggregate(total=Sum('credits'))
                corporate_total = float(total.get('total') or 0)
    except Exception:
        pass

    return {
        "kind": tx_dict.get("kind"),
        "amount": float(tx_dict.get("amount") or 0),
        "project": project,
        "sender": tx_dict.get("sender"),
        "recipient": tx_dict.get("recipient"),
        "sender_user": sender_user,
        "recipient_user": recipient_user,
        "sender_location": sender_location,
        "recipient_location": recipient_location,
        "corporate_total_purchased": corporate_total,
        "meta": tx_dict.get("meta"),
        "transaction_type": "simple_blockchain"
    }


# --------------------
# Certificate Download
# --------------------
@login_required
@user_passes_test(is_corporate)
def download_certificate(request, purchase_id: int):
    """Allow a corporate to download their own purchase certificate."""
    purchase = get_object_or_404(Purchase, id=purchase_id)
    if purchase.corporate_id != request.user.id:
        return HttpResponseForbidden("Not allowed")
    if not purchase.certificate:
        messages.error(request, "Certificate not available yet. Please check again shortly.")
        return redirect("corporate_dashboard")

    from django.core.files.storage import default_storage
    path = purchase.certificate.name if hasattr(purchase.certificate, 'name') else purchase.certificate
    f = default_storage.open(path, 'rb')
    return FileResponse(f, as_attachment=True, filename=f"certificate_{purchase.id}.pdf")


# --------------------
# Field Officer Dashboard
# --------------------
def is_field_officer(user):
    """Check if user is a field officer"""
    return hasattr(user, 'profile') and user.profile.role == 'field_officer'

@login_required
@user_passes_test(is_field_officer)
def field_officer_dashboard(request):
    """Field officer dashboard view"""
    # Optional deep-link to open modal for a specific project
    deep_link_project_id = request.GET.get('project_id')

    # Get field officer's statistics
    total_submissions = FieldDataSubmission.objects.filter(field_officer=request.user).count()
    total_hectares = FieldDataSubmission.objects.filter(field_officer=request.user).aggregate(
        total=models.Sum('hectare_area'))['total'] or 0
    total_images = sum([submission.images.count() for submission in 
                       FieldDataSubmission.objects.filter(field_officer=request.user)])
    species_count = len(set([species['name'] for submission in 
                           FieldDataSubmission.objects.filter(field_officer=request.user)
                           for species in submission.species_data]))
    
    field_stats = {
        'total_submissions': total_submissions,
        'total_hectares': total_hectares,
        'total_images': total_images,
        'species_count': species_count,
    }
    
    # Show projects uploaded by NGOs that still need field data
    # Criteria: NOT approved/rejected AND no field data submitted yet
    # Projects needing field data: no field verification yet and not finalized
    # Use case-insensitive checks to handle any inconsistent historical values.
    assigned_projects = (
        Project.objects
        .filter(field_verified_at__isnull=True)
        .filter(~Q(status__iexact='approved') & ~Q(status__iexact='rejected'))
        .order_by('-submitted_at')
    )
    
    # Get recent submissions
    recent_submissions = FieldDataSubmission.objects.filter(
        field_officer=request.user
    ).order_by('-created_at')[:10]
    
    context = {
        'field_stats': field_stats,
        'assigned_projects': assigned_projects,
        'recent_submissions': recent_submissions,
        'project_id': deep_link_project_id,
    }
    
    return render(request, 'api/dashboards/field_officer_dashboard.html', context)


@login_required
@user_passes_test(is_field_officer)
def field_officer_projects(request):
    """List view of projects needing field data with deep-link to open the modal."""
    projects = (
        Project.objects
        .filter(field_verified_at__isnull=True)
        .filter(~Q(status__iexact='approved') & ~Q(status__iexact='rejected'))
        .order_by('-submitted_at')
    )
    # Support opening the modal from query param
    project_id = request.GET.get('project_id')
    return render(request, 'api/field_officer/projects_list.html', {
        'projects': projects,
        'project_id': project_id,
    })


@login_required
@user_passes_test(is_field_officer)
def field_officer_submissions(request):
    """History view of submissions by this field officer."""
    submissions = FieldDataSubmission.objects.filter(field_officer=request.user).order_by('-created_at')
    return render(request, 'api/field_officer/submissions_list.html', {'submissions': submissions})


@login_required
@user_passes_test(is_field_officer)
def field_officer_submission_detail(request, submission_id: int):
    submission = get_object_or_404(FieldDataSubmission, pk=submission_id, field_officer=request.user)
    images = list(submission.images.all())
    return render(request, 'api/field_officer/submission_detail.html', {
        'submission': submission,
        'images': images,
    })


# --------------------
# ISRO Admin Dashboard
# --------------------
def is_isro_admin(user):
    """Check if user is an ISRO admin"""
    return hasattr(user, 'profile') and user.profile.role == 'isro_admin'

@login_required
@user_passes_test(is_isro_admin)
def isro_admin_dashboard(request):
    """ISRO admin dashboard view"""
    
    # Get ISRO admin statistics
    # Count projects that still need satellite data (not finalized)
    pending_projects = (
        Project.objects
        .filter(isro_verified_at__isnull=True)
        .filter(~Q(status__iexact='approved') & ~Q(status__iexact='rejected'))
        .filter(Q(isro_admin__isnull=True) | Q(isro_admin=request.user))
        .count()
    )
    approved_projects = Project.objects.filter(status__iexact='approved').count()
    satellite_images = SatelliteImageSubmission.objects.filter(isro_admin=request.user).count()
    rejected_projects = Project.objects.filter(status__iexact='rejected').count()
    
    isro_stats = {
        'pending_projects': pending_projects,
        'approved_projects': approved_projects,
        'satellite_images': satellite_images,
        'rejected_projects': rejected_projects,
    }
    
    # Get projects pending review
    # Show NGO-uploaded projects that still need satellite data
    # Criteria: either fully pending (no data) or field data already submitted but satellite data missing
    pending_projects_list = (
        Project.objects
        .filter(isro_verified_at__isnull=True)
        .filter(~Q(status__iexact='approved') & ~Q(status__iexact='rejected'))
        .filter(Q(isro_admin__isnull=True) | Q(isro_admin=request.user))
        .order_by('-updated_at')[:10]
    )
    
    # Get recent activities (simplified)
    recent_activities = []
    for project in Project.objects.filter(
        isro_admin=request.user
    ).order_by('-isro_verified_at')[:5]:
        recent_activities.append({
            'type': 'approval' if project.status == 'approved' else 'upload',
            'description': f"{'Approved' if project.status == 'approved' else 'Uploaded satellite data for'} project: {project.title}",
            'timestamp': project.isro_verified_at or project.updated_at,
        })
    
    context = {
        'isro_stats': isro_stats,
        'pending_projects': pending_projects_list,
        'recent_activities': recent_activities,
    }
    
    return render(request, 'api/dashboards/isro_admin_dashboard.html', context)


def isro_pending_projects(request):
    """View for listing all pending projects for ISRO admin"""
    
    # Get all projects pending review
    pending_projects_list = (
        Project.objects
        .filter(isro_verified_at__isnull=True)
        .filter(~Q(status__iexact='approved') & ~Q(status__iexact='rejected'))
        .filter(Q(isro_admin__isnull=True) | Q(isro_admin=request.user))
        .order_by('-updated_at')
    )
    
    context = {
        'pending_projects': pending_projects_list,
    }
    
    return render(request, 'api/dashboards/isro_pending_projects.html', context)


@login_required
@user_passes_test(is_isro_admin)
def isro_analytics(request):
    """View for ISRO analytics dashboard"""
    
    # Calculate statistics
    total_projects = Project.objects.count()
    approved_projects = Project.objects.filter(status__iexact='approved').count()
    rejected_projects = Project.objects.filter(status__iexact='rejected').count()
    pending_projects = Project.objects.filter(status__iexact='pending').count()
    
    # Calculate total area covered
    total_area = Project.objects.aggregate(total_area=models.Sum('area'))['total_area'] or 0
    verified_area = Project.objects.filter(status__iexact='approved').aggregate(total_area=models.Sum('area'))['total_area'] or 0
    
    # Get recent satellite submissions
    recent_submissions = SatelliteImageSubmission.objects.filter(isro_admin=request.user).order_by('-created_at')[:10]
    
    context = {
        'stats': {
            'total_projects': total_projects,
            'approved_projects': approved_projects,
            'rejected_projects': rejected_projects,
            'pending_projects': pending_projects,
            'total_area': total_area,
            'verified_area': verified_area,
        },
        'recent_submissions': recent_submissions,
    }
    
    return render(request, 'api/dashboards/isro_analytics.html', context)


# --------------------
# API Endpoints for Field Data Submission
# --------------------
@login_required
@csrf_exempt
def submit_field_data(request):
    """API endpoint for field data submission"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method allowed'})
    
    try:
        # Get project
        project_id = request.POST.get('project_id')
        project = get_object_or_404(Project, id=project_id)

        # Server-side guard: prevent duplicate submissions or submissions to finalized projects
        if project.status in ['approved', 'rejected']:
            return JsonResponse({'success': False, 'message': 'This project is already finalized and cannot accept field data.'})
        if project.field_verified_at is not None:
            return JsonResponse({'success': False, 'message': 'Field data has already been submitted for this project.'})
        from .models import FieldDataSubmission as _FDS
        if _FDS.objects.filter(project=project).exists():
            return JsonResponse({'success': False, 'message': 'Field data has already been submitted for this project.'})
        
        # Create field data submission
        submission = FieldDataSubmission.objects.create(
            project=project,
            field_officer=request.user,
            survey_date=request.POST.get('survey_date'),
            hectare_area=request.POST.get('hectare_area'),
            latitude=request.POST.get('latitude'),
            longitude=request.POST.get('longitude'),
            soil_type=request.POST.get('soil_type'),
            water_salinity=request.POST.get('water_salinity') or None,
            tidal_range=request.POST.get('tidal_range') or None,
            species_data=[
                {
                    'name': name,
                    'count': count,
                    'health': health
                }
                for name, count, health in zip(
                    request.POST.getlist('species_name[]'),
                    request.POST.getlist('species_count[]'),
                    request.POST.getlist('species_health[]')
                )
            ],
            notes=request.POST.get('notes', '')
        )
        
        # Handle uploaded images
        for image_file in request.FILES.getlist('field_images'):
            FieldImage.objects.create(
                field_submission=submission,
                image=image_file
            )
        
        return JsonResponse({'success': True, 'message': 'Field data submitted successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


# --------------------
# API Endpoints for Satellite Image Upload
# --------------------
@login_required
@csrf_exempt
def upload_satellite_images(request):
    """API endpoint for satellite image upload"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method allowed'})
    
    try:
        # Get project
        project_id = request.POST.get('project_id')
        project = get_object_or_404(Project, id=project_id)

        # Server-side guard: prevent duplicate submissions or submissions to finalized projects
        if project.status in ['approved', 'rejected']:
            return JsonResponse({'success': False, 'message': 'This project is already finalized and cannot accept satellite data.'})
        if project.isro_verified_at is not None:
            return JsonResponse({'success': False, 'message': 'Satellite data has already been uploaded for this project.'})
        from .models import SatelliteImageSubmission as _SIS
        if _SIS.objects.filter(project=project).exists():
            return JsonResponse({'success': False, 'message': 'Satellite data has already been uploaded for this project.'})
        
        # Parse capture date (supports formats: YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY, MM/DD/YYYY)
        capture_date_val = request.POST.get('capture_date')
        parsed_capture_date = None
        if capture_date_val:
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
                try:
                    parsed_capture_date = datetime.strptime(capture_date_val, fmt).date()
                    break
                except Exception:
                    continue
        
        # Create satellite image submission
        submission = SatelliteImageSubmission.objects.create(
            project=project,
            isro_admin=request.user,
            image_type=request.POST.get('image_type'),
            capture_date=parsed_capture_date or capture_date_val,
            satellite_name=request.POST.get('satellite_name'),
            resolution=request.POST.get('resolution'),
            north_bound=request.POST.get('north_bound'),
            south_bound=request.POST.get('south_bound'),
            east_bound=request.POST.get('east_bound'),
            west_bound=request.POST.get('west_bound'),
            measured_area=request.POST.get('measured_area') or None,
            analysis_notes=request.POST.get('analysis_notes', '')
        )
        
        # Handle uploaded images
        for image_file in request.FILES.getlist('satellite_images'):
            SatelliteImage.objects.create(
                submission=submission,
                image=image_file,
                filename=image_file.name,
                file_size=image_file.size
            )
        
        return JsonResponse({'success': True, 'message': 'Satellite images uploaded successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


# --------------------
# Project Approval/Rejection API
# --------------------
@login_required
@csrf_exempt
def approve_project(request, project_id):
    """API endpoint for project approval"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method allowed'})
    
    try:
        project = get_object_or_404(Project, id=project_id)
        # Enforce that both datasets exist before approval
        if not (project.has_field_data and project.has_satellite_data):
            return JsonResponse({'success': False, 'message': 'Cannot approve: both field and satellite data are required.'}, status=400)

        # Update project status
        project.status = 'approved'
        project.admin_reviewer = request.user
        project.save()
        
        return JsonResponse({'success': True, 'message': 'Project approved successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@csrf_exempt
def reject_project(request, project_id):
    """API endpoint for project rejection"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method allowed'})
    
    try:
        import json
        
        project = get_object_or_404(Project, id=project_id)
        
        # Get rejection reason from request body
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            reason = data.get('reason', '')
        else:
            reason = request.POST.get('reason', '')
        
        # Update project status
        project.status = 'rejected'
        project.admin_reviewer = request.user
        project.admin_review_notes = reason
        project.save()
        
        return JsonResponse({'success': True, 'message': 'Project rejected successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

def collaboration_hub(request):
    """Public collaboration hub page - no login required"""
    # Get all allotted tenders to show collaborations
    from .models import Tender
    collaborations = Tender.objects.filter(allotted_to__isnull=False).order_by('-updated_at')
    return render(request, "api/tenders/collaboration_hub.html", {"collaborations": collaborations})

@login_required
@user_passes_test(is_admin)
def blockchain_status(request):
    """API endpoint to check blockchain connection status"""
    try:
        status = BlockchainService.get_blockchain_status()
        return JsonResponse(status)
    except Exception as e:
        return JsonResponse({
            'connected': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
def api_blockchain_status(request):
    """Public API endpoint for blockchain status (for mobile/external apps)"""
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=405)
    
    try:
        status = BlockchainService.get_blockchain_status()
        return JsonResponse({
            'success': True,
            'blockchain': status
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def user_wallet_info(request):
    """Get current user's wallet information and balance"""
    try:
        wallet = Wallet.ensure(request.user)
        balance = BlockchainService.get_user_balance(request.user)
        
        return JsonResponse({
            'address': wallet.address,
            'balance': balance,
            'is_external': wallet.is_external
        })
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)