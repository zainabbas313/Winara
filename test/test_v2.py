import requests
import json
from typing import Dict, List

# API endpoints
BASE_URL = "http://127.0.0.1:8000/api/v1"
LOGIN_URL = f"{BASE_URL}/auth/login"
BIDS_URL = f"{BASE_URL}/bids"
MEMBER_VERTICAL_URL = f"{BASE_URL}/members/{{member_id}}/verticals"  # Adjust based on actual API

# Admin credentials for assigning verticals
ADMIN_CREDENTIALS = {
    "email": "zain@winara.com",  # Update with actual admin credentials
    "password": "123qwe!@#QWE"
}

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

# Member to Vertical assignments based on their planned bids
MEMBER_VERTICAL_ASSIGNMENTS = {
    "3fdf817c-5361-42a3-8c74-693838b7c1d7": [  # David (Operations)
        "af4b8f95-940b-406c-84e9-a5c0a65bb47e",  # Technology
        "3fac2e80-d804-4b0a-a282-0aa7d82fdbb5"   # Education
    ],
    "efbe5455-0af0-40c3-80ea-d83162bacb98": [  # Emma (Operations)
        "fe3e5804-0a31-4717-bf29-43c0fae1c7f3",  # Machine Learning
        "b5f5d2d9-b7c7-4b18-ac1a-815f6e22f0cf"   # Retail
    ],
    "f0a4f587-897a-409b-bf2c-d427b5c873be": [  # Sophia (Support)
        "5b786f83-5664-4e9e-be57-2fc93d670221",  # Artificial Intelligence
        "13d35c90-b1f3-41c5-ba81-804208906909"   # Healthcare
    ],
    "970fd3d9-ed2c-4f81-9038-e85ec0fc8398": [  # Liam (Support)
        "c3c83ebf-74f2-40ee-bfe3-78cfb8b9aee5"   # Telemedicine
    ],
    "7e1f3656-b3a5-49d8-9051-5d7be9a95c31": [  # Olivia (Integration)
        "e2560d14-5479-432f-a94c-29f7975c1d55"   # E-Commerce
    ],
    "0adfaee8-c52f-4816-91fb-163793d77fb7": [  # Noah (Integration)
        "3273c456-53a6-46a0-a670-ddc5814e4b6f",  # Renewable Energy
        "5b786f83-5664-4e9e-be57-2fc93d670221"   # Artificial Intelligence
    ]
}

