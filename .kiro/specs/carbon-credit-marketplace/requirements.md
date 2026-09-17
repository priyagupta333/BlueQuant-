# Requirements Document

## Introduction

The Carbon Credit Marketplace is a comprehensive Django-based platform that facilitates the creation, verification, and trading of carbon credits from environmental restoration projects. The system supports multiple user roles including NGOs (project contributors), corporations (credit purchasers), administrators, field officers, and ISRO satellite data administrators. It features blockchain integration for credit tracking, ML-based credit prediction, and a tendering system for project collaboration.

## Glossary

- **System**: The Carbon Credit Marketplace platform
- **NGO**: Non-governmental organization that submits carbon credit projects
- **Corporate**: Company that purchases carbon credits for offsetting
- **Field_Officer**: Personnel who conduct on-site project verification
- **ISRO_Admin**: Satellite data administrator who provides remote sensing verification
- **Admin**: System administrator who reviews and approves projects
- **Project**: A carbon sequestration initiative submitted by an NGO
- **Credit**: A unit representing one metric ton of CO2 equivalent sequestered
- **Blockchain**: Distributed ledger for tracking credit issuance and transfers
- **Tender**: A request for proposals from corporates seeking specific carbon credits
- **Wallet**: Blockchain address associated with a user for credit transactions
- **ML_Model**: Machine learning model for predicting carbon credit potential

## Requirements

### Requirement 1: Multi-Role User Authentication

**User Story:** As a platform user, I want to register and authenticate with role-specific access, so that I can access appropriate functionality based on my role.

#### Acceptance Criteria

1. THE System SHALL support five distinct user roles: NGO, Corporate, Admin, Field_Officer, and ISRO_Admin
2. WHEN a user registers, THE System SHALL require role-specific information and verification
3. WHEN an NGO registers, THE System SHALL require OTP verification for email and phone
4. WHEN a Corporate registers, THE System SHALL validate corporate email domains and require business documentation
5. THE System SHALL create blockchain wallets automatically for all registered users
6. WHEN a user logs in, THE System SHALL redirect them to their role-specific dashboard
7. THE System SHALL maintain backward compatibility with legacy login tables

### Requirement 2: Project Submission and Management

**User Story:** As an NGO, I want to submit carbon sequestration projects, so that I can generate and sell carbon credits.

#### Acceptance Criteria

1. WHEN an NGO submits a project, THE System SHALL require title, location, species, area, and supporting documents
2. THE System SHALL accept GPS coordinates for precise project location
3. WHEN a project is submitted, THE System SHALL set initial status to "pending"
4. THE System SHALL store project documents securely in media storage
5. THE System SHALL track project workflow through multiple verification stages
6. THE System SHALL prevent duplicate submissions for the same project area

### Requirement 3: ML-Based Credit Prediction

**User Story:** As the system, I want to predict carbon credit potential from project data, so that stakeholders can estimate project value.

#### Acceptance Criteria

1. THE System SHALL load a pre-trained ML model for biomass prediction
2. WHEN a project document is uploaded, THE System SHALL extract image features for prediction
3. THE System SHALL calculate credits based on area, biomass, carbon content, and CO2 equivalent
4. THE System SHALL provide detailed prediction breakdowns including biomass per hectare
5. WHEN the ML model is unavailable, THE System SHALL handle errors gracefully
6. THE System SHALL support both simple feature extraction and full image preprocessing

### Requirement 4: Field Officer Verification

**User Story:** As a field officer, I want to submit on-site verification data, so that projects can be validated with ground-truth measurements.

#### Acceptance Criteria

1. WHEN a field officer submits data, THE System SHALL require survey date, GPS coordinates, and area measurements
2. THE System SHALL collect environmental data including soil type, water salinity, and tidal range
3. THE System SHALL accept multiple species data entries with counts and health status
4. THE System SHALL support multiple field image uploads with categorization
5. WHEN field data is submitted, THE System SHALL update project status to "field_data_submitted"
6. THE System SHALL prevent duplicate field submissions for the same project
7. THE System SHALL link field data to the submitting officer and timestamp

### Requirement 5: Satellite Data Integration

**User Story:** As an ISRO admin, I want to upload satellite imagery and analysis, so that projects can be verified using remote sensing data.

#### Acceptance Criteria

1. WHEN satellite data is uploaded, THE System SHALL require image type, capture date, and satellite source
2. THE System SHALL accept geographic bounds for the satellite coverage area
3. THE System SHALL store measured area and vegetation index from satellite analysis
4. THE System SHALL support multiple satellite image file uploads
5. WHEN satellite data is submitted, THE System SHALL update project status to "satellite_data_submitted"
6. THE System SHALL prevent duplicate satellite submissions for the same project
7. WHEN both field and satellite data exist, THE System SHALL advance status to "under_review"

### Requirement 6: Administrative Project Review

**User Story:** As an admin, I want to review projects with complete verification data, so that I can approve credit issuance.

#### Acceptance Criteria

1. WHEN an admin reviews a project, THE System SHALL require both field and satellite data to be present
2. WHEN a project is approved, THE System SHALL calculate final credits using the ML model
3. WHEN credits are issued, THE System SHALL record the transaction on the blockchain
4. WHEN a project is rejected, THE System SHALL update status and notify the NGO
5. THE System SHALL prevent multiple credit issuance for the same project
6. THE System SHALL provide admin dashboard with pending projects and statistics

### Requirement 7: Blockchain Credit Management

**User Story:** As the system, I want to track credit issuance and transfers on a blockchain, so that all transactions are transparent and immutable.

#### Acceptance Criteria

