import requests
import json
from typing import Dict, List

# API endpoints
BASE_URL = "http://127.0.0.1:8000/api/v1"
LOGIN_URL = f"{BASE_URL}/auth/login"
BID_STATUS_URL = f"{BASE_URL}/bids/{{bid_id}}/status"

# Member credentials mapping
MEMBER_CREDENTIALS = {
    "3fdf817c-5361-42a3-8c74-693838b7c1d7": {
        "email": "member1_ops@example.com",
        "password": "Ops@1234"
    },
    "efbe5455-0af0-40c3-80ea-d83162bacb98": {
        "email": "member2_ops@example.com",
        "password": "Ops#5678"
    },
    "f0a4f587-897a-409b-bf2c-d427b5c873be": {
        "email": "member1_support@example.com",
        "password": "Supp@1234"
    },
    "970fd3d9-ed2c-4f81-9038-e85ec0fc8398": {
        "email": "member2_support@example.com",
        "password": "Supp#5678"
    },
    "7e1f3656-b3a5-49d8-9051-5d7be9a95c31": {
        "email": "member1_integration@example.com",
        "password": "Int@1234"
    },
    "0adfaee8-c52f-4816-91fb-163793d77fb7": {
        "email": "member2_integration@example.com",
        "password": "Int#5678"
    }
}

# Member bids mapping (from the API response)
MEMBER_BIDS = {
    "3fdf817c-5361-42a3-8c74-693838b7c1d7": [  # David Miller
        {
            "bid_id": "e1f152d7-860f-4a95-a7fb-fe4d7e34180e",
            "job_title": "Education Platform Backend"
        },
        {
            "bid_id": "f3fe9e6e-68e4-460e-a4a0-e47bcde35a64",
            "job_title": "Data Entry Automation"
        }
    ],
    "efbe5455-0af0-40c3-80ea-d83162bacb98": [  # Emma Brown
        {
            "bid_id": "d34b6622-649c-4a6a-89a2-b5c0d5908e31",
            "job_title": "Retail Sales Forecasting"
        },
        {
            "bid_id": "2cb4ae80-a6a8-4c43-84e4-f052fc6d5da3",
            "job_title": "Machine Learning Model Deployment"
        }
    ],
    "f0a4f587-897a-409b-bf2c-d427b5c873be": [  # Sophia Taylor
        {
            "bid_id": "9dcb2537-4af9-44c7-9441-df1d2610a6df",
            "job_title": "Telemedicine App Support"
        },
        {
            "bid_id": "3b62230e-4470-4c2d-8adc-6d68f78fb1b2",
            "job_title": "Customer Support Automation"
        }
    ],
    "970fd3d9-ed2c-4f81-9038-e85ec0fc8398": [  # Liam Wilson
        {
            "bid_id": "680a5bd6-6f48-4750-b1b0-c6861dd9b0db",
            "job_title": "Healthcare Chatbot"
        }
    ],
    "7e1f3656-b3a5-49d8-9051-5d7be9a95c31": [  # Olivia Anderson
        {
            "bid_id": "e2f0f7ac-6b03-42d3-92c9-77bc014f3302",
            "job_title": "E-Commerce Integration"
        }
    ],
    "0adfaee8-c52f-4816-91fb-163793d77fb7": [  # Noah Martinez
        {
            "bid_id": "7a9135f2-d779-43eb-87b3-5c12c4057eb0",
            "job_title": "Energy Dashboard"
        },
        {
            "bid_id": "82e120f6-cd61-47ef-9dc3-841e46a1629c",
            "job_title": "AI Recommendation Engine"
        }
    ]
}

def login_member(email: str, password: str) -> Dict:
    """Login a member and return the authentication token and user info"""
    login_data = {
        "email": email,
        "password": password
    }
    
    try:
        response = requests.post(LOGIN_URL, json=login_data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Login failed for {email}: {e}")
        return None

def update_bid_status(bid_id: str, access_token: str, job_title: str) -> bool:
    """Update bid status to 'won' using the authenticated session"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    endpoint = BID_STATUS_URL.format(bid_id=bid_id)
    
    # Status update payload
    status_data = {
        "status": "won"
    }
    
    try:
        response = requests.patch(endpoint, json=status_data, headers=headers)
        response.raise_for_status()
        print(f"  ✅ Updated '{job_title}' status to WON")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Failed to update '{job_title}' status: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"     Error details: {e.response.text}")
        return False

def main():
    """Main function to update all bid statuses to 'won'"""
    print("🏆 Starting bid status update process...")
    print(f"📊 Total members: {len(MEMBER_BIDS)}")
    total_bids = sum(len(bids) for bids in MEMBER_BIDS.values())
    print(f"📝 Total bids to update: {total_bids}")
    print("-" * 50)
    
    success_count = 0
    failed_count = 0
    
    # Process each member's bids
    for member_id, member_bids in MEMBER_BIDS.items():
        if member_id not in MEMBER_CREDENTIALS:
            print(f"⚠️  No credentials found for member {member_id}")
            failed_count += len(member_bids)
            continue
            
        credentials = MEMBER_CREDENTIALS[member_id]
        print(f"\n👤 Processing status updates for {credentials['email']}...")
        
        # Login the member
        auth_response = login_member(credentials['email'], credentials['password'])
        if not auth_response:
            print(f"❌ Login failed for {credentials['email']}")
            failed_count += len(member_bids)
            continue
            
        access_token = auth_response.get('access_token')
        user_info = auth_response.get('user', {})
        print(f"✅ Login successful for {user_info.get('first_name', 'User')} {user_info.get('last_name', '')}")
        
        # Update all bid statuses for this member
        for bid in member_bids:
            if update_bid_status(bid['bid_id'], access_token, bid['job_title']):
                success_count += 1
            else:
                failed_count += 1
    
    # Final Summary
    print("\n" + "="*50)
    print("🏆 BID STATUS UPDATE SUMMARY")
    print("="*50)
    print(f"✅ Successfully updated: {success_count} bids to WON")
    print(f"❌ Failed to update: {failed_count} bids")
    print(f"📊 Total processed: {success_count + failed_count} bids")
    
    if success_count == total_bids:
        print("🎉 All bid statuses updated to WON successfully!")
    else:
        print("⚠️  Some bid status updates failed. Check the logs above.")

if __name__ == "__main__":
    main()