# Bid data with corrected vertical mappings
BIDS_DATA = [
    {
        "job_title": "Data Entry Automation",
        "job_url": "https://example.com/jobs/1",
        "job_description": "Automate repetitive data entry tasks using Python.",
        "client_name": "Acme Corp",
        "budget_type": "fixed",
        "budget_min": 200,
        "budget_max": 500,
        "hourly_rate": None,
        "estimated_hours": 0,
        "connects_used": 2,
        "boost_connects_used": 0,
        "proposal_text": "Strong experience in automation with Python and Pandas.",
        "cover_letter": "Can deliver within 3 days.",
        "is_featured": True,
        "competition_level": 2,
        "notes": "Quick turnaround job.",
        "vertical_id": "af4b8f95-940b-406c-84e9-a5c0a65bb47e",  # Technology
        "team_id": "b1077522-1bfc-4d6f-afbb-5f91aaae89f9",
        "member_id": "3fdf817c-5361-42a3-8c74-693838b7c1d7"
    },
    {
        "job_title": "Machine Learning Model Deployment",
        "job_url": "https://example.com/jobs/2",
        "job_description": "Deploy ML models to production using FastAPI and Docker.",
        "client_name": "ML Labs",
        "budget_type": "fixed",
        "budget_min": 1000,
        "budget_max": 2000,
        "hourly_rate": None,
        "estimated_hours": 0,
        "connects_used": 3,
        "boost_connects_used": 0,
        "proposal_text": "Experience in ML Ops and deployment pipelines.",
        "cover_letter": "Can provide scalable deployment.",
        "is_featured": False,
        "competition_level": 3,
        "notes": "Requires cloud setup.",
        "vertical_id": "fe3e5804-0a31-4717-bf29-43c0fae1c7f3",  # Machine Learning
        "team_id": "b1077522-1bfc-4d6f-afbb-5f91aaae89f9",
        "member_id": "efbe5455-0af0-40c3-80ea-d83162bacb98"
    },
    {
        "job_title": "Customer Support Automation",
        "job_url": "https://example.com/jobs/3",
        "job_description": "Implement chatbot for customer queries.",
        "client_name": "Retail Hub",
        "budget_type": "hourly",
        "budget_min": None,
        "budget_max": None,
        "hourly_rate": 20,
        "estimated_hours": 50,
        "connects_used": 2,
        "boost_connects_used": 5,
        "proposal_text": "Skilled in AI chatbots with Dialogflow.",
        "cover_letter": "I can integrate with CRM.",
        "is_featured": False,
        "competition_level": 4,
        "notes": "CRM integration required.",
        "vertical_id": "5b786f83-5664-4e9e-be57-2fc93d670221",  # Artificial Intelligence
        "team_id": "52c028b3-2f26-4313-bca3-0fdd490e9971",
        "member_id": "f0a4f587-897a-409b-bf2c-d427b5c873be"
    },
    {
        "job_title": "Healthcare Chatbot",
        "job_url": "https://example.com/jobs/4",
        "job_description": "Develop chatbot for patient appointment booking.",
        "client_name": "HealthFirst",
        "budget_type": "fixed",
        "budget_min": 800,
        "budget_max": 1500,
        "hourly_rate": None,
        "estimated_hours": 0,
        "connects_used": 4,
        "boost_connects_used": 0,
        "proposal_text": "Experience in healthcare domain.",
        "cover_letter": "Will ensure HIPAA compliance.",
        "is_featured": True,
        "competition_level": 5,
        "notes": "High sensitivity project.",
        "vertical_id": "c3c83ebf-74f2-40ee-bfe3-78cfb8b9aee5",  # Telemedicine
        "team_id": "52c028b3-2f26-4313-bca3-0fdd490e9971",
        "member_id": "970fd3d9-ed2c-4f81-9038-e85ec0fc8398"
    },
    {
        "job_title": "E-Commerce Integration",
        "job_url": "https://example.com/jobs/5",
        "job_description": "Integrate Shopify with third-party payment gateways.",
        "client_name": "ShopNow",
        "budget_type": "fixed",
        "budget_min": 500,
        "budget_max": 1200,
        "hourly_rate": None,
        "estimated_hours": 0,
        "connects_used": 2,
        "boost_connects_used": 0,
        "proposal_text": "Expert in Shopify APIs.",
        "cover_letter": "Will ensure smooth checkout process.",
        "is_featured": False,
        "competition_level": 3,
        "notes": "Requires testing.",
        "vertical_id": "e2560d14-5479-432f-a94c-29f7975c1d55",  # E-Commerce
        "team_id": "a92d705f-5d9a-4d51-bf55-1ae3e1d48e40",
        "member_id": "7e1f3656-b3a5-49d8-9051-5d7be9a95c31"
    },
    {
        "job_title": "Energy Dashboard",
        "job_url": "https://example.com/jobs/6",
        "job_description": "Build dashboard for energy consumption monitoring.",
        "client_name": "GreenEnergy",
        "budget_type": "fixed",
        "budget_min": 1500,
        "budget_max": 2500,
        "hourly_rate": None,
        "estimated_hours": 0,
        "connects_used": 3,
        "boost_connects_used": 10,
        "proposal_text": "Skilled in React + D3.js visualizations.",
        "cover_letter": "Will integrate live energy data APIs.",
        "is_featured": True,
        "competition_level": 4,
        "notes": "High complexity.",
        "vertical_id": "3273c456-53a6-46a0-a670-ddc5814e4b6f",  # Renewable Energy
        "team_id": "a92d705f-5d9a-4d51-bf55-1ae3e1d48e40",
        "member_id": "0adfaee8-c52f-4816-91fb-163793d77fb7"
    },
    {
        "job_title": "Education Platform Backend",
        "job_url": "https://example.com/jobs/7",
        "job_description": "Build FastAPI backend for LMS.",
        "client_name": "LearnHub",
        "budget_type": "hourly",
        "budget_min": None,
        "budget_max": None,
        "hourly_rate": 25,
        "estimated_hours": 100,
        "connects_used": 5,
        "boost_connects_used": 0,
        "proposal_text": "Backend expert with JWT auth experience.",
        "cover_letter": "Can scale to thousands of users.",
        "is_featured": False,
        "competition_level": 2,
        "notes": "Long-term project.",
        "vertical_id": "3fac2e80-d804-4b0a-a282-0aa7d82fdbb5",  # Education
        "team_id": "b1077522-1bfc-4d6f-afbb-5f91aaae89f9",
        "member_id": "3fdf817c-5361-42a3-8c74-693838b7c1d7"
    },
    {
        "job_title": "Retail Sales Forecasting",
        "job_url": "https://example.com/jobs/8",
        "job_description": "Build ML model to predict retail sales.",
        "client_name": "MarketPro",
        "budget_type": "fixed",
        "budget_min": 1200,
        "budget_max": 2500,
        "hourly_rate": None,
        "estimated_hours": 0,
        "connects_used": 2,
        "boost_connects_used": 0,
        "proposal_text": "Specialized in Time Series ML.",
        "cover_letter": "Will provide accurate forecasting.",
        "is_featured": True,
        "competition_level": 5,
        "notes": "High value project.",
        "vertical_id": "b5f5d2d9-b7c7-4b18-ac1a-815f6e22f0cf",  # Retail
        "team_id": "b1077522-1bfc-4d6f-afbb-5f91aaae89f9",
        "member_id": "efbe5455-0af0-40c3-80ea-d83162bacb98"
    },
    {
        "job_title": "Telemedicine App Support",
        "job_url": "https://example.com/jobs/9",
        "job_description": "Provide backend support for telemedicine app.",
        "client_name": "MediLink",
        "budget_type": "hourly",
        "budget_min": None,
        "budget_max": None,
        "hourly_rate": 30,
        "estimated_hours": 40,
        "connects_used": 3,
        "boost_connects_used": 0,
        "proposal_text": "Healthcare app support experience.",
        "cover_letter": "24/7 support available.",
        "is_featured": False,
        "competition_level": 3,
        "notes": "Ongoing support contract.",
        "vertical_id": "13d35c90-b1f3-41c5-ba81-804208906909",  # Healthcare
        "team_id": "52c028b3-2f26-4313-bca3-0fdd490e9971",
        "member_id": "f0a4f587-897a-409b-bf2c-d427b5c873be"
    },
    {
        "job_title": "AI Recommendation Engine",
        "job_url": "https://example.com/jobs/10",
        "job_description": "Develop AI-based recommendation system for e-commerce.",
        "client_name": "SmartShop",
        "budget_type": "fixed",
        "budget_min": 2000,
        "budget_max": 4000,
        "hourly_rate": None,
        "estimated_hours": 0,
        "connects_used": 6,
        "boost_connects_used": 20,
        "proposal_text": "Deep expertise in recommendation systems.",
        "cover_letter": "Ready to build scalable AI pipelines.",
        "is_featured": True,
        "competition_level": 5,
        "notes": "High performance system needed.",
        "vertical_id": "5b786f83-5664-4e9e-be57-2fc93d670221",  # Artificial Intelligence
        "team_id": "a92d705f-5d9a-4d51-bf55-1ae3e1d48e40",
        "member_id": "0adfaee8-c52f-4816-91fb-163793d77fb7"
    }
]

