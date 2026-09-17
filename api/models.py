from django.db import models
from django.contrib.auth.models import User
import secrets


# --------------------
# User Management
# --------------------
class UserProfile(models.Model):
    """Extended user profile with role information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    role = models.CharField(max_length=20, choices=[
        ('ngo', 'NGO Representative'),
        ('corporate', 'Corporate User'),
        ('admin', 'System Administrator'),
        ('field_officer', 'Field Officer'),
        ('isro_admin', 'ISRO Administrator'),
    ])
    
    # Contact information
    phone = models.CharField(max_length=20, blank=True)
    organization = models.CharField(max_length=255, blank=True)
    
    # Field officer specific
    certification = models.CharField(max_length=255, blank=True, help_text="Professional certification")
    assigned_regions = models.JSONField(default=list, help_text="List of regions assigned to field officer")
    
    # ISRO admin specific
    clearance_level = models.CharField(max_length=50, blank=True, help_text="Security clearance level")
    specialization = models.CharField(max_length=255, blank=True, help_text="Technical specialization")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"


class Wallet(models.Model):
    """Blockchain wallet storing an on-chain address for a user."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    address = models.CharField(max_length=42, unique=True)  # Ethereum address format
    private_key = models.CharField(max_length=66, blank=True, help_text="Encrypted private key (optional)")
    is_external = models.BooleanField(default=False, help_text="True if user provided their own wallet")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.address}"[:64]

    @staticmethod
    def ensure(user: User):
        """Ensure user has a wallet, create one if needed"""
        wallet, created = Wallet.objects.get_or_create(
            user=user,
            defaults={"address": Wallet._generate_address()},
        )
        return wallet
    
    @staticmethod
    def _generate_address():
        """Generate a new Ethereum address"""
        try:
            from eth_account import Account
            account = Account.create()
            return account.address
        except ImportError:
            # Fallback to mock address if eth_account not available
            import secrets
            return f"0x{secrets.token_hex(20)}"
    
    def get_balance(self):
        """Get the current token balance for this wallet"""
        from .blockchain import get_blockchain_manager
        manager = get_blockchain_manager()
        if hasattr(manager, 'get_balance'):
            return manager.get_balance(self.address)
        return 0


# --------------------
# Core Project Model
# --------------------
class Project(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('field_data_submitted', 'Field Data Submitted'),
        ('satellite_data_submitted', 'Satellite Data Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    # Basic project information (submitted by NGO)
    ngo = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ngo_projects')
    title = models.CharField(max_length=255, default='')  # Changed from 'name' to 'title'
    location = models.CharField(max_length=255)
    species = models.CharField(max_length=255)
    area = models.DecimalField(max_digits=10, decimal_places=2, help_text="Planned area in hectares")
    document = models.FileField(upload_to="documents/")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Project status and workflow
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    credits = models.IntegerField(default=0)
    chain_issued = models.BooleanField(default=False)
    
    # Field officer data (when available)
    field_officer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='field_verified_projects')
    field_verified_at = models.DateTimeField(null=True, blank=True)
    field_area_measured = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Field measured area in hectares")
    field_species_data = models.JSONField(null=True, blank=True, help_text="Field officer species data")
    field_notes = models.TextField(blank=True)
    field_images_count = models.IntegerField(default=0)
    
    # ISRO admin data (when available)
    isro_admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='isro_verified_projects')
    isro_verified_at = models.DateTimeField(null=True, blank=True)
    satellite_area_measured = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Satellite measured area in hectares")
    satellite_analysis_data = models.JSONField(null=True, blank=True, help_text="Satellite analysis results")
    isro_notes = models.TextField(blank=True)
    satellite_images_count = models.IntegerField(default=0)
    
    # Admin review
    admin_reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='admin_reviewed_projects')
    admin_review_notes = models.TextField(blank=True)
    final_approved_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Final approved area in hectares")
    
    # Timestamps
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.status})"

    @property
    def has_field_data(self):
        return self.field_officer is not None and self.field_verified_at is not None

    @property
    def has_satellite_data(self):
        return self.isro_admin is not None and self.isro_verified_at is not None

    def update_workflow_status(self, save=True):
        """Advance project status based on data availability.

        - If both field and satellite data exist -> under_review (unless already approved/rejected)
        - Else keep current state (field_data_submitted / satellite_data_submitted / pending)
        """
        if self.status not in ["approved", "rejected"]:
            if self.has_field_data and self.has_satellite_data:
                self.status = "under_review"
                if save:
                    self.save(update_fields=["status", "updated_at"])  # updated_at auto-updates
        return self.status

    @property
    def completion_percentage(self):
        """Calculate project completion percentage"""
        steps = 0
        if self.status in ['field_data_submitted', 'satellite_data_submitted', 'under_review', 'approved', 'rejected']:
            steps += 25  # NGO submitted
        if self.has_field_data:
            steps += 25  # Field data added
        if self.has_satellite_data:
            steps += 25  # Satellite data added
        if self.status in ['approved', 'rejected']:
            steps += 25  # Admin reviewed
        return steps


