from django import forms
from django.contrib.auth.models import User
from .models import Project, Wallet, NGOLogin, CorporateLogin, Tender, TenderApplication, TenderV2, ProposalV2

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["title", "location", "species", "area", "document", "latitude", "longitude"]

    # Allow manual entry; provide helpful input constraints
    latitude = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            "step": "0.000001",
            "min": "-90",
            "max": "90",
            "placeholder": "e.g., 22.572645",
        }),
    )
    longitude = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            "step": "0.000001",
            "min": "-180",
            "max": "180",
            "placeholder": "e.g., 88.363892",
        }),
    )


class NGORegisterForm(forms.ModelForm):
    """Contributor registration (NGO) with OTP verification.

    Changes:
    - Removed registration_number and password fields (password is auto-generated)
    - Added email/phone OTP flow validation via request.session
    - Made email and contact_number required for OTP
    """

    # Hidden username; we map it from email during clean() so ModelForm validation passes
    username = forms.CharField(required=False, widget=forms.HiddenInput())
    # Basic organization details
    name = forms.CharField(max_length=255, label="Name")
    email = forms.EmailField(label="Email Address")
    # Passwords
    password = forms.CharField(label="Password", widget=forms.PasswordInput, min_length=8)
    confirm_password = forms.CharField(label="Confirm Password", widget=forms.PasswordInput, min_length=8)
    # OTP helper inputs (not stored, just to collect if you want to submit directly)
    email_otp = forms.CharField(max_length=6, required=False, label="Email OTP")
    pincode = forms.CharField(max_length=10, required=False, label="Pincode")
    address = forms.CharField(
        max_length=512,
        required=False,
        label="Address",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Street, village, landmark, etc."}),
    )
    taluka = forms.CharField(max_length=128, required=False, label="Taluka / Block")
    district = forms.CharField(max_length=128, required=False, label="District")
    state = forms.CharField(max_length=128, required=False, label="State")
    contact_person_name = forms.CharField(max_length=255, required=False, label="Contact Person Name")
    contact_number = forms.CharField(max_length=32, required=True, label="Contact Number")
    phone_otp = forms.CharField(max_length=6, required=False, label="Phone OTP")
    wallet_address = forms.CharField(max_length=255, help_text="Public wallet address for credit issuance")
    project_type = forms.ChoiceField(
        choices=[
            ("mangroves", "Mangroves"),
            ("forestry", "Forestry"),
            ("renewable", "Renewable"),
            ("afforestation", "Afforestation / Reforestation"),
            ("soil", "Soil Carbon"),
            ("blue_other", "Blue Carbon (Other)"),
        ],
        label="Type of Carbon Project",
        required=True,
    )
    # Identity verification uploads (all optional; stored to media storage)
    aadhaar_pan_document = forms.FileField(required=False, label="Aadhaar / PAN (Individuals)")
    gst_registration_certificate = forms.FileField(required=False, label="GST / Registration Certificate (NGOs/Organizations)")
    government_id_document = forms.FileField(required=False, label="Government-issued ID")
    # Additional documents
    land_ownership_proof = forms.FileField(required=False, label="Land ownership proof / MoU with govt body")
    environmental_clearance_certificate = forms.FileField(required=False, label="Environmental clearance or Forest Dept certificate")
    # Bank details (stored securely later; for now collected via basic fields)
    bank_account_name = forms.CharField(max_length=255, required=False, label="Bank Account Name")
    bank_account_number = forms.CharField(max_length=64, required=False, label="Bank Account Number")
    bank_ifsc = forms.CharField(max_length=16, required=False, label="IFSC Code")
    agreement = forms.BooleanField(label='I confirm that the information provided is accurate and our NGO is legally registered.', required=True)
    accept_terms = forms.BooleanField(label='I accept the Terms & Conditions and Privacy Policy', required=True)

    class Meta:
        model = User
        fields = ["username", "email"]

    def __init__(self, *args, **kwargs):
        # Accept request to check session for OTP flags
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        # Ensure placeholders/attrs if needed
        self._generated_password = None
        self.generated_password = None

    def save(self, commit=True):
        user = super().save(commit=False)
        # Use email as username so the legacy provisioning/auth code can
        # find users by email (username field is used elsewhere).
        user.username = self.cleaned_data.get("email") or self.cleaned_data.get("username")
        # Set provided password
        pwd = self.cleaned_data.get("password")
        user.set_password(pwd)
        # store organization name in first_name for now
        name = self.cleaned_data.get("name")
        if name:
            user.first_name = name
        if commit:
            user.save()
            # ensure wallet address uniqueness
            from django.core.exceptions import ValidationError
            addr = self.cleaned_data.get("wallet_address")
            if addr and Wallet.objects.filter(address=addr).exists():
                raise ValidationError({"wallet_address": ["This wallet address is already in use."]})
            Wallet.objects.create(user=user, address=addr)
            # Save identity documents if provided (paths not persisted to DB for now)
            try:
                from django.core.files.storage import default_storage
                from django.utils.text import slugify
                import os
                base_dir = f"documents/identity/{slugify(user.email)}/"
                os.makedirs(os.path.join(getattr(__import__('django.conf').conf, 'settings').MEDIA_ROOT, base_dir), exist_ok=True)
                def _save_if_present(field_name):
                    f = self.files.get(field_name) if hasattr(self, 'files') else None
                    if f:
                        filename = f"{field_name}_{f.name}"
                        path = default_storage.save(base_dir + filename, f)
                        return path
                    return None
                _save_if_present("aadhaar_pan_document")
                _save_if_present("gst_registration_certificate")
                _save_if_present("government_id_document")
                _save_if_present("land_ownership_proof")
                _save_if_present("environmental_clearance_certificate")

                # Save bank details as a JSON file under the same folder (lightweight storage)
                bank = {
                    "account_name": self.cleaned_data.get("bank_account_name"),
                    "account_number": self.cleaned_data.get("bank_account_number"),
                    "ifsc": self.cleaned_data.get("bank_ifsc"),
                }
                try:
                    import json
                    from django.core.files.base import ContentFile
                    bank_json = json.dumps(bank or {}, ensure_ascii=False, indent=2)
                    default_storage.save(base_dir + "bank_details.json", ContentFile(bank_json.encode("utf-8")))
                except Exception:
                    pass
            except Exception:
                # Non-fatal; continue without failing registration
                pass
            # Create legacy NGOLogin record to support existing provision/login flows
            # Attempt to persist extended NGO info into legacy NGOLogin if model supports extra fields.
            try:
                ngo_kwargs = {
                    "email": user.email,
                    # store password in legacy table for back-compat
                    "password": pwd,
                }
                # Add optional fields if present
                extra_fields = ["name", "pincode", "address", "taluka", "district", "state", "contact_person_name", "contact_number", "wallet_address"]
                for f in extra_fields:
                    if f in self.cleaned_data:
                        ngo_kwargs[f] = self.cleaned_data.get(f)
                NGOLogin.objects.create(**ngo_kwargs)
            except TypeError:
                # legacy model doesn't accept new kwargs, fall back to minimal record
                try:
                    NGOLogin.objects.create(email=user.email, password=pwd)
                except Exception:
                    pass
            except Exception:
                # ignore other creation errors
                pass
        return user
    def clean_wallet_address(self):
        addr = self.cleaned_data.get("wallet_address")
        if addr and Wallet.objects.filter(address=addr).exists():
            raise forms.ValidationError("This wallet address is already registered.")
        return addr

    def clean(self):
        cleaned = super().clean()
        # Password confirmation
        pwd = cleaned.get("password")
        cpwd = cleaned.get("confirm_password")
        if pwd and cpwd and pwd != cpwd:
            self.add_error("confirm_password", "Passwords do not match.")
        # Optional basic strength rule
        if pwd and len(pwd) < 8:
            self.add_error("password", "Password must be at least 8 characters.")
        # Ensure agreement checkboxes are true
        if not cleaned.get("agreement"):
            self.add_error("agreement", "You must confirm the accuracy and legal registration.")
        if not cleaned.get("accept_terms"):
            self.add_error("accept_terms", "You must accept the Terms & Conditions and Privacy Policy.")
        # Ensure username is set from email for underlying User model validation
        email = cleaned.get("email")
        if email:
            cleaned["username"] = email

        # OTP checks using session flags
        session = getattr(self.request, "session", None) if self.request else None
        if not session:
            self.add_error(None, "Session is required for OTP verification. Enable cookies and try again.")
            return cleaned

        # Email OTP must be verified
        verified_email = session.get("otp_email_verified") and session.get("otp_verified_email_value") == email
        if not verified_email:
            self.add_error("email", "Please verify your email via OTP before submitting.")

        # Phone OTP must be verified
        phone = cleaned.get("contact_number")
        if not phone:
            self.add_error("contact_number", "Contact number is required for OTP verification.")
        else:
            verified_phone = session.get("otp_phone_verified") and session.get("otp_verified_phone_value") == phone
            if not verified_phone:
                self.add_error("contact_number", "Please verify your phone via OTP before submitting.")

        return cleaned


