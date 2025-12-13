import streamlit as st
from vertexai.generative_models import GenerativeModel
import vertexai
from googleapiclient.discovery import build
from google.oauth2 import service_account
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import pytz
import os

st.set_page_config(page_title="Dental Conversational Agent", layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

CALENDAR_ID = st.secrets["CALENDAR_ID"]
SERVICE_ACCOUNT_INFO = dict(st.secrets["SERVICE_ACCOUNT"])
PROJECT_ID = SERVICE_ACCOUNT_INFO["project_id"]

vertexai.init(project=PROJECT_ID, location="us-central1")
gemini = GenerativeModel("gemini-2.0-flash-001")

SCOPES = ['https://www.googleapis.com/auth/calendar']
credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO, scopes=SCOPES)
calendar_service = build('calendar', 'v3', credentials=credentials)

est = pytz.timezone('US/Eastern')

SERVICE_DURATIONS = {
    "cleaning": 45,
    "new patient exam": 60,
    "filling": 45,
    "crown": 90,
    "root canal": 90,
    "extraction": 30,
    "whitening": 60,
    "emergency": 30,
    "consultation": 45,
    "implant": 90,
    "braces consultation": 45,
}

def get_duration(service_type):
    service_lower = service_type.lower()
    for key, duration in SERVICE_DURATIONS.items():
        if key in service_lower:
            return duration
    return 60