# --------------------
# Field Officer Data
# --------------------
class FieldDataSubmission(models.Model):
    """Field data submitted by field officers"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='field_submissions')
    field_officer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='field_submissions')
    
    # Survey information
    survey_date = models.DateField()
    hectare_area = models.DecimalField(max_digits=10, decimal_places=2)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    # Environmental data
    soil_type = models.CharField(max_length=100, choices=[
        ('sandy', 'Sandy'),
        ('clay', 'Clay'),
        ('loamy', 'Loamy'),
        ('muddy', 'Muddy'),
        ('rocky', 'Rocky'),
    ])
    water_salinity = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, help_text="Parts per thousand (ppt)")
    tidal_range = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, help_text="Meters")
    
    # Species data (JSON field to store multiple species)
    species_data = models.JSONField(help_text="Array of species with name, count, and health status")
    
    # Additional notes
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Field submission for {self.project.title} by {self.field_officer.username}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update the project with field data
        self.project.field_officer = self.field_officer
        self.project.field_verified_at = self.created_at
        self.project.field_area_measured = self.hectare_area
        self.project.field_species_data = self.species_data
        self.project.field_notes = self.notes
        self.project.field_images_count = self.images.count()
        if self.project.status == 'pending':
            self.project.status = 'field_data_submitted'
        self.project.save()
        # Auto-advance if both datasets present
        self.project.update_workflow_status()


class FieldImage(models.Model):
    """Images submitted with field data"""
    field_submission = models.ForeignKey(FieldDataSubmission, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='field_images/')
    caption = models.CharField(max_length=255, blank=True)
    image_type = models.CharField(max_length=50, choices=[
        ('overview', 'Overview'),
        ('closeup', 'Close-up'),
        ('measurement', 'Measurement'),
        ('species', 'Species'),
        ('gps', 'GPS Location'),
        ('other', 'Other'),
    ], default='other')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.field_submission.project.title} - {self.image_type}"


# --------------------
# ISRO Admin Data
# --------------------
class SatelliteImageSubmission(models.Model):
    """Satellite images uploaded by ISRO admins"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='satellite_submissions')
    isro_admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name='satellite_submissions')
    
    # Image metadata
    image_type = models.CharField(max_length=50, choices=[
        ('pre_project', 'Pre-Project (Baseline)'),
        ('during_project', 'During Project'),
        ('post_project', 'Post-Project'),
        ('monitoring', 'Monitoring'),
    ])
    capture_date = models.DateField()
    satellite_name = models.CharField(max_length=100, choices=[
        ('cartosat', 'Cartosat-2'),
        ('resourcesat', 'ResourceSat-2'),
        ('risat', 'RISAT-1'),
        ('hypersat', 'HysIS'),
        ('landsat', 'Landsat-8'),
        ('sentinel', 'Sentinel-2'),
        ('other', 'Other'),
    ])
    resolution = models.DecimalField(max_digits=5, decimal_places=1, help_text="Spatial resolution in meters")
    
    # Geographic bounds
    north_bound = models.DecimalField(max_digits=9, decimal_places=6)
    south_bound = models.DecimalField(max_digits=9, decimal_places=6)
    east_bound = models.DecimalField(max_digits=9, decimal_places=6)
    west_bound = models.DecimalField(max_digits=9, decimal_places=6)
    
    # Analysis data
    measured_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Satellite measured area in hectares")
    vegetation_index = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True, help_text="NDVI or similar index")
    analysis_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Satellite images for {self.project.title} - {self.image_type}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update the project with satellite data
        self.project.isro_admin = self.isro_admin
        self.project.isro_verified_at = self.created_at
        self.project.satellite_area_measured = self.measured_area
        # Build analysis data safely regardless of string/number/date inputs
        try:
            res_val = float(self.resolution) if self.resolution is not None else None
        except Exception:
            res_val = None

        cap = self.capture_date
        if hasattr(cap, 'isoformat'):
            cap_iso = cap.isoformat()
        else:
            # If capture_date is a string, keep as-is
            cap_iso = str(cap) if cap is not None else None

        self.project.satellite_analysis_data = {
            'vegetation_index': float(self.vegetation_index) if self.vegetation_index else None,
            'satellite_name': self.satellite_name,
            'resolution': res_val,
            'capture_date': cap_iso,
        }
        self.project.isro_notes = self.analysis_notes
        self.project.satellite_images_count = self.images.count()
        if self.project.status in ['pending', 'field_data_submitted']:
            self.project.status = 'satellite_data_submitted'
        self.project.save()
        # Auto-advance if both datasets present
        self.project.update_workflow_status()


