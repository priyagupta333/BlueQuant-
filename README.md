# BlueQuant

A **Blockchain-Based Monitoring, Reporting & Verification (MRV) Platform** for Blue Carbon ecosystems. This system enables transparent, verifiable, and decentralized carbon credit management for mangrove and coastal restoration projects.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Installation & Setup](#installation--setup)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [User Roles & Workflows](#user-roles--workflows)
- [Smart Contracts](#smart-contracts)
- [API Reference](#api-reference)
- [Mobile Application](#mobile-application)
- [Blockchain Integration](#blockchain-integration)
- [Development Guide](#development-guide)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

---

## Overview

BlueQuant is designed to:

- **Verify** NGO/Panchayat restoration projects using satellite imagery and field data
- **Calculate** carbon sequestration using ML-powered biomass estimation
- **Tokenize** verified carbon credits on the Ethereum blockchain
- **Trade** carbon credits through a transparent marketplace
- **Connect** NGOs, Corporates, Field Officers, and Administrators

---

## Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| ML-Powered Verification | Biomass estimation from satellite/drone imagery using trained models |
| Blockchain Registry | Immutable credit issuance and transfer via ERC-20 smart contracts |
| Carbon Calculation | Biomass to Carbon to CO2e to Credits pipeline |
| Multi-Role Dashboards | Tailored interfaces for NGOs, Corporates, Admins, Field Officers, ISRO |
| Mobile App | Flutter-based NGO app for field data collection |
| Tender Marketplace | Corporate tender system for carbon credit procurement |
| Email Notifications | Automated notifications for project status updates |
| Certificate Generation | PDF certificates for carbon credit purchases.. |

### User Portals

- **NGO/Contributor Portal** - Submit projects, upload evidence, track credits
- **Corporate Portal** - Browse marketplace, create tenders, purchase credits
- **Admin Portal (NCCR)** - Review projects, approve credits, manage system
- **Field Officer Portal** - Submit ground-truth field data
- **ISRO Admin Portal** - Upload satellite imagery and analysis

---

## System Architecture

```
+-----------------------------------------------------------------------------+
|                              PRESENTATION LAYER                              |
+-----------------------------------------------------------------------------+
|  +---------------+  +---------------+  +-----------------------------+      |
|  |  Web Portal   |  |  Mobile App   |  |    Blockchain Explorer      |      |
|  |  (Django)     |  |  (Flutter)    |  |    (Web Interface)          |      |
|  +-------+-------+  +-------+-------+  +-------------+---------------+      |
+----------|-----------------|-----------------------|------------------------+
           |                 |                       |
+----------|-----------------|-----------------------|------------------------+
|          v                 v                       v                        |
|  +---------------------------------------------------------------------+    |
|  |                       DJANGO BACKEND (API)                           |    |
|  |  +--------+ +--------+ +--------+ +--------+ +--------+              |    |
|  |  | Views  | | Models | | Forms  | | Emails | | Signals|              |    |
|  |  +--------+ +--------+ +--------+ +--------+ +--------+              |    |
|  +---------------------------------------------------------------------+    |
|                             APPLICATION LAYER                                |
+-----------------------------------------------------------------------------+
           |                                              |
+----------|--------------------------------------------- |--------------------+
|          v                                             v                    |
|  +-------------------+                    +---------------------------+     |
|  |  PostgreSQL DB    |                    |   Blockchain Service      |     |
|  |  (Neon/Local)     |                    |   +-------------------+   |     |
|  |                   |                    |   |  Web3.py Client   |   |     |
|  |  - Users/Profiles |                    |   +---------+---------+   |     |
|  |  - Projects       |                    |             |             |     |
|  |  - Transactions   |                    |   +---------v---------+   |     |
|  |  - Tenders        |                    |   | Hardhat Network   |   |     |
|  |  - Wallets        |                    |   | (Local/Testnet)   |   |     |
|  +-------------------+                    |   +---------+---------+   |     |
|                                           |             |             |     |
|                                           |   +---------v---------+   |     |
|                                           |   | Smart Contracts   |   |     |
|                                           |   | - CarbonToken     |   |     |
|                                           |   | - Marketplace     |   |     |
|                                           |   +-------------------+   |     |
|                                           +---------------------------+     |
|                               DATA & BLOCKCHAIN LAYER                        |
+-----------------------------------------------------------------------------+
           |
+----------|-----------------------------------------------------------------+
|          v                                                                  |
|  +---------------------------------------------------------------------+    |
|  |                       ML PREDICTION ENGINE                           |    |
|  |  +----------------+  +----------------+  +------------------+        |    |
|  |  |Image Processing|->|Feature Extract |->| AGBM Prediction  |        |    |
|  |  |(Pillow/NumPy)  |  |(RGB, VI Index) |  | (scikit-learn)   |        |    |
|  |  +----------------+  +----------------+  +------------------+        |    |
|  +---------------------------------------------------------------------+    |
|                             ML/ANALYTICS LAYER                               |
+-----------------------------------------------------------------------------+
```

---

## Technology Stack

### Backend
| Component | Technology | Version |
|-----------|------------|---------|
| Framework | Django | 5.2.4 |
| Language | Python | 3.10+ |
| Database | PostgreSQL (Neon) | 15+ |
| ORM | Django ORM | - |
| Authentication | Django Auth + Custom Roles | - |
| Environment | django-environ | 0.12.0 |
| Email | SMTP (Gmail) | - |
| File Storage | Django Media Files | - |
| ASGI Server | Uvicorn/Gunicorn | - |

### Frontend (Web)
| Component | Technology | Version |
|-----------|------------|---------|
| Templates | Django Templates | - |
| Markup | HTML5 | - |
| Styling | CSS3 | - |
| Framework | Bootstrap | 5.x |
| JavaScript | Vanilla JS / ES6+ | - |
| Icons | Font Awesome | 6.x |
| Charts | Chart.js | - |

### Blockchain
| Component | Technology | Version |
|-----------|------------|---------|
| Network | Ethereum | - |
| Local Dev Network | Hardhat | 2.19.0 |
| Testnet | Sepolia | - |
| Smart Contract Language | Solidity | 0.8.20 |
| Contract Framework | OpenZeppelin | 5.4.0 |
| Web3 Client (Python) | Web3.py | 7.6.0 |
| Account Management | eth-account | 0.13.4 |
| Solidity Compiler | solc | via py-solc-x 2.0.3 |
| Key Management | eth-keys | 0.6.0 |
| Hex Utilities | hexbytes | 1.2.1 |

### Mobile Application
| Component | Technology | Version |
|-----------|------------|---------|
| Framework | Flutter | 3.x |
| Language | Dart | 3.0+ |
| State Management | StatefulWidget | - |
| HTTP Client | http | 1.1.0 |
| Secure Storage | flutter_secure_storage | 9.0.0 |
| Image Picker | image_picker | 1.0.4 |
| File System | path_provider | 2.1.1 |
| Local Storage | shared_preferences | 2.2.2 |
| Date Formatting | intl | 0.19.0 |
| Charts | fl_chart | 0.64.0 |
| Image Caching | cached_network_image | 3.3.0 |
| GPS/Location | geolocator | 10.1.0 |
| Permissions | permission_handler | 11.0.1 |
| App Info | package_info_plus | 4.2.0 |

### Machine Learning & Data Science
| Component | Technology | Version |
|-----------|------------|---------|
| ML Framework | scikit-learn | 1.8.0 |
| Numerical Computing | NumPy | 2.3.5 |
| Data Analysis | Pandas | 2.3.3 |
| Scientific Computing | SciPy | 1.16.3 |
| Image Processing | Pillow | latest |
| Model Serialization | joblib | 1.5.2 |
| Thread Pool | threadpoolctl | 3.6.0 |

### Database & Storage
| Component | Technology | Version |
|-----------|------------|---------|
| Primary Database | PostgreSQL | 15+ |
| Cloud Database | Neon | - |
| Python DB Adapter | psycopg2-binary | 2.9.11 |
| File Storage | Local Media / S3 | - |

### DevOps & Tools
| Component | Technology | Purpose |
|-----------|------------|---------|
| Version Control | Git | Source control |
| Package Manager (Python) | pip | Python dependencies |
| Package Manager (Node) | npm | Node dependencies |
| Task Runner | Hardhat | Contract compilation/deployment |
| Environment Variables | python-environ | Config management |

### Security Libraries
| Component | Technology | Purpose |
|-----------|------------|---------|
| Password Hashing | Django PBKDF2 | User authentication |
| CSRF Protection | Django Middleware | Form security |
| SQL Injection | Django ORM | Query parameterization |
| Contract Security | OpenZeppelin | Audited patterns |

### Python Dependencies (Complete)
```
asgiref==3.11.0
Django==5.2.4
django-environ==0.12.0
joblib==1.5.2
numpy==2.3.5
pandas==2.3.3
psycopg2-binary==2.9.11
python-dateutil==2.9.0.post0
python-environ==0.4.54
pytz==2025.2
scikit-learn==1.8.0
scipy==1.16.3
six==1.17.0
sqlparse==0.5.4
threadpoolctl==3.6.0
tzdata==2025.2
Pillow
web3==7.6.0
py-solc-x==2.0.3
eth-account==0.13.4
eth-keys==0.6.0
hexbytes==1.2.1
```

### Node.js Dependencies (Contracts)
```json
{
  "devDependencies": {
    "@nomicfoundation/hardhat-toolbox": "^4.0.0",
    "hardhat": "^2.19.0"
  },
  "dependencies": {
    "@openzeppelin/contracts": "^5.4.0"
  }
}
```

### Flutter Dependencies (Mobile)
```yaml
dependencies:
  flutter: sdk
  http: ^1.1.0
  flutter_secure_storage: ^9.0.0
  image_picker: ^1.0.4
  path_provider: ^2.1.1
  shared_preferences: ^2.2.2
  intl: ^0.19.0
  fl_chart: ^0.64.0
  cached_network_image: ^3.3.0
  geolocator: ^10.1.0
  permission_handler: ^11.0.1
  package_info_plus: ^4.2.0
```

---

## Project Structure

```
bluequant/
|-- api/                          # Django API application
|   |-- models.py                 # Database models
|   |-- views.py                  # View controllers
|   |-- urls.py                   # URL routing
|   |-- forms.py                  # Form definitions
|   |-- blockchain.py             # Blockchain manager
|   |-- blockchain_service.py     # Blockchain service layer
|   |-- blockchain_auto_setup.py  # Auto blockchain initialization
|   |-- emails.py                 # Email utilities
|   |-- signals.py                # Django signals
|   |-- admin.py                  # Admin configuration
|   |-- templates/                # HTML templates
|   |   +-- api/
|   |       |-- auth/             # Authentication pages
|   |       |-- dashboards/       # Role-specific dashboards
|   |       |-- blockchain/       # Blockchain explorer
|   |       |-- tenders/          # Tender system
|   |       |-- projects/         # Project management
|   |       +-- emails/           # Email templates
|   +-- static/                   # Static assets
|
|-- backend/                      # Django project settings
|   |-- settings.py               # Main configuration
|   |-- urls.py                   # Root URL config
|   |-- wsgi.py                   # WSGI entry point
|   +-- asgi.py                   # ASGI entry point
|
|-- contracts/                    # Smart contracts
|   |-- contracts/
|   |   |-- CarbonCreditToken.sol     # ERC-20 carbon token
|   |   +-- CarbonCreditMarketplace.sol # Marketplace contract
|   |-- scripts/
|   |   +-- deploy.js             # Deployment script
|   |-- deployments/              # Deployment artifacts
|   |-- hardhat.config.js         # Hardhat configuration
|   +-- package.json              # Node dependencies
|
|-- mobile/                       # Mobile application
|   +-- flutter_ngo_app/
|       |-- lib/
|       |   |-- main.dart         # App entry point
|       |   |-- config.dart       # API configuration
|       |   |-- screens/          # UI screens
|       |   |-- theme/            # App theming
|       |   +-- widgets/          # Reusable widgets
|       +-- pubspec.yaml          # Flutter dependencies
|
|-- dataset/                      # ML model and training data
|   +-- agbm_model.joblib         # Trained biomass model
|
|-- scripts/                      # Utility scripts
|   |-- deploy_contracts.py       # Python contract deployer
|   |-- setup_real_blockchain.py  # Blockchain setup
|   +-- email_test.py             # Email testing
|
|-- media/                        # User uploads
|-- logs/                         # Application logs
|-- manage.py                     # Django CLI
|-- requirements.txt              # Python dependencies
|-- .env.example                  # Environment template
+-- README.md                     # This file
```

---

## Installation & Setup

### Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- PostgreSQL database (or Neon account)
- Flutter SDK 3.x (for mobile development)
- Git

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd bluequant
```

### Step 2: Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Environment Configuration

```bash
# Copy example environment file
copy .env.example .env   # Windows
cp .env.example .env     # Linux/Mac

# Edit .env with your configuration
```

### Step 4: Database Setup

```bash
# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser
```

### Step 5: Smart Contract Setup

```bash
# Navigate to contracts directory
cd contracts

# Install Node dependencies
npm install

# Compile contracts
npm run compile

# Return to project root
cd ..
```

### Step 6: Start Local Blockchain (Development)

```bash
# In a separate terminal, start Hardhat node
cd contracts
npx hardhat node

# Deploy contracts (in another terminal)
npm run deploy:local
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Security
SECRET_KEY='your-django-secret-key-here'
DEBUG=True

# Database (PostgreSQL)
DATABASE_URL=postgresql://user:password@host:port/dbname?sslmode=require

# Allowed Hosts
ALLOWED_HOSTS=127.0.0.1,localhost

# Email Configuration
EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST='smtp.gmail.com'
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER='your-email@gmail.com'
EMAIL_HOST_PASSWORD='your-app-password'
DEFAULT_FROM_EMAIL='your-email@gmail.com'

# Organization Branding
ORG_NAME='BlueQuant'
SENDER_NAME='BlueQuant Support'
SUPPORT_EMAIL='support@example.com'
DASHBOARD_URL='http://127.0.0.1:8000/'

# Blockchain (Local Development)
HARDHAT_PRIVATE_KEY=0xxxxxx
```

### Blockchain Networks

The system supports multiple networks configured in `contracts/hardhat.config.js`:

| Network | Chain ID | RPC URL | Use Case |
|---------|----------|---------|----------|
| localhost | 1337 | http://127.0.0.1:8545 | Development |
| sepolia | 11155111 | Via Infura/Alchemy | Testing |
| mainnet | 1 | Via Infura/Alchemy | Production |

---

## Running the Application

### Development Mode

```bash
# Terminal 1: Start blockchain (if using local)
cd contracts
npx hardhat node

# Terminal 2: Deploy contracts
cd contracts
npm run deploy:local

# Terminal 3: Start Django server
python manage.py runserver 8000
```

Access the application at: `http://127.0.0.1:8000`

### Auto Blockchain Setup

The system includes automatic blockchain initialization. When Django starts:
1. Checks if local blockchain is running
2. Starts Hardhat node if needed
3. Deploys smart contracts automatically
4. Updates Django configuration with contract addresses

---

## User Roles & Workflows

### 1. NGO/Contributor

**Registration:** `/register/ngo/`

**Workflow:**
1. Register with email/phone OTP verification
2. Submit restoration project with location, species, area
3. Upload supporting documents/images
4. Track project status through verification stages
5. Receive carbon credits upon approval
6. Browse and apply to corporate tenders

**Dashboard Features:**
- Project submission form
- Project status tracking
- Credit balance display
- Tender applications

### 2. Field Officer

**Workflow:**
1. View assigned pending projects
2. Conduct field surveys
3. Submit field data (GPS, area, species, soil type)
4. Upload field photographs
5. Add verification notes

**Data Collected:**
- Survey date and GPS coordinates
- Measured hectare area
- Soil type and water salinity
- Species inventory with health status
- Photographic evidence

### 3. ISRO Administrator

**Workflow:**
1. View projects pending satellite verification
2. Upload satellite imagery (pre/during/post project)
3. Provide measured area from satellite analysis
4. Submit vegetation indices (NDVI)
5. Add analysis notes

**Supported Satellites:**
- Cartosat-2, ResourceSat-2, RISAT-1
- HysIS, Landsat-8, Sentinel-2

### 4. System Administrator

**Workflow:**
1. Review projects with complete field + satellite data
2. View ML-predicted carbon credits
3. Approve or reject projects
4. Credits automatically minted on blockchain upon approval
5. Generate reports

**Review Criteria:**
- Field data completeness
- Satellite verification match
- Area consistency between sources
- Species viability assessment

### 5. Corporate User

**Workflow:**
1. Register corporate account
2. Browse verified projects in marketplace
3. Purchase carbon credits directly
4. Create tenders for credit requirements
5. Review NGO proposals
6. Award tenders and receive credits
7. Download purchase certificates

---

## Smart Contracts

### CarbonCreditToken (ERC-20)

**Address:** Deployed to local/testnet

**Features:**
- ERC-20 compliant carbon credit token
- Project registration with NGO association
- Minting controlled by contract owner
- Project-specific credit tracking
- Pausable for emergency stops

**Key Functions:**
```solidity
function registerProject(string name, address ngo, uint256 estimatedCredits) returns (uint256 projectId)
function mintCredits(address to, uint256 amount, uint256 projectId)
function transferCredits(address to, uint256 amount, uint256 projectId)
function transferCreditsFrom(address from, address to, uint256 amount, uint256 projectId)
function getUserProjectCredits(address user, uint256 projectId) returns (uint256)
```

### CarbonCreditMarketplace

**Features:**
- Tender creation by corporates
- Proposal submission by NGOs
- Automated tender awarding
- Direct listing marketplace
- 2.5% marketplace fee

**Key Functions:**
```solidity
function createTender(title, description, creditsRequired, maxPrice, durationDays) returns (uint256)
function submitProposal(tenderId, creditsOffered, pricePerCredit, projectId, description) returns (uint256)
function awardTender(tenderId, proposalId)
function createDirectListing(projectId, creditsAmount, pricePerCredit) returns (uint256)
function purchaseFromListing(listingId, creditsAmount)
```

---

## API Reference

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/login/` | User login |
| GET | `/logout/` | User logout |
| GET/POST | `/register/ngo/` | NGO registration |
| GET/POST | `/register/corporate/` | Corporate registration |
| POST | `/api/otp/send-email/` | Send email OTP |
| POST | `/api/otp/verify-email/` | Verify email OTP |

### Project Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/ngo/dashboard/` | NGO dashboard |
| POST | `/ngo/upload-project/` | Submit new project |
| GET | `/project/<id>/detail/` | Project details modal |
| POST | `/panel/review-project/<id>/` | Admin review action |

### Field Officer Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/field-officer/dashboard/` | Field officer dashboard |
| GET | `/field-officer/projects/` | Assigned projects list |
| POST | `/api/submit-field-data/` | Submit field survey data |
| GET | `/field-officer/submissions/` | View past submissions |

### ISRO Admin Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/isro/dashboard/` | ISRO admin dashboard |
| GET | `/isro/pending-projects/` | Projects awaiting satellite data |
| POST | `/api/upload-satellite-images/` | Upload satellite imagery |
| GET | `/isro/analytics/` | Analytics dashboard |

### Blockchain Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/blockchain/` | Blockchain explorer |
| GET | `/api/blockchain/status/` | Connection status |
| GET | `/api/wallet/info/` | User wallet info |

### Corporate Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/corporate/dashboard/` | Corporate dashboard |
| POST | `/corporate/purchase/<id>/` | Purchase credits |
| GET | `/corporate/tenders/` | View tenders |
| POST | `/corporate/tenders/new/` | Create new tender |

### Mobile API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/mobile/login/` | Mobile authentication |
| GET | `/mobile/profile/` | User profile |
| GET/POST | `/mobile/projects/` | Project list/create |
| GET | `/mobile/projects/<id>/` | Project detail |

---

## Mobile Application

### Setup

```bash
cd mobile/flutter_ngo_app

# Get dependencies
flutter pub get

# Run on emulator/device
flutter run
```

### Configuration

Edit `lib/config.dart` for API endpoint:

```dart
// For Android emulator
const String API_BASE_EMULATOR = 'http://10.0.2.2:8000';

// For physical device (use your computer's IP)
const String API_BASE_DEVICE = 'http://192.168.x.x:8000';
```

### Features

- **Login Screen** - Token-based authentication
- **Dashboard** - Project overview with statistics
- **New Project** - Submit projects with image capture
- **Project Detail** - View status and credit information

### Screens

| Screen | File | Description |
|--------|------|-------------|
| Login | `login.dart` | Authentication |
| Dashboard | `dashboard.dart` | Main overview |
| New Project | `new_project.dart` | Project submission |
| Project Detail | `project_detail.dart` | Project information |

---

## Blockchain Integration

### How Credits Flow

```
1. NGO submits project
        |
        v
2. Field Officer verifies (ground truth)
        |
        v
3. ISRO Admin verifies (satellite data)
        |
        v
4. Admin reviews & approves
        |
        v
5. ML model predicts credits
        |
        v
6. Smart contract mints tokens to NGO wallet
        |
        v
7. Corporate purchases via marketplace
        |
        v
8. Smart contract transfers tokens
        |
        v
9. Transaction recorded on blockchain
```

### Credit Calculation

```python
# Biomass estimation from ML model
biomass_t_per_ha = model.predict(image_features)

# Carbon calculation
biomass_total = biomass_t_per_ha * area_hectares
carbon_tonnes = biomass_total * 0.5  # 50% carbon content
co2e_tonnes = carbon_tonnes * (44/12)  # CO2 equivalent
credits = co2e_tonnes  # 1 credit = 1 tonne CO2e
```

### Blockchain Service Layer

The `BlockchainService` class provides:

```python
# Register project on chain
BlockchainService.register_project_on_blockchain(project)

# Mint credits for approved project
BlockchainService.mint_credits_for_project(project)

# Transfer credits between users
BlockchainService.transfer_credits(from_user, to_user, amount, project_id)

# Get user balance
BlockchainService.get_user_balance(user)

# Check blockchain status
BlockchainService.get_blockchain_status()
```

---

## Development Guide

### Adding New Features

1. **Models** - Define in `api/models.py`
2. **Views** - Add to `api/views.py`
3. **URLs** - Register in `api/urls.py`
4. **Templates** - Create in `api/templates/api/`
5. **Forms** - Define in `api/forms.py`

### Running Tests

```bash
# Django tests
python manage.py test

# Smart contract tests
cd contracts
npm test
```

### Code Style

- Python: PEP 8
- JavaScript: ESLint
- Solidity: Solhint
- Flutter: Dart analyzer

### Database Migrations

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Show migration status
python manage.py showmigrations
```

---

## Security Considerations

### Production Deployment Checklist

- [ ] Set `DEBUG=False` in production
- [ ] Use strong, unique `SECRET_KEY`
- [ ] Configure `ALLOWED_HOSTS` properly
- [ ] Use HTTPS for all connections
- [ ] Store private keys in secure vault (not in `.env`)
- [ ] Enable CSRF protection
- [ ] Configure proper CORS settings
- [ ] Use environment variables for all secrets
- [ ] Regular security audits of smart contracts
- [ ] Database backups and encryption

### Blockchain Security

- Private keys should never be committed to version control
- Use hardware wallets for production deployments
- Smart contracts have been designed with OpenZeppelin security patterns
- Pausable contracts allow emergency stops
- Owner-only functions for critical operations

### Data Protection

- User passwords are hashed using Django's PBKDF2
- Wallet private keys are stored encrypted (optional)
- File uploads are validated and sanitized
- SQL injection protection via Django ORM

---

## Troubleshooting

### Common Issues

**Blockchain not connecting:**
```bash
# Ensure Hardhat is running
cd contracts
npx hardhat node

# Check if port 8545 is available
netstat -an | findstr 8545
```

**Contract deployment fails:**
```bash
# Recompile contracts
cd contracts
npm run compile

# Redeploy
npm run deploy:local
```

**Database connection error:**
```bash
# Verify DATABASE_URL in .env
# Check PostgreSQL service is running
# Test connection with psql
```

**Email not sending:**
```bash
# Verify SMTP settings in .env
# For Gmail, use App Password (not regular password)
# Check EMAIL_USE_TLS=True
```

**Mobile app can't connect:**
```bash
# Use correct IP for your network
# Ensure Django allows the host in ALLOWED_HOSTS
# Check firewall settings
```

### Logs

Application logs are stored in `logs/` directory. Enable debug logging in `settings.py`:

```python
LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'logs/debug.log',
        },
    },
    'loggers': {
        'api': {
            'handlers': ['file'],
            'level': 'DEBUG',
        },
    },
}
```

---

## Contributing

### How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/your-username/bluequant.git

# Add upstream remote
git remote add upstream https://github.com/original/bluequant.git

# Keep fork updated
git fetch upstream
git merge upstream/main
```

### Code Review Guidelines

- Follow existing code style
- Write meaningful commit messages
- Include tests for new features
- Update documentation as needed
- Ensure all tests pass before submitting PR

---

## Roadmap

### Upcoming Features

- [ ] Multi-language support (Hindi, Tamil, etc.)
- [ ] Advanced ML models for species detection
- [ ] Integration with more satellite data sources
- [ ] Mobile app for Field Officers
- [ ] Real-time project monitoring dashboard
- [ ] Carbon credit retirement tracking
- [ ] Integration with international carbon registries

---

## Acknowledgments

- **OpenZeppelin** - Smart contract security patterns
- **Hardhat** - Ethereum development environment
- **Django** - Web framework
- **Flutter** - Mobile framework

---

## License

This project is developed for Blue Carbon ecosystem monitoring and verification.

---

*Built for a sustainable future*