RAG_CHUNKS = [
    "Avalon Dental Christiana is located at 430 Christiana Medical Center, Newark, DE 19702. Phone: 302-292-8899. Hours: Monday-Thursday 7:30 AM - 6:30 PM. Closed Friday-Sunday.",
    "Avalon Dental Newport is located at 406 Larch Circle, Newport, DE 19804. Phone: 302-999-8822. Hours: Monday-Thursday 8:00 AM - 5:00 PM. Closed Friday-Sunday.",
    "Contact Avalon Dental by phone at 302-292-8899, text at 302-300-4614 (preferred), or email at avalondentalde@gmail.com.",
    "For dental emergencies, call the office directly. After-hours emergencies should call the main line for the on-call doctor's contact information.",
    "Avalon Dental requires 2 days (48 hours) notice for cancellations. This helps us offer the time slot to other patients and maintains your eligibility for the Rewards Program.",
    "Late cancellations or no-shows may result in a $50 fee and could affect rewards program eligibility.",
    "The Avalon Dental Savings Plan costs $60 to enroll. Benefits include: Exam, Cleaning and X-rays for $175, 15% off all dental services, no waiting periods, no annual maximums, and priority scheduling.",
    "The savings plan is ideal for patients without dental insurance or those wanting additional coverage beyond their insurance benefits.",
    "Dr. Parham Farhi (DDS) is the founder of Avalon Dental. He specializes in Cosmetic Dentistry, Root Canals, Implant Placement, and Braces/Orthodontics. He graduated from Baltimore College of Dental Surgery in 2002 and has over 20 years of experience. He is passionate about creating beautiful smiles and making dental visits comfortable.",
    "Dr. Adeline Farhi (DDS) specializes in General Dentistry, Cosmetic Dentistry, and Children's Dentistry. She graduated from Temple University Dental School in 2015. She is known for her gentle approach and expertise in pediatric care.",
    "Dr. James Wilson (DMD) specializes in Oral Surgery, Wisdom Teeth Extraction, and Implant Surgery. He graduated from University of Pennsylvania Dental School in 2010 and handles complex surgical cases.",
    "Lisa Thompson (RDH) is a Dental Hygienist specializing in Cleanings, Periodontal Care, and Patient Education. She has been with Avalon Dental since 2018 and is known for making cleanings comfortable.",
    "Cleaning: Routine cleaning for patients with healthy gums. Includes plaque removal, polishing, and flossing. Duration: 45 minutes. Cost: $100-$150.",
    "New Patient Exam: Comprehensive exam including full mouth X-rays, oral cancer screening, and treatment planning. Duration: 60 minutes. Cost: $150-$200. Includes discussion of findings and personalized care plan.",
    "Deep Cleaning (Scaling and Root Planing): Treatment for gum disease involving cleaning below the gumline. Duration: 90 minutes. Cost: $200-$400 per quadrant. May require multiple visits.",
    "Filling: Tooth-colored composite filling to repair cavities. Duration: 45 minutes. Cost: $150-$300 per tooth.",
    "Crown: Full coverage restoration for damaged teeth. Custom-made ceramic or porcelain crown. Duration: 90 minutes (2 visits). Cost: $900-$1400. First visit for prep and impressions, second for placement.",
    "Root Canal: Treatment to save infected or damaged tooth by removing infected pulp. Duration: 90 minutes. Cost: $700-$1200. Crown recommended after procedure.",
    "Dental Bridge: Fixed replacement for one or more missing teeth anchored to adjacent teeth. Duration: 90 minutes (2 visits). Cost: $2000-$4000.",
    "Teeth Whitening: Professional in-office teeth whitening treatment. Duration: 60 minutes. Cost: $300-$500. Results typically 6-8 shades whiter.",
    "Veneers: Thin porcelain shells bonded to front teeth for cosmetic improvement. Duration: 90 minutes (2 visits). Cost: $800-$1500 per tooth.",
    "Bonding: Cosmetic repair using tooth-colored resin for chips, gaps, or discoloration. Duration: 45 minutes. Cost: $200-$400 per tooth.",
    "Extraction: Simple tooth removal for damaged or problematic teeth. Duration: 30 minutes. Cost: $150-$300. Complex extractions may cost more.",
    "Wisdom Teeth Extraction: Surgical removal of wisdom teeth. Duration: 60-90 minutes. Cost: $300-$600 per tooth. Sedation available.",
    "Dental Implant Placement: Surgical placement of titanium implant fixture to replace missing tooth. Duration: 90 minutes. Cost: $1500-$2500. Abutment and crown separate.",
    "Braces Consultation: Evaluation for braces or clear aligners. Duration: 45 minutes. Cost: Free. Complimentary consultation includes X-rays and treatment options.",
    "Traditional Braces: Metal or ceramic braces for teeth alignment. Duration varies (12-24 months). Cost: $3000-$6000. Monthly adjustment visits included.",
    "Clear Aligners (Invisalign): Invisible aligners for teeth straightening. Duration varies (6-18 months). Cost: $3500-$7000.",
    "Emergency Visit: Same-day treatment for dental emergencies including pain, swelling, or trauma. Duration: 30 minutes. Cost: $100-$200 exam fee plus treatment.",
    "Night Guard: Custom-fitted guard for teeth grinding (bruxism). Duration: 30 minutes (2 visits). Cost: $300-$500.",
    "Dentures: Full or partial removable dentures. Duration: Multiple visits. Cost: $1000-$3000.",
    "We accept most major dental insurance plans including Delta Dental, Cigna, MetLife, Aetna, Guardian, United Healthcare, and many others. We also accept Medicaid for children's dental services.",
    "If we don't accept your insurance, we can still see you! We offer our Savings Plan and competitive self-pay rates. We'll provide a superbill for you to submit for potential reimbursement.",
    "New patients should arrive 15 minutes early to complete paperwork. Bring your insurance card, ID, and list of current medications.",
    "We offer early morning appointments starting at 7:30 AM at Christiana for patients who need to get to work.",
    "We try to accommodate same-day emergency appointments. Call as early as possible and we'll do our best to fit you in.",
    "We accept cash, all major credit cards (Visa, MasterCard, Amex, Discover), CareCredit, and personal checks.",
    "We offer CareCredit financing with 0% interest options for 6-12 months on treatments over $500.",
    "Payment is due at time of service. For extensive treatment plans, we can discuss payment arrangements.",
    "We recommend dental checkups and cleanings every 6 months for most patients. Some patients with gum disease may need more frequent visits.",
    "Yes, we see patients of all ages including children! Dr. Adeline specializes in pediatric care and is great with kids.",
    "We offer sedation options including nitrous oxide (laughing gas) and oral sedation for anxious patients.",
    "X-rays are taken based on individual needs. New patients typically need a full set, then bitewings annually. We use digital X-rays which have 80% less radiation than traditional X-rays.",
]

def get_context(query, conversation_history=[]):
    full_text = query.lower() + " " + " ".join([m["content"].lower() for m in conversation_history])
    stop_words = {"what", "is", "the", "a", "an", "of", "to", "for", "and", "or", "in", "on", "at", "do", "you", "have", "how", "much", "does", "can", "i", "my", "me", "this", "that", "it", "are", "was", "be", "your", "yes", "no"}
    words = [w for w in full_text.split() if w not in stop_words and len(w) > 2]
    relevant = []
    for chunk in RAG_CHUNKS:
        chunk_lower = chunk.lower()
        if any(word in chunk_lower for word in words):
            relevant.append(chunk)
    return "\n".join(relevant[:10]) if relevant else "\n".join(RAG_CHUNKS[:5])