class CorporateRegisterForm(forms.ModelForm):
    # Hidden username; mapped from email in clean()
    username = forms.CharField(required=False, widget=forms.HiddenInput())
    # Basic Details
    company_name = forms.CharField(max_length=255, label="Company Name")
    # Business Verification
    cin = forms.CharField(max_length=30, required=False, label="CIN (Corporate Identification Number)")
    gst_number = forms.CharField(max_length=32, required=False, label="GSTIN")
    company_pan = forms.CharField(max_length=20, required=False, label="Company PAN")
    gst_document = forms.FileField(required=False, label="GST Document (PDF or image)")
    # Document Uploads
    certificate_of_incorporation = forms.FileField(required=False, label="Certificate of Incorporation")
    board_resolution = forms.FileField(required=False, label="Board Resolution / Authorized Signatory Letter")
    csr_mandate = forms.FileField(required=False, label="CSR Mandate (if applicable)")
    # Address
    pincode = forms.CharField(max_length=10, required=False, label="Pincode")
    address = forms.CharField(
        max_length=512,
        required=False,
        label="Registered Address",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Street, building, landmark..."}),
    )
    taluka = forms.CharField(max_length=128, required=False, label="Taluka / Block")
    district = forms.CharField(max_length=128, required=False, label="District")
    state = forms.CharField(max_length=128, required=False, label="State")
    # Contacts
    contact_person_name = forms.CharField(max_length=255, required=False, label="Contact Person Name")
    contact_number = forms.CharField(max_length=32, required=False, label="Phone")
    phone_otp = forms.CharField(max_length=6, required=False, label="Phone OTP")
    # Passwords
    password = forms.CharField(label="Password", widget=forms.PasswordInput, min_length=8)
    confirm_password = forms.CharField(label="Confirm Password", widget=forms.PasswordInput, min_length=8)
    # Wallet and agreements
    wallet_address = forms.CharField(max_length=255, help_text="Corporate wallet for purchasing credits")
    agreement = forms.BooleanField(label='I confirm that the information provided is accurate and our Company is legally registered.', required=True)
    accept_terms = forms.BooleanField(label='I accept the Terms & Conditions and Privacy Policy', required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data.get("email") or self.cleaned_data.get("username")
        user.set_password(self.cleaned_data["password"])
        # store company name in first_name for now
        cname = self.cleaned_data.get("company_name")
        if cname:
            user.first_name = cname
        # store gst number in last_name (lightweight storage)
        gst = self.cleaned_data.get("gst_number")
        if gst:
            user.last_name = gst
        if commit:
            user.save()
            addr = self.cleaned_data.get("wallet_address")
            if addr and Wallet.objects.filter(address=addr).exists():
                raise forms.ValidationError({"wallet_address": ["This wallet address is already in use."]})
            Wallet.objects.create(user=user, address=addr)
            # Attempt to persist extended corporate info into legacy CorporateLogin if supported.
            try:
                corp_kwargs = {"email": user.email, "password": self.cleaned_data["password"]}
                extra_fields = [
                    "company_name",
                    "cin",
                    "gst_number",
                    "company_pan",
                    "pincode",
                    "address",
                    "taluka",
                    "district",
                    "state",
                    "contact_person_name",
                    "contact_number",
                    "wallet_address",
                ]
                for f in extra_fields:
                    if f in self.cleaned_data:
                        corp_kwargs[f] = self.cleaned_data.get(f)

                # Handle gst_document file saving to MEDIA and include path if possible
                from django.core.files.storage import default_storage
                gst_file = self.files.get("gst_document") if hasattr(self, 'files') else None
                if gst_file:
                    save_path = default_storage.save(f"corporate_docs/{user.username}_gst_{gst_file.name}", gst_file)
                    corp_kwargs["gst_document"] = save_path

                # Save additional corporate documents
                coi = self.files.get("certificate_of_incorporation") if hasattr(self, 'files') else None
                if coi:
                    corp_kwargs["certificate_of_incorporation"] = default_storage.save(
                        f"corporate_docs/{user.username}_coi_{coi.name}", coi
                    )
                br = self.files.get("board_resolution") if hasattr(self, 'files') else None
                if br:
                    corp_kwargs["board_resolution"] = default_storage.save(
                        f"corporate_docs/{user.username}_br_{br.name}", br
                    )
                csr = self.files.get("csr_mandate") if hasattr(self, 'files') else None
                if csr:
                    corp_kwargs["csr_mandate"] = default_storage.save(
                        f"corporate_docs/{user.username}_csr_{csr.name}", csr
                    )

                CorporateLogin.objects.create(**corp_kwargs)
            except TypeError:
                try:
                    CorporateLogin.objects.create(email=user.email, password=self.cleaned_data["password"])
                except Exception:
                    pass
            except Exception:
                # ignore other creation errors
                pass
        return user
    def clean_wallet_address(self):
        addr = self.cleaned_data.get("wallet_address")
        if addr and Wallet.objects.filter(address=addr).exists():
            raise forms.ValidationError("This wallet address is already registered.")
        return addr

    def clean_email(self):
        email = self.cleaned_data.get("email", "")
        # Basic domain-based verification: disallow common free email providers
        blocked = {
            "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "live.com", "aol.com",
            "icloud.com", "proton.me", "protonmail.com", "yandex.com", "rediffmail.com", "zoho.com",
        }
        try:
            domain = email.split("@", 1)[1].lower()
        except Exception:
            return email
        if domain in blocked:
            raise forms.ValidationError("Please use your corporate email domain (not a public email provider).")
        return email

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get("email")
        if email:
            cleaned["username"] = email

        # Password confirmation
        pwd = cleaned.get("password")
        cpwd = cleaned.get("confirm_password")
        if pwd and cpwd and pwd != cpwd:
            self.add_error("confirm_password", "Passwords do not match.")
        if pwd and len(pwd) < 8:
            self.add_error("password", "Password must be at least 8 characters.")

        # Enforce phone OTP verification via session (if request is provided)
        session = getattr(self, "request", None) and getattr(self.request, "session", None)
        phone = cleaned.get("contact_number")
        if session and phone:
            verified_phone = session.get("otp_phone_verified") and session.get("otp_verified_phone_value") == phone
            if not verified_phone:
                self.add_error("contact_number", "Please verify your phone via OTP before submitting.")
        return cleaned


class TenderForm(forms.ModelForm):
    class Meta:
        model = Tender
        fields = ["title", "location", "credits_required", "location_preference", "deadline", "budget_range", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Describe your requirements (species preference, timeline, region specifics)..."}),
            "deadline": forms.DateInput(attrs={"type": "date"}),
            "location_preference": forms.TextInput(attrs={"placeholder": "Optional – e.g., Coastal India"}),
            "budget_range": forms.TextInput(attrs={"placeholder": "Optional – e.g., $8 to $12 per credit"}),
        }


class TenderApplicationForm(forms.ModelForm):
    class Meta:
        model = TenderApplication
        fields = [
            "offered_credits",
            "price_per_credit",
            "project_location",
            "supporting_documents",
            "project_description",
        ]
        widgets = {
            "project_description": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Short explanation of your carbon project and its impact (verification status, methods, community benefits).",
                }
            ),
        }
    # No extra validation needed; project selection removed by design.


# --------------------
# Tender v2 Forms
# --------------------
class TenderV2Form(forms.ModelForm):
    class Meta:
        model = TenderV2
        fields = [
            "tender_title",
            "required_credits",
            "location_preference",
            "deadline",
            "budget_range",
            "description",
        ]
        widgets = {
            "deadline": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "Brief description of CSR objective, verification requirements, and timelines."}),
            "location_preference": forms.TextInput(attrs={"placeholder": "Optional (e.g., India - Coastal)"}),
            "budget_range": forms.TextInput(attrs={"placeholder": "Optional (e.g., $8 to $12 per credit)"}),
        }


class ProposalV2Form(forms.ModelForm):
    supporting_documents = forms.FileField(required=False)

    class Meta:
        model = ProposalV2
        fields = [
            "offered_credits",
            "price_per_credit",
            "project_location",
            "supporting_documents",
            "project_description",
        ]
        widgets = {
            "project_description": forms.Textarea(attrs={"rows": 4, "placeholder": "Summarize project scope, verification status, and community impact."}),
        }