class SatelliteImage(models.Model):
    """Individual satellite image files"""
    submission = models.ForeignKey(SatelliteImageSubmission, on_delete=models.CASCADE, related_name='images')
    image = models.FileField(upload_to='satellite_images/')  # Support TIF, TIFF, PNG, JPG
    filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField(help_text="File size in bytes")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Satellite image: {self.filename}"


# --------------------
# Purchase & Credits
# --------------------
class Purchase(models.Model):
    corporate = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    credits = models.IntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    certificate = models.FileField(upload_to="certificates/", null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.corporate.username} bought {self.credits} from {self.project.title}"

    def save(self, *args, **kwargs):
        PRICE_PER_CREDIT = 300.00
        try:
            self.price = round(float(self.credits) * float(PRICE_PER_CREDIT), 2)
        except Exception:
            self.price = 0
        super().save(*args, **kwargs)


# --------------------
# Tendering System
# --------------------
class Tender(models.Model):
    STATUS_CHOICES = [
        ("Open", "Open"),
        ("Allotted", "Allotted"),
        ("Closed", "Closed"),
    ]

    corporate = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tenders")
    title = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    # v1 extension fields (optional) to match full tender spec
    location_preference = models.CharField(max_length=255, blank=True)
    deadline = models.DateField(null=True, blank=True)
    budget_range = models.CharField(max_length=255, blank=True)
    credits_required = models.IntegerField()
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="Open")
    allotted_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="awarded_tenders")
    allotted_project = models.ForeignKey('Project', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.status})"


class TenderApplication(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Applied", "Applied"),  # legacy
        ("Allotted", "Allotted"),
        ("Rejected", "Rejected"),
    ]

    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name="applications")
    ngo = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True)
    # Legacy message field (kept for back-compat)
    message = models.TextField(blank=True)
    # Proposal fields (aligning v1 with v2 UX)
    offered_credits = models.IntegerField(null=True, blank=True)
    price_per_credit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    project_location = models.CharField(max_length=255, blank=True)
    supporting_documents = models.FileField(upload_to="tenders/proposals/", null=True, blank=True)
    project_description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("tender", "ngo")

    def __str__(self):
        return f"Application by {self.ngo.username} for {self.tender.title}"


# --------------------
# Legacy Login Models (keeping for backward compatibility)
# --------------------
class NGOLogin(models.Model):
    email = models.EmailField(unique=True)  
    password = models.CharField(max_length=128)

    def __str__(self):
        return self.email


class CorporateLogin(models.Model):
    email = models.EmailField(unique=True)  
    password = models.CharField(max_length=128)

    def __str__(self):
        return self.email


class AdminLogin(models.Model):
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)

    def __str__(self):
        return self.email