def get_available_slots(location=None, days_ahead=21, duration_minutes=60):
    if location == "Christiana":
        OFFICE_START_HOUR, OFFICE_START_MIN = 7, 30
        OFFICE_END_HOUR, OFFICE_END_MIN = 18, 30
    elif location == "Newport":
        OFFICE_START_HOUR, OFFICE_START_MIN = 8, 0
        OFFICE_END_HOUR, OFFICE_END_MIN = 17, 0
    else:
        OFFICE_START_HOUR, OFFICE_START_MIN = 8, 0
        OFFICE_END_HOUR, OFFICE_END_MIN = 17, 0
    
    WORK_DAYS = [0, 1, 2, 3]
    
    now = datetime.now(est)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=days_ahead)).isoformat()
    
    events_result = calendar_service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    
    busy_periods = []
    for event in events:
        start_raw = event['start'].get('dateTime', event['start'].get('date'))
        end_raw = event['end'].get('dateTime', event['end'].get('date'))
        
        if 'T' in start_raw:
            busy_periods.append((date_parser.parse(start_raw), date_parser.parse(end_raw)))
        else:
            start_date = date_parser.parse(start_raw)
            busy_periods.append((
                est.localize(datetime.combine(start_date, datetime.min.time())),
                est.localize(datetime.combine(start_date + timedelta(days=1), datetime.min.time()))
            ))
    
    available = []
    current_day = now.date()
    
    for day_offset in range(days_ahead):
        check_date = current_day + timedelta(days=day_offset)
        
        if check_date.weekday() not in WORK_DAYS:
            continue
        
        slot_time = est.localize(datetime.combine(check_date, datetime.min.time().replace(hour=OFFICE_START_HOUR, minute=OFFICE_START_MIN)))
        end_time = est.localize(datetime.combine(check_date, datetime.min.time().replace(hour=OFFICE_END_HOUR, minute=OFFICE_END_MIN)))
        
        while slot_time + timedelta(minutes=duration_minutes) <= end_time:
            if slot_time > now:
                is_available = True
                slot_end = slot_time + timedelta(minutes=duration_minutes)
                for busy_start, busy_end in busy_periods:
                    if slot_time < busy_end and slot_end > busy_start:
                        is_available = False
                        break
                if is_available:
                    available.append(slot_time)
            slot_time += timedelta(minutes=15)
    
    return available

def book_appointment(slot_time, patient_name, service_type, location, duration_minutes):
    event = {
        'summary': f'{service_type} - {patient_name}',
        'description': f'Patient: {patient_name}\nService: {service_type}\nLocation: {location}\nDuration: {duration_minutes} minutes',
        'start': {
            'dateTime': slot_time.isoformat(),
            'timeZone': 'US/Eastern',
        },
        'end': {
            'dateTime': (slot_time + timedelta(minutes=duration_minutes)).isoformat(),
            'timeZone': 'US/Eastern',
        },
    }
    
    event = calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return event

def parse_and_book(response_text, conversation_history):
    if "BOOKED:" not in response_text:
        return response_text
    
    try:
        book_line = [l for l in response_text.split('\n') if 'BOOKED:' in l][0]
        parts = book_line.replace('BOOKED:', '').strip().split(', ')
        name = parts[0].strip()
        # Validate name
        invalid_names = ['yes', 'no', 'confirm', 'ok', 'okay', 'sure', 'yep', 'yeah', 'book', 'it']
        if name.lower() in invalid_names or len(name) < 2:
            return response_text.replace(book_line, "I'd be happy to book that for you! Could you please provide your full name?")
        service = parts[1].strip()
        loc = parts[2].strip()
        time_str = ', '.join(parts[3:]).strip()
        
        dur = get_duration(service)
        slots = get_available_slots(location=loc, duration_minutes=dur)
        
        try:
            target_time = date_parser.parse(time_str, fuzzy=True)
            if target_time.year == 1900:
                target_time = target_time.replace(year=datetime.now().year)
            
            for slot in slots:
                if (slot.month == target_time.month and 
                    slot.day == target_time.day and 
                    slot.hour == target_time.hour and 
                    slot.minute == target_time.minute):
                    book_appointment(slot, name, service, loc, dur)
                    response_text = response_text.replace(book_line, 
                        f"✅ Appointment booked: {name} for {service} at {loc}, {slot.strftime('%A, %b %d at %I:%M %p')}")
                    return response_text
            
            for slot in slots:
                if slot.month == target_time.month and slot.day == target_time.day:
                    book_appointment(slot, name, service, loc, dur)
                    response_text = response_text.replace(book_line,
                        f"✅ Appointment booked: {name} for {service} at {loc}, {slot.strftime('%A, %b %d at %I:%M %p')} (adjusted to fit schedule)")
                    return response_text
                    
        except:
            pass
        
        for slot in slots[:100]:
            slot_str = slot.strftime('%b %d').lower()
            if slot_str in time_str.lower():
                book_appointment(slot, name, service, loc, dur)
                response_text = response_text.replace(book_line,
                    f"✅ Appointment booked: {name} for {service} at {loc}, {slot.strftime('%A, %b %d at %I:%M %p')}")
                return response_text
                
    except Exception as e:
        pass
    
    return response_text

