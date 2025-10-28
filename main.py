from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Any
import asyncio
import dns.resolver  # Robust DNS lookup library
import smtplib
import socket
import os

# --- 1. Configuration and Dependency Loading ---

def load_blacklist(file_path: str) -> set[str]:
    """Loads blacklisted domains from a text file, filtering out invalid entries."""
    if not os.path.exists(file_path):
        print(f"Warning: Blacklist file not found at: {file_path}")
        return set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return {line.strip().lower() for line in f if line.strip()}
    except Exception as e:
        print(f"Error loading blacklist: {e}")
        return set()

BLACKLIST_FILE = "domains_blacklist.txt"
BLACKLISTED_DOMAINS = load_blacklist(BLACKLIST_FILE)

# Defined list of valid TLDs for stricter format checking
VALID_TLDS = {".com", ".net", ".org", ".edu", ".gov", ".co", ".io", ".dev", ".info", ".biz", ".mx", ".es", ".app", ".xyz"}

# --- 2. API Initialization and Data Models ---

app = FastAPI(
    title="Email Validator API (V3.2 - Production Ready)",
    description="A robust and asynchronous API for email verification, including format, TLD, MX record, and optional SMTP validation. Includes workarounds for common DNS resolution failures.",
    version="3.2.0"
)

class EmailRequest(BaseModel):
    email: EmailStr

class ValidationResult(BaseModel):
    is_valid_format: bool
    domain_exists: bool
    is_blacklisted: bool
    smtp_check_status: str  # 'success', 'refused', 'timeout', 'skipped', 'unknown'
    is_role_based: bool
    message: str
    mx_records: Optional[List[str]] = None

# --- 3. Core Business Logic and Utilities ---

ROLE_BASED_USERS = {"admin", "info", "support", "sales", "contact", "webmaster", "postmaster", "abuse", "hostmaster"}

def is_role_based(email: str) -> bool:
    """Checks if the local part of the email is a common role-based address."""
    local_part = email.split("@")[0].lower().split("+")[0].replace(".", "") 
    return local_part in ROLE_BASED_USERS

def is_valid_tld(domain: str) -> bool:
    """Ensures the domain ends with a known TLD and has a name preceding it."""
    sorted_tlds = sorted(list(VALID_TLDS), key=len, reverse=True)

    for tld in sorted_tlds:
        if domain.endswith(tld):
            # Check if the TLD is not the entire domain (i.e., ensure something precedes it)
            tld_start_index = len(domain) - len(tld)
            if tld_start_index > 0:
                return True
    return False

async def get_mx_records(domain: str) -> Optional[List[str]]:
    """
    Asynchronously resolves MX records by executing the synchronous dnspython 
    resolver in a thread. Explicitly sets public nameservers to mitigate local network DNS issues (NXDOMAIN).
    """
    loop = asyncio.get_event_loop()
    
    def sync_mx_lookup():
        # Function executed in a separate thread
        try:
            # Force the use of reliable public DNS resolvers
            resolver = dns.resolver.Resolver()
            resolver.nameservers = ['1.1.1.1', '8.8.8.8', '9.9.9.9']
            
            # Resolve the MX query without a strict lifetime/timeout
            mx_answers = resolver.resolve(domain, 'MX') 
            
            # Process and order results by preference
            mx_records = [str(answer.exchange).rstrip('.') for answer in mx_answers]
            mx_records.sort(key=lambda x: [
                int(mx.preference) 
                for mx in mx_answers if str(mx.exchange).rstrip('.') == x
            ][0])
            return mx_records
        except dns.resolver.NXDOMAIN:
            return None  # Domain does not exist
        except dns.resolver.NoAnswer:
            return []    # Domain exists, but no MX records
        except Exception:
            # Catch all other network/DNS resolution errors
            return None 

    # Run the synchronous function in asyncio's thread pool
    return await loop.run_in_executor(None, sync_mx_lookup)

# --- FUNCIÓN check_smtp CORREGIDA ---