def login_user(email: str, password: str) -> Dict:
    """Login a user and return the authentication token and user info"""
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

def assign_member_to_verticals(member_id: str, vertical_ids: List[str], admin_token: str) -> bool:
    """Assign a member to multiple verticals using admin privileges"""
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }
    
    endpoint = f"{BASE_URL}/users/verticals"  # Correct endpoint without user_id in path
    
    assignment_data = {
        "user_id": member_id,  # user_id goes in request body
        "vertical_ids": vertical_ids,
        "is_active": True,
        "notes": "Automated assignment for bid creation"
    }
    
    try:
        response = requests.post(endpoint, json=assignment_data, headers=headers)
        response.raise_for_status()
        print(f"  ✅ Assigned to {len(vertical_ids)} verticals")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Assignment failed: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"     Error details: {e.response.text}")
        return False

def create_bid(bid_data: Dict, access_token: str) -> bool:
    """Create a bid using the authenticated session"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Remove member_id from bid data
    bid_payload = {k: v for k, v in bid_data.items() if k != 'member_id'}
    
    try:
        response = requests.post(BIDS_URL, json=bid_payload, headers=headers)
        response.raise_for_status()
        print(f"  ✅ Successfully created bid: '{bid_payload['job_title']}'")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Failed to create bid '{bid_payload['job_title']}': {e}")
        if hasattr(e, 'response') and e.response:
            print(f"     Error details: {e.response.text}")
        return False

def assign_all_verticals(admin_token: str) -> bool:
    """Assign all members to their required verticals"""
    print("\n" + "="*50)
    print("📋 ASSIGNING MEMBERS TO VERTICALS")
    print("="*50)
    
    success_count = 0
    total_members = len(MEMBER_VERTICAL_ASSIGNMENTS)
    
    for member_id, vertical_ids in MEMBER_VERTICAL_ASSIGNMENTS.items():
        member_email = MEMBER_CREDENTIALS.get(member_id, {}).get('email', 'Unknown')
        print(f"\n👤 Assigning verticals for {member_email}...")
        
        if assign_member_to_verticals(member_id, vertical_ids, admin_token):
            success_count += 1
    
    print(f"\n📊 Vertical Assignment Summary: {success_count}/{total_members} members assigned")
    return success_count == total_members

def main():
    """Main function to process vertical assignments and bid creation"""
    print("🚀 Starting automated bid creation process...")
    print(f"📊 Total bids to create: {len(BIDS_DATA)}")
    print(f"👥 Members to assign to verticals: {len(MEMBER_VERTICAL_ASSIGNMENTS)}")
    print("-" * 50)
    
    # Step 1: Login as admin to assign verticals
    print("\n🔐 Logging in as admin...")
    admin_auth = login_user(ADMIN_CREDENTIALS['email'], ADMIN_CREDENTIALS['password'])
    if not admin_auth:
        print("❌ Admin login failed. Cannot assign verticals.")
        print("Please update ADMIN_CREDENTIALS with correct admin login details.")
        return
    
    admin_token = admin_auth.get('access_token')
    print("✅ Admin login successful")
    
    # Step 2: Assign members to verticals
    if not assign_all_verticals(admin_token):
        print("⚠️  Some vertical assignments failed. Proceeding with bid creation anyway...")
    
    # Step 3: Create bids for each member
    print("\n" + "="*50)
    print("📝 CREATING BIDS")
    print("="*50)
    
    success_count = 0
    failed_count = 0
    
    # Group bids by member_id
    bids_by_member = {}
    for bid in BIDS_DATA:
        member_id = bid['member_id']
        if member_id not in bids_by_member:
            bids_by_member[member_id] = []
        bids_by_member[member_id].append(bid)
    
    # Process each member's bids
    for member_id, member_bids in bids_by_member.items():
        if member_id not in MEMBER_CREDENTIALS:
            print(f"⚠️  No credentials found for member {member_id}")
            failed_count += len(member_bids)
            continue
            
        credentials = MEMBER_CREDENTIALS[member_id]
        print(f"\n👤 Processing bids for {credentials['email']}...")
        
        # Login the member
        auth_response = login_user(credentials['email'], credentials['password'])
        if not auth_response:
            print(f"❌ Login failed for {credentials['email']}")
            failed_count += len(member_bids)
            continue
            
        access_token = auth_response.get('access_token')
        user_info = auth_response.get('user', {})
        print(f"✅ Login successful for {user_info.get('first_name', 'User')} {user_info.get('last_name', '')}")
        
        # Create all bids for this member
        for bid in member_bids:
            if create_bid(bid, access_token):
                success_count += 1
            else:
                failed_count += 1
    
    # Final Summary
    print("\n" + "="*50)
    print("📈 FINAL SUMMARY")
    print("="*50)
    print(f"✅ Successfully created: {success_count} bids")
    print(f"❌ Failed to create: {failed_count} bids")
    print(f"📊 Total processed: {success_count + failed_count} bids")
    
    if success_count == len(BIDS_DATA):
        print("🎉 All bids created successfully!")
    else:
        print("⚠️  Some bids failed to create. Check the logs above.")
        print("\n💡 If vertical assignment errors persist, you may need to:")
        print("   1. Manually assign members to verticals through your admin interface")
        print("   2. Update the member-vertical assignment API endpoint in this script")
        print("   3. Verify admin credentials and permissions")

if __name__ == "__main__":
    main()