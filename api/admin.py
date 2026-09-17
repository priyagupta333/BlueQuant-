from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import (
    UserProfile, Project, Purchase, Tender, TenderApplication, 
    NGOLogin, CorporateLogin, AdminLogin, FieldOfficerLogin, IsroAdminLogin,
    FieldDataSubmission, FieldImage, SatelliteImageSubmission, SatelliteImage,
    Wallet, ChainBlock, ChainTransaction, BlockchainConfig, MobileToken,
    TenderV2, ProposalV2
)


# --------------------
# User Management
# --------------------
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'is_staff')
    list_filter = BaseUserAdmin.list_filter + ('profile__role',)
    
    def get_role(self, obj):
        try:
            return obj.profile.role
        except UserProfile.DoesNotExist:
            return 'No Profile'
    get_role.short_description = 'Role'


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'organization', 'phone', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('user__username', 'user__email', 'organization')


# --------------------
# Blockchain Management
# --------------------
@admin.register(BlockchainConfig)
class BlockchainConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'network_type', 'chain_id', 'is_active', 'has_contracts', 'created_at')
    list_filter = ('network_type', 'is_active')
    search_fields = ('name', 'rpc_url')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Configuration', {
            'fields': ('name', 'network_type', 'rpc_url', 'chain_id', 'is_active')
        }),
        ('Contract Addresses', {
            'fields': ('carbon_token_address', 'marketplace_address'),
            'description': 'Set these after deploying the smart contracts'
        }),
        ('Security', {
            'fields': ('private_key',),
            'classes': ('collapse',),
            'description': 'Private key for contract interactions. Keep secure!'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def has_contracts(self, obj):
        return bool(obj.carbon_token_address and obj.marketplace_address)
    has_contracts.boolean = True
    has_contracts.short_description = 'Contracts Deployed'


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'address', 'is_external', 'get_balance_display', 'created_at')
    list_filter = ('is_external', 'created_at')
    search_fields = ('user__username', 'address')
    readonly_fields = ('created_at', 'get_balance_display')
    
    def get_balance_display(self, obj):
        try:
            balance = obj.get_balance()
            return f"{balance} CCT"
        except Exception:
            return "N/A"
    get_balance_display.short_description = 'Token Balance'


@admin.register(ChainBlock)
class ChainBlockAdmin(admin.ModelAdmin):
    list_display = ('index', 'hash_short', 'transaction_count', 'timestamp_formatted')
    list_filter = ('timestamp',)
    search_fields = ('hash', 'previous_hash')
    readonly_fields = ('hash', 'raw')
    
    def hash_short(self, obj):
        return f"{obj.hash[:8]}...{obj.hash[-8:]}" if obj.hash else "N/A"
    hash_short.short_description = 'Hash'
    
    def transaction_count(self, obj):
        return obj.txs.count()
    transaction_count.short_description = 'Transactions'
    
    def timestamp_formatted(self, obj):
        import datetime
        return datetime.datetime.fromtimestamp(obj.timestamp).strftime('%Y-%m-%d %H:%M:%S')
    timestamp_formatted.short_description = 'Timestamp'


@admin.register(ChainTransaction)
class ChainTransactionAdmin(admin.ModelAdmin):
    list_display = ('kind', 'sender_short', 'recipient_short', 'amount', 'project_id', 'tx_hash_short', 'timestamp')
    list_filter = ('kind', 'timestamp')
    search_fields = ('sender', 'recipient', 'tx_hash')
    readonly_fields = ('timestamp',)
    
    def sender_short(self, obj):
        return f"{obj.sender[:8]}...{obj.sender[-8:]}" if len(obj.sender) > 16 else obj.sender
    sender_short.short_description = 'Sender'
    
    def recipient_short(self, obj):
        return f"{obj.recipient[:8]}...{obj.recipient[-8:]}" if len(obj.recipient) > 16 else obj.recipient
    recipient_short.short_description = 'Recipient'
    
    def tx_hash_short(self, obj):
        if obj.tx_hash:
            return f"{obj.tx_hash[:8]}...{obj.tx_hash[-8:]}"
        return "N/A"
    tx_hash_short.short_description = 'Tx Hash'


# --------------------
# Project Management
# --------------------
@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'ngo', 'status', 'credits', 'chain_issued', 'completion_percentage', 'submitted_at')
    list_filter = ('status', 'chain_issued', 'submitted_at')
    search_fields = ('title', 'location', 'ngo__username')
    readonly_fields = ('submitted_at', 'updated_at', 'completion_percentage')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('ngo', 'title', 'location', 'species', 'area', 'document', 'latitude', 'longitude')
        }),
        ('Status', {
            'fields': ('status', 'credits', 'chain_issued', 'completion_percentage')
        }),
        ('Field Data', {
            'fields': ('field_officer', 'field_verified_at', 'field_area_measured', 'field_notes'),
            'classes': ('collapse',)
        }),
        ('Satellite Data', {
            'fields': ('isro_admin', 'isro_verified_at', 'satellite_area_measured', 'isro_notes'),
            'classes': ('collapse',)
        }),
        ('Admin Review', {
            'fields': ('admin_reviewer', 'admin_review_notes', 'final_approved_area'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('submitted_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


# --------------------
# Field Data
# --------------------
class FieldImageInline(admin.TabularInline):
    model = FieldImage
    extra = 0
    readonly_fields = ('uploaded_at',)


@admin.register(FieldDataSubmission)
class FieldDataSubmissionAdmin(admin.ModelAdmin):
    list_display = ('project', 'field_officer', 'survey_date', 'hectare_area', 'soil_type', 'created_at')
    list_filter = ('soil_type', 'survey_date', 'created_at')
    search_fields = ('project__title', 'field_officer__username')
    inlines = [FieldImageInline]


# --------------------
# Satellite Data
# --------------------
class SatelliteImageInline(admin.TabularInline):
    model = SatelliteImage
    extra = 0
    readonly_fields = ('uploaded_at', 'file_size')


@admin.register(SatelliteImageSubmission)
class SatelliteImageSubmissionAdmin(admin.ModelAdmin):
    list_display = ('project', 'isro_admin', 'image_type', 'capture_date', 'satellite_name', 'measured_area', 'created_at')
    list_filter = ('image_type', 'satellite_name', 'capture_date', 'created_at')
    search_fields = ('project__title', 'isro_admin__username')
    inlines = [SatelliteImageInline]


# --------------------
# Marketplace
# --------------------
@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('corporate', 'project', 'credits', 'price', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('corporate__username', 'project__title')
    readonly_fields = ('price', 'timestamp')


@admin.register(Tender)
class TenderAdmin(admin.ModelAdmin):
    list_display = ('title', 'corporate', 'credits_required', 'status', 'allotted_to', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'corporate__username', 'location')


@admin.register(TenderApplication)
class TenderApplicationAdmin(admin.ModelAdmin):
    list_display = ('tender', 'ngo', 'status', 'offered_credits', 'price_per_credit', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('tender__title', 'ngo__username')


# --------------------
# Legacy Login Models
# --------------------
@admin.register(NGOLogin)
class NGOLoginAdmin(admin.ModelAdmin):
    list_display = ('email',)
    search_fields = ('email',)


@admin.register(CorporateLogin)
class CorporateLoginAdmin(admin.ModelAdmin):
    list_display = ('email',)
    search_fields = ('email',)


@admin.register(AdminLogin)
class AdminLoginAdmin(admin.ModelAdmin):
    list_display = ('email',)
    search_fields = ('email',)


@admin.register(FieldOfficerLogin)
class FieldOfficerLoginAdmin(admin.ModelAdmin):
    list_display = ('email',)
    search_fields = ('email',)


@admin.register(IsroAdminLogin)
class IsroAdminLoginAdmin(admin.ModelAdmin):
    list_display = ('email',)
    search_fields = ('email',)


@admin.register(MobileToken)
class MobileTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'key_short', 'created_at')
    search_fields = ('user__username', 'key')
    readonly_fields = ('created_at',)
    
    def key_short(self, obj):
        return f"{obj.key[:8]}...{obj.key[-8:]}"
    key_short.short_description = 'API Key'


# --------------------
# Tendering System v2
# --------------------
@admin.register(TenderV2)
class TenderV2Admin(admin.ModelAdmin):
    list_display = ('tender_title', 'corporate', 'required_credits', 'status', 'deadline', 'created_at')
    list_filter = ('status', 'created_at', 'deadline')
    search_fields = ('tender_title', 'corporate__username')


@admin.register(ProposalV2)
class ProposalV2Admin(admin.ModelAdmin):
    list_display = ('tender', 'contributor', 'offered_credits', 'price_per_credit', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('tender__tender_title', 'contributor__username')


# Customize admin site
admin.site.site_header = "Carbon Credit Marketplace Admin"
admin.site.site_title = "Carbon Credit Admin"
admin.site.index_title = "Welcome to Carbon Credit Marketplace Administration"