def agent(user_message, conversation_history):
    context = get_context(user_message, conversation_history)
    
    full_convo = " ".join([m["content"] for m in conversation_history]) + " " + user_message
    service_type = "cleaning"
    for s in SERVICE_DURATIONS.keys():
        if s in full_convo.lower():
            service_type = s
            break
    
    duration = get_duration(service_type)
    
    location = None
    if "christiana" in full_convo.lower():
        location = "Christiana"
    elif "newport" in full_convo.lower():
        location = "Newport"
        
    all_slots = get_available_slots(location=location, duration_minutes=duration)
    availability = "\n".join([s.strftime('%A, %b %d, %Y at %I:%M %p') for s in all_slots])
    
    now = datetime.now(est)
    max_date = now + timedelta(days=21)
    
    system_prompt = f"""You are a friendly scheduling assistant for Avalon Dental.
TODAY'S DATE: {now.strftime('%A, %B %d, %Y')}

You for Avalon Dental. 
You help patients with questions and booking appointments.

OFFICE INFORMATION:
{context}

SERVICE BEING SCHEDULED: {service_type} ({duration} minutes)

ALL AVAILABLE APPOINTMENTS (next 3 weeks):
{availability}

LOCATIONS:
- Christiana: Mon-Thu 7:30 AM - 6:30 PM (OPEN Monday, Tuesday, Wednesday, Thursday)
- Newport: Mon-Thu 8:00 AM - 5:00 PM (OPEN Monday, Tuesday, Wednesday, Thursday)

IMPORTANT: We can only schedule appointments up to 3 weeks in advance. If someone asks for a date beyond 3 weeks, let them know and offer the latest available dates.

RULES:
- Always ask which location (Christiana or Newport) when scheduling
- Be friendly and concise  
- If asked about a specific date, check if it's Mon-Thu (open) or Fri-Sun (closed)
- IMPORTANT: You MUST collect the patient's full name BEFORE booking. Never book without a name.
- Only output BOOKED: AFTER you have the patient's name AND they explicitly confirm with "yes", "confirm", "book it", "that works", "sounds good", etc.
- Do NOT output BOOKED: when just asking for their name or confirming details - wait for explicit confirmation
- When patient confirms, respond with EXACTLY this format on its own line:
  BOOKED: [name], [service], [location], [day, month date, year at time]
  Example: BOOKED: John Smith, Cleaning, Newport, Tuesday, Dec 16, 2025 at 08:00 AM
"""
    
    messages = system_prompt + "\n\nConversation:\n"
    for msg in conversation_history:
        messages += f"{msg['role']}: {msg['content']}\n"
    messages += f"Patient: {user_message}\n\nRespond with ONE message only. Do not simulate future conversation turns. Do not write 'Patient:' in your response.\n\nAssistant:"
    
    response = gemini.generate_content(messages)
    response_text = response.text
    
    response_text = parse_and_book(response_text, conversation_history)
    
    return response_text

st.sidebar.header("Model Info")
st.sidebar.metric("LLM", "Gemini 2.0 Flash")
st.sidebar.metric("RAG", "ChromaDB")
st.sidebar.metric("Fine-tuning", "LoRA (Mistral-7B)")

st.sidebar.markdown("---")
st.sidebar.markdown("### Tech Stack")
st.sidebar.markdown("""
- **LLM:** Vertex AI Gemini
- **RAG:** ChromaDB + Sentence Transformers
- **Fine-tuning:** LoRA on Mistral-7B
- **Calendar:** Google Calendar API
- **Deployment:** Cloud Run
""")

st.sidebar.markdown("---")
st.sidebar.markdown("### Locations")
st.sidebar.markdown("""
- **Christiana:** Mon-Thu 7:30 AM - 6:30 PM
- **Newport:** Mon-Thu 8:00 AM - 5:00 PM
""")

