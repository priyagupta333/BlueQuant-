from django.urls import path
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    # --------------------
    # Public URLs
    # --------------------
    path("", views.home, name="home"),
    path("login/", views.user_login, name="login"),
    # Role-specific login pages (reuse the same backend auth handler)
    path("login/contributor/", TemplateView.as_view(template_name="api/auth/contributor_login.html"), name="login_contributor"),
    path("login/corporate/", TemplateView.as_view(template_name="api/auth/corporate_login.html"), name="login_corporate"),
    path("login/admin/", TemplateView.as_view(template_name="api/auth/admin_login.html"), name="login_admin"),
    path("login/field-officer/", TemplateView.as_view(template_name="api/auth/field_officer_login.html"), name="login_field_officer"),
    path("login/isro-admin/", TemplateView.as_view(template_name="api/auth/isro_admin_login.html"), name="login_isro_admin"),
    path("logout/", views.user_logout, name="logout"),
    path("register/ngo/", views.register_ngo, name="register_ngo"),
    path("register/corporate/", views.register_corporate, name="register_corporate"),
    # OTP endpoints
    path("api/otp/send-email/", views.send_email_otp, name="send_email_otp"),
    path("api/otp/verify-email/", views.verify_email_otp, name="verify_email_otp"),
    path("api/otp/send-phone/", views.send_phone_otp, name="send_phone_otp"),
    path("api/otp/verify-phone/", views.verify_phone_otp, name="verify_phone_otp"),
    path("blockchain/", views.blockchain_explorer, name="blockchain_explorer"),
    path("api/blockchain/status/", views.api_blockchain_status, name="api_blockchain_status"),
    path("admin/blockchain/status/", views.blockchain_status, name="blockchain_status"),
    path("api/wallet/info/", views.user_wallet_info, name="user_wallet_info"),

    # --------------------
    # NGO URLs
    # --------------------
    path("ngo/dashboard/", views.ngo_dashboard, name="ngo_dashboard"),
    path("ngo/upload-project/", views.upload_project, name="upload_project"),

    # --------------------
    # Field Officer URLs
    # --------------------
    path("field-officer/dashboard/", views.field_officer_dashboard, name="field_officer_dashboard"),
    path("api/submit-field-data/", views.submit_field_data, name="submit_field_data"),
    path("field-officer/projects/", views.field_officer_projects, name="field_officer_projects"),
    path("field-officer/submissions/", views.field_officer_submissions, name="field_officer_submissions"),
    path("field-officer/submission/<int:submission_id>/", views.field_officer_submission_detail, name="field_officer_submission_detail"),

    # --------------------
    # ISRO Admin URLs
    # --------------------
    path("isro/dashboard/", views.isro_admin_dashboard, name="isro_admin_dashboard"),
    # Pending projects list view
    path("isro/pending-projects/", views.isro_pending_projects, name="isro_pending_projects"),
    # Analytics view
    path("isro/analytics/", views.isro_analytics, name="isro_analytics"),
    path("api/upload-satellite-images/", views.upload_satellite_images, name="upload_satellite_images"),

    # --------------------
    # Admin URLs (avoid conflict with Django Admin at /admin/)
    # --------------------
    path("panel/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("panel/review-project/<int:project_id>/", views.review_project, name="review_project"),
    path("panel/reports-data/", views.reports_data, name="reports_data"),
    path("api/approve-project/<int:project_id>/", views.approve_project, name="approve_project"),
    path("api/reject-project/<int:project_id>/", views.reject_project, name="reject_project"),
    path("about/", views.about, name="about"),
    path("project/<int:project_id>/detail/", views.project_detail_modal, name="project_detail_modal"),
    path("mobile/projects/", views.mobile_upload_project, name="mobile_upload_project"),
    path("mobile/login/", views.mobile_login, name="mobile_login"),
    path("mobile/profile/", views.mobile_profile, name="mobile_profile"),
    path("mobile/ngo/projects/", views.mobile_ngo_projects, name="mobile_ngo_projects"),
    path("mobile/projects/<int:project_id>/", views.mobile_project_detail, name="mobile_project_detail"),

    # --------------------
    # Corporate URLs
    # --------------------
    path("corporate/dashboard/", views.corporate_dashboard, name="corporate_dashboard"),
    path("corporate/purchase/<int:project_id>/", views.purchase_credits, name="purchase_credits"),
    path("corporate/certificate/<int:purchase_id>/download/", views.download_certificate, name="download_certificate"),
    path("corporate/certificate/<int:purchase_id>/request/", views.request_certificate, name="request_certificate"),

    # Tenders
    path("corporate/tenders/", views.tenders_list, name="tenders_list"),
    path("corporate/tenders/new/", views.tender_create, name="tender_create"),
    path("corporate/tenders/<int:tender_id>/", views.tender_review, name="tender_review"),
    path("corporate/tenders/<int:tender_id>/accept/<int:application_id>/", views.tender_accept, name="tender_accept"),
    path("corporate/tenders/<int:tender_id>/reject/<int:application_id>/", views.tender_reject, name="tender_reject"),
    path("corporate/tenders/<int:tender_id>/allot/<int:application_id>/", views.tender_allot, name="tender_allot"),

    path("ngo/tenders/", views.tenders_browse, name="tenders_browse"),
    path("ngo/tenders/<int:tender_id>/apply/", views.tender_apply, name="tender_apply"),

    path("collaboration/", views.collaboration_hub, name="collaboration_hub"),

    # Tenders v2 (parallel routes)
    path("corporate/tenders/v2/", views.tenders_v2_list, name="tenders_v2_list"),
    path("corporate/tenders/v2/new/", views.tender_v2_create, name="tender_v2_create"),
    path("corporate/tenders/v2/<int:tender_id>/", views.tender_v2_review, name="tender_v2_review"),
    path("corporate/tenders/v2/<int:tender_id>/accept/<int:proposal_id>/", views.tender_v2_accept, name="tender_v2_accept"),
    path("corporate/tenders/v2/<int:tender_id>/reject/<int:proposal_id>/", views.tender_v2_reject, name="tender_v2_reject"),
    path("ngo/tenders/v2/", views.tenders_v2_browse, name="tenders_v2_browse"),
    path("ngo/tenders/v2/<int:tender_id>/apply/", views.tender_v2_apply, name="tender_v2_apply"),
]
# Force reload