1. THE System SHALL maintain an in-memory blockchain with persistent storage
2. WHEN credits are issued, THE System SHALL create an "ISSUE" transaction from SYSTEM to NGO wallet
3. WHEN credits are purchased, THE System SHALL create a "TRANSFER" transaction between wallets
4. THE System SHALL mine blocks automatically when transactions are added
5. THE System SHALL persist blockchain data to database models for durability
6. THE System SHALL provide a blockchain explorer for administrators
7. THE System SHALL ensure wallet addresses are unique across all users

### Requirement 8: Corporate Credit Marketplace

**User Story:** As a corporate user, I want to browse and purchase carbon credits, so that I can offset my organization's carbon footprint.

#### Acceptance Criteria

1. WHEN a corporate views the marketplace, THE System SHALL display only approved projects with available credits
2. WHEN purchasing credits, THE System SHALL validate sufficient credit availability
3. WHEN a purchase is completed, THE System SHALL transfer credits via blockchain and update project inventory
4. THE System SHALL generate purchase certificates on demand
5. THE System SHALL send email confirmations to both buyer and seller
6. THE System SHALL provide corporate dashboard with purchase history and statistics
7. THE System SHALL calculate purchase prices at a fixed rate per credit

### Requirement 9: Tendering System

**User Story:** As a corporate user, I want to post tenders for specific carbon credit requirements, so that NGOs can propose suitable projects.

#### Acceptance Criteria

1. WHEN a corporate creates a tender, THE System SHALL require title, location preference, credit requirements, and description
2. THE System SHALL allow NGOs to browse open tenders and submit proposals
3. WHEN an NGO applies to a tender, THE System SHALL require offered credits, pricing, and project details
4. WHEN a corporate accepts a proposal, THE System SHALL close the tender and reject other applications
5. THE System SHALL send email notifications for proposal acceptance and rejection
6. THE System SHALL support both v1 and v2 tender workflows for backward compatibility
7. THE System SHALL track tender status through Open, Under Review, and Closed states

### Requirement 10: Email Notification System

**User Story:** As a user, I want to receive email notifications for important events, so that I stay informed about project and transaction status.

#### Acceptance Criteria

1. WHEN a project is approved, THE System SHALL email the NGO with credit issuance details
2. WHEN credits are purchased, THE System SHALL email both buyer and seller with transaction details
3. WHEN tender proposals are accepted or rejected, THE System SHALL notify the NGO
4. THE System SHALL support both HTML and plain text email formats
5. THE System SHALL use configurable email templates with organization branding
6. THE System SHALL handle email delivery failures gracefully
7. THE System SHALL support OTP delivery via email for registration verification

### Requirement 11: Certificate Generation

**User Story:** As a corporate user, I want to download certificates for my carbon credit purchases, so that I have official documentation for compliance reporting.

#### Acceptance Criteria

1. WHEN a certificate is requested, THE System SHALL generate a PDF certificate with purchase details
2. THE System SHALL include company name, NGO name, credit amount, and CO2 equivalent on certificates
3. THE System SHALL support multiple PDF generation libraries with fallback options
4. THE System SHALL store generated certificates for future download
5. THE System SHALL email certificates to corporate users upon request
6. THE System SHALL include unique certificate IDs and issue dates
7. THE System SHALL handle certificate generation failures gracefully

### Requirement 12: Mobile API Support

**User Story:** As a mobile app user, I want to access core functionality via API endpoints, so that I can use the platform on mobile devices.

#### Acceptance Criteria

1. THE System SHALL provide token-based authentication for mobile clients
2. THE System SHALL support project submission via multipart form data
3. THE System SHALL return JSON responses for mobile dashboard data
4. THE System SHALL provide project detail endpoints with prediction information
5. THE System SHALL support file uploads for project documents via mobile API
6. THE System SHALL maintain API compatibility with existing mobile applications
7. THE System SHALL validate mobile API requests and handle errors appropriately

### Requirement 13: Data Persistence and Storage

**User Story:** As the system, I want to persist all data reliably, so that no information is lost and the platform remains consistent.

#### Acceptance Criteria

1. THE System SHALL use PostgreSQL as the primary database with proper connection handling
2. THE System SHALL store uploaded files in organized media directories
3. THE System SHALL persist blockchain data to database models for durability across restarts
4. THE System SHALL handle database connection failures gracefully
5. THE System SHALL support database migrations for schema changes
6. THE System SHALL maintain referential integrity between related models
7. THE System SHALL backup critical data including projects, transactions, and user information

### Requirement 14: Security and Access Control

**User Story:** As a platform administrator, I want robust security controls, so that user data and transactions are protected.

#### Acceptance Criteria

1. THE System SHALL enforce role-based access control for all endpoints
2. THE System SHALL validate file uploads and prevent malicious content
3. THE System SHALL use CSRF protection for all form submissions
4. THE System SHALL sanitize user inputs to prevent injection attacks
5. THE System SHALL require HTTPS in production environments
6. THE System SHALL implement secure password policies and hashing
7. THE System SHALL log security events for audit purposes

### Requirement 15: System Configuration and Deployment

**User Story:** As a system administrator, I want configurable deployment options, so that the platform can be deployed in different environments.

#### Acceptance Criteria

1. THE System SHALL use environment variables for sensitive configuration
2. THE System SHALL support both development and production settings
3. THE System SHALL configure email backends based on environment settings
4. THE System SHALL handle missing configuration gracefully with sensible defaults
5. THE System SHALL support static file serving in production
6. THE System SHALL provide health check endpoints for monitoring
7. THE System SHALL include comprehensive logging for debugging and monitoring