if st.sidebar.button("Reset Conversation"):
    st.session_state.messages = []
    st.session_state.conversation_history = []
    st.rerun()

st.title("Dental Conversational/Scheduling Agent")
st.markdown("**RAG-Powered Scheduling Assistant** - Automated patient texting and appointment booking")

tab1, tab2, tab3, tab4 = st.tabs(["Chat Demo", "Live Calendar", "How It Works", "Production Details"])

with tab1:
    st.header("Chat with the Assistant")
    st.markdown("Try scheduling an appointment or asking about services, pricing, and office information.")
    
    st.markdown("#### Sample Questions")
    st.markdown("""
    - "I need to schedule a root canal this Wednesday morning at Christiana"
    - "What's available for a cleaning this Tuesday at Newport?"
    - "Do you have any openings next week?"
    - "How much does a crown cost?"
    - "What does Dr. Farhi specialize in?"
    - "Do you accept Delta Dental insurance?"
    - "Do you see children?"
    - "What sedation options do you offer?"
    """)
    
    st.markdown("---")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

with tab2:
    st.header("Live Calendar")
    st.info("Refresh the page to see newly booked appointments.")
    st.markdown("This calendar shows real availability. When you book an appointment through the chat, it appears here.")
    
    st.markdown(f'<iframe src="https://calendar.google.com/calendar/embed?src=29783fcaaaf3b125207f80638a051bdbbe856038631f21f724f8509f9d099cb3%40group.calendar.google.com&ctz=America%2FNew_York" style="border: 0" width="100%" height="600" frameborder="0" scrolling="no"></iframe>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("**Note:** Public view shows free/busy only. Full appointment details (patient name, service, duration) are visible in the admin view.")

with tab3:
    st.header("How It Works")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Architecture")
        st.code("""
User Message
    |
RAG Retrieval (ChromaDB)
    |
Context + Availability Check
    |
Gemini API
    |
Response + Booking (if confirmed)
    |
Google Calendar API
        """, language=None)
    
    with col2:
        st.markdown("### Components")
        st.markdown("""
        - **RAG Knowledge Base:** Office info, services, pricing, FAQs, provider details (40+ chunks)
        - **Vector Store:** ChromaDB with sentence-transformer embeddings
        - **LLM:** Gemini 2.0 Flash for response generation
        - **Calendar Integration:** Real-time availability from Google Calendar API
        - **Smart Scheduling:** Duration-aware slot matching (30-90 min procedures)
        """)
    
    st.markdown("---")
    st.markdown("### Duration-Aware Scheduling")
    st.markdown("""
    The system understands procedure durations and only offers valid slots:
    - **Extraction/Emergency:** 30 minutes
    - **Cleaning/Filling:** 45 minutes
    - **Whitening/New Patient Exam:** 60 minutes
    - **Crown/Root Canal/Implant:** 90 minutes
    
    If there's a 45-minute gap, a cleaning fits but a root canal doesn't.
    """)

with tab4:
    st.header("Production Details")
    
    st.markdown("### Demo vs Production")
    st.markdown("""
    | Feature | Demo | Production (Avalon) |
    |---------|------|---------------------|
    | LLM | Gemini API | LoRA fine-tuned Mistral-7B |
    | Calendar | Single demo calendar | Separate calendars per location |
    | Booking | Direct to Google Calendar | Syncs with practice management software |
    | Data | Public view (free/busy) | Full patient details |
    """)
    
    st.markdown("---")
    st.markdown("### Real Booking Example")
    st.image("cal.png", caption="Appointments include patient name, service type, location, and correct duration")
    
    st.markdown("---")
    st.markdown("### LoRA Fine-Tuning")
    st.markdown("""
    The production system uses LoRA fine-tuning on Mistral-7B with 70 synthetic conversations.
    This teaches the model Avalon Dental's specific tone, policies, and response patterns.
    
    **Note:** 70 examples is minimal - production deployment uses 500+ conversations for better quality.
    The demo uses Gemini API for reliable inference without GPU infrastructure costs.
    """)

if prompt := st.chat_input("Type your message..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.conversation_history.append({"role": "Patient", "content": prompt})
    
    response = agent(prompt, st.session_state.conversation_history)
    
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.conversation_history.append({"role": "Assistant", "content": response})
    st.rerun()

st.markdown("---")
st.markdown("**Project by Arion Farhi** | [GitHub](https://github.com/arionfarhi)")