class FieldOfficerLogin(models.Model):
    """Legacy-style login table for Field Officers (email/password)."""
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)

    def __str__(self):
        return self.email


class IsroAdminLogin(models.Model):
    """Legacy-style login table for ISRO Admins (email/password)."""
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)

    def __str__(self):
        return self.email


class MobileToken(models.Model):
    """Simple API token for mobile clients."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    key = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"MobileToken({self.user.username})"


# --------------------
# Blockchain Models
# --------------------
class BlockchainConfig(models.Model):
    """Configuration for blockchain network connection"""
    NETWORK_CHOICES = [
        ('local', 'Local Development'),
        ('sepolia', 'Sepolia Testnet'),
        ('goerli', 'Goerli Testnet'),
        ('mainnet', 'Ethereum Mainnet'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    network_type = models.CharField(max_length=20, choices=NETWORK_CHOICES)
    rpc_url = models.URLField(help_text="RPC endpoint URL")
    chain_id = models.IntegerField()
    
    # Contract addresses (set after deployment)
    carbon_token_address = models.CharField(max_length=42, blank=True, help_text="Carbon Credit Token contract address")
    marketplace_address = models.CharField(max_length=42, blank=True, help_text="Marketplace contract address")
    
    # Account configuration
    private_key = models.CharField(max_length=66, blank=True, help_text="Private key for contract interactions (keep secure!)")
    
    # Status
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_active', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.network_type})"
    
    @classmethod
    def get_active_config(cls):
        """Get the currently active blockchain configuration"""
        return cls.objects.filter(is_active=True).first()
    
    def save(self, *args, **kwargs):
        # Ensure only one config is active at a time
        if self.is_active:
            BlockchainConfig.objects.filter(is_active=True).update(is_active=False)
        super().save(*args, **kwargs)


class ChainBlock(models.Model):
    """Persisted blockchain block for durability across restarts."""
    index = models.IntegerField()
    timestamp = models.FloatField()
    previous_hash = models.CharField(max_length=255, null=True, blank=True)
    nonce = models.IntegerField()
    hash = models.CharField(max_length=255)
    raw = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["index"]

    def __str__(self):
        return f"Block {self.index} ({self.hash[:8]})"


class ChainTransaction(models.Model):
    block = models.ForeignKey(ChainBlock, on_delete=models.CASCADE, related_name="txs", null=True, blank=True)
    sender = models.CharField(max_length=255)
    recipient = models.CharField(max_length=255)
    amount = models.FloatField()
    project_id = models.IntegerField(null=True, blank=True)
    kind = models.CharField(max_length=32)
    meta = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Real blockchain transaction data
    tx_hash = models.CharField(max_length=66, blank=True, help_text="Blockchain transaction hash")
    block_number = models.BigIntegerField(null=True, blank=True, help_text="Blockchain block number")
    gas_used = models.BigIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.kind} {self.amount} -> {self.recipient}"


# --------------------
# Tendering System v2 (non-breaking, parallel to existing)
# --------------------
class TenderV2(models.Model):
    WORKFLOW_CHOICES = [
        ("Open", "Open"),
        ("Under Review", "Under Review"),
        ("Closed", "Closed"),
    ]

    corporate = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tenders_v2")
    tender_title = models.CharField(max_length=255)
    required_credits = models.IntegerField()
    location_preference = models.CharField(max_length=255, blank=True)
    deadline = models.DateField(null=True, blank=True)
    budget_range = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=WORKFLOW_CHOICES, default="Open")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.tender_title} ({self.status})"


class ProposalV2(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Accepted", "Accepted"),
        ("Rejected", "Rejected"),
    ]

    tender = models.ForeignKey(TenderV2, on_delete=models.CASCADE, related_name="proposals")
    contributor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="proposals_v2")
    offered_credits = models.IntegerField()
    price_per_credit = models.DecimalField(max_digits=10, decimal_places=2)
    project_location = models.CharField(max_length=255)
    supporting_documents = models.FileField(upload_to="tenders/proposals/", null=True, blank=True)
    project_description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="Pending")
    chain_tx_hash = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Proposal by {self.contributor.username} for {self.tender.tender_title}"
