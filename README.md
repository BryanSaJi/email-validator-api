# Email Validator API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A robust and asynchronous API for email validation including format verification, TLD checking, MX records lookup, and optional SMTP validation.

##  Features

- **Format Validation**: Syntactic validation using Pydantic EmailStr
- **TLD Verification**: Checks that the domain has a valid Top-Level Domain
- **Domain Blacklist**: Configurable system to block specific domains
- **MX Records**: Verifies domain existence and mail servers
- **SMTP Validation**: Connects directly to mail server to verify mailbox existence
- **Role-Based Email Detection**: Identifies addresses like admin@, support@, etc.
- **Robust DNS**: Uses reliable public DNS servers (Cloudflare, Google, Quad9)
- **Asynchronous Architecture**: Designed for high performance

##  Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

## 🔧 Installation

1. **Clone the repository** (or download the files):

```bash
git clone [https://github.com/your-username/email-validator-api.git](https://github.com/BryanSaJi/email-validator-api.git)

```

2. **Create a virtual environment**:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:

```bash
pip install fastapi uvicorn pydantic[email] dnspython
```

##  Configuration

### Blacklist File

Create a `domain_blacklist.txt` file in the project root directory with the domains you want to block (one per line):

```text
tempmail.com
throwaway.email
guerrillamail.com
10minutemail.com
```

If the file doesn't exist, the API will work without blacklist restrictions.

### Configuration Variables

You can modify the following constants in the code according to your needs:

```python
BLACKLIST_FILE = "domain_blacklist.txt"  # Blacklist file path
VALID_TLDS = {".com", ".net", ".org", ...}  # Valid TLDs
```

##  Usage

### Start the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### Interactive Documentation

Once the server is started, access:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📡 Endpoints

### POST /validate

Validates a complete email address.

#### Request Body

```json
{
  "email": "user@example.com"
}
```

#### Query Parameters

- `smtp_check_enabled` (boolean, optional, default: `true`): Enables SMTP verification

#### Response

```json
{
  "is_valid_format": true,
  "domain_exists": true,
  "is_blacklisted": false,
  "smtp_check_status": "success",
  "is_role_based": false,
  "message": "Email 'user@example.com' is valid and the mailbox exists.",
  "mx_records": ["mx1.example.com", "mx2.example.com"]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `is_valid_format` | boolean | Indicates if the email format is valid |
| `domain_exists` | boolean | Indicates if the domain has MX records |
| `is_blacklisted` | boolean | Indicates if the domain is blacklisted |
| `smtp_check_status` | string | SMTP verification status: `success`, `refused`, `timeout`, `skipped`, `unknown` |
| `is_role_based` | boolean | Indicates if it's a role-based email (admin, support, etc.) |
| `message` | string | Descriptive message of the result |
| `mx_records` | array | List of domain MX servers |

##  Usage Examples

### cURL

```bash
# Full validation with SMTP
curl -X POST "http://localhost:8000/validate?smtp_check_enabled=true" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@gmail.com"}'

# Validation without SMTP (faster)
curl -X POST "http://localhost:8000/validate?smtp_check_enabled=false" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@gmail.com"}'
```

### Python

```python
import requests

url = "http://localhost:8000/validate"
payload = {"email": "user@example.com"}
params = {"smtp_check_enabled": True}

response = requests.post(url, json=payload, params=params)
print(response.json())
```

### JavaScript (Fetch)

```javascript
const response = await fetch('http://localhost:8000/validate?smtp_check_enabled=true', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ email: 'user@example.com' })
});

const data = await response.json();
console.log(data);
```

##  Project Structure

```
email-validator-api/
│
├── main.py                 # Main API code
├── domain_blacklist.txt    # Blocked domains file
├── requirements.txt        # Project dependencies
└── README.md              # This file
```

## 🔍 Validation Process

1. **Format Validation**: Pydantic verifies email syntax
2. **TLD Verification**: Checks that the domain has a valid TLD
3. **Blacklist**: Verifies if the domain is blocked
4. **MX Records**: DNS query to verify mail servers
5. **SMTP Verification** (optional): Connects to mail server to validate mailbox

##  Performance

- **Mode without SMTP**: ~100-300ms per validation
- **Mode with SMTP**: ~1-5 seconds per validation (depends on mail server)
- **Asynchronous architecture**: Allows handling multiple concurrent requests

##  Important Considerations

### SMTP Verification

- Some mail servers block SMTP verifications due to security policies
- Timeouts are normal and don't always indicate the email is invalid
- Gmail and other large providers often don't respond to SMTP verifications
- Recommended: use `smtp_check_enabled=false` for fast validations in production

### Limits and Rate Limiting

- Consider implementing rate limiting in production
- Some servers may block your IP for performing too many SMTP verifications
- Use rotating proxies if you need to validate large volumes

##  Security

- Doesn't store emails in logs
- Uses trusted public DNS servers
- Configured timeout to avoid hanging connections
- Robust error and exception handling

##  Development

### Development Dependencies

```bash
pip install pytest pytest-asyncio httpx
```

### Run Tests

```bash
pytest tests/
```

##  License

This project is under the MIT License. See the `LICENSE` file for more details.

##  Contributions



##  Contact

For questions, suggestions, or to report issues, open an issue in the repository.

##  Roadmap



---

**Version**: 3.2.0  
**Last Updated**: 2025