async def check_smtp(email: str, mx_records: List[str]) -> tuple[str, str]:
    """Attempts to connect to the highest priority MX server to verify mailbox existence."""
    
    mx_server = mx_records[0]
    loop = asyncio.get_event_loop()
    conn = None # Initialize conn outside try block for finally clause

    try:
        # 1. Conexión y Bloqueos de Red
        conn = smtplib.SMTP(timeout=4)
        # Execute the blocking connect call in the executor
        await loop.run_in_executor(None, conn.connect, mx_server, 25)
        
        # 2. Diálogo SMTP
        conn.helo('email-validator.example.com') 

        # MAIL FROM check
        code, _ = conn.mail('test@example.com')
        if code != 250:
            return 'refused', "Server refused MAIL FROM command."

        # RCPT TO check (core existence test)
        code, msg = conn.rcpt(email)
        
        if code == 250:
            return 'success', "The mail server confirmed the email address exists (Code 250)."
        elif code in (550, 553):
            return 'refused', "Mailbox does not exist (550/553) or server explicitly rejected the address."
        else:
            return 'refused', f"Server rejected the recipient with code {code}."

    except (socket.timeout, TimeoutError):
        return 'timeout', f"Connection to the mail server ({mx_server}) timed out."
    except smtplib.SMTPConnectError:
        return 'refused', f"Could not connect to the mail server ({mx_server}) on port 25."
    except (smtplib.SMTPServerDisconnected, ConnectionResetError, socket.error):
        return 'timeout', f"The mail server or network unexpectedly disconnected during validation. Status is uncertain."
    except Exception:
        return 'unknown', "An unexpected critical error occurred."
    finally:
        if conn:
            try:
                conn.quit() 
                conn.close()
            except Exception:
                pass
    

# --- 4. API Endpoints ---

@app.post("/validate", response_model=ValidationResult)
async def validate_email(
    request: EmailRequest,
    smtp_check_enabled: bool = Query(True, description="Enable SMTP verification (slower but provides mailbox existence guarantee)")
):
    """
    Performs full email validation against format, TLD, blacklist, MX records, and SMTP.
    """
    email = request.email
    domain = email.split("@")[-1].lower()

    # 1. Initialize Result (Format is guaranteed by Pydantic EmailStr)
    result = {
        "is_valid_format": True,
        "domain_exists": False,
        "is_blacklisted": False,
        "smtp_check_status": "skipped" if not smtp_check_enabled else "unknown",
        "is_role_based": is_role_based(email),
        "message": "",
        "mx_records": None
    }
    
    # 2. Blacklist Check
    if domain in BLACKLISTED_DOMAINS:
        result["is_blacklisted"] = True
        result["message"] = f"The domain '{domain}' is blacklisted and should not be used."
        return result

    # 3. Strict TLD Check (prevents malformed domains like 'example.com.com')
    if not is_valid_tld(domain):
        result["message"] = f"The domain '{domain}' does not appear to have a valid Top-Level Domain."
        return result

    # 4. MX Records Check (DNS existence)
    mx_records = await get_mx_records(domain)
    
    if mx_records is None:
        result["message"] = f"The domain '{domain}' does not exist (NXDOMAIN)."
        return result
    
    if mx_records:
        result["domain_exists"] = True
        result["mx_records"] = mx_records
    else:
        result["message"] = f"The domain '{domain}' exists, but no Mail Exchange (MX) records were found."
        return result

    # 5. SMTP Validation Check
    if smtp_check_enabled:
        smtp_status, smtp_message = await check_smtp(email, mx_records)
        
        result["smtp_check_status"] = smtp_status
        
        # Generate final message based on SMTP status
        if smtp_status == 'success':
            result["message"] = f"Email '{email}' is valid and the mailbox exists."
        elif smtp_status == 'refused':
            result["message"] = f"Domain exists, but the mail server explicitly rejected the address. It is likely invalid. Detail: {smtp_message}"
        elif smtp_status == 'timeout':
            result["message"] = f"Domain exists, but the mail server timed out. Mailbox existence is uncertain."
        else:
             result["message"] = f"Validation failed due to an unexpected server error. Detail: {smtp_message}"
    
    # Default message if SMTP check was skipped
    if not result["message"]:
        result["message"] = "Basic validation successful. Domain is valid, but mailbox existence was not verified (SMTP check skipped)."
        
        
    return result