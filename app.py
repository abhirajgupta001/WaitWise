import hashlib
import math
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from streamlit_geolocation import streamlit_geolocation
import firebase_admin
from firebase_admin import credentials, firestore

# --- Page Configuration ---
st.set_page_config(
    page_title="Wait Wise - Live Doctor Queue",
    page_icon="🩺",
    layout="centered",
)

# --- Automatic Real-Time Refresh (Every 5 Seconds) ---
st_autorefresh(interval=5000, limit=None, key="datarefresh")

# --- Warm Light Brown Theme & Custom Styling ---
st.markdown(
    """
    <style>
    /* Main App Background */
    .stApp {
        background-color: #F5F2EB;
    }
    h1, h2, h3 {
        color: #008080 !important;
    }
    .stButton>button {
        background-color: #008080 !important;
        color: white !important;
        border-radius: 5px;
        border: none;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #005959 !important;
        color: white !important;
    }
    [data-testid="stSidebar"] {
        background-color: #EBE5D8;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# --- Firebase Initialization ---
if not firebase_admin._apps:
  try:
    if "firebase" in st.secrets:
      cred_dict = dict(st.secrets["firebase"])
      cred = credentials.Certificate(cred_dict)
      firebase_admin.initialize_app(cred)
    else:
      cred = credentials.Certificate("serviceAccountKey.json")
      firebase_admin.initialize_app(cred)
  except Exception as e:
    st.error(f"Firebase initialization error: {e}")

db = firestore.client() if firebase_admin._apps else None

# --- Session State Tracking ---
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False
if "user_email" not in st.session_state:
  st.session_state.user_email = ""
if "user_role" not in st.session_state:
  st.session_state.user_role = ""

# Persistent sign-up field session states
if "signup_name" not in st.session_state:
  st.session_state["signup_name"] = ""
if "signup_email" not in st.session_state:
  st.session_state["signup_email"] = ""
if "signup_password" not in st.session_state:
  st.session_state["signup_password"] = ""
if "signup_phone" not in st.session_state:
  st.session_state["signup_phone"] = ""


# --- Firebase Data Loaders & Savers ---
def load_app_data():
  if not db:
    return {"slots_by_date": {}, "booked_appointments": [], "avg_consultation_time": 10}
  doc_ref = db.collection("app_data").document("main_config")
  doc = doc_ref.get()
  if doc.exists:
    return doc.to_dict()
  else:
    default_data = {"slots_by_date": {}, "booked_appointments": [], "avg_consultation_time": 10}
    doc_ref.set(default_data)
    return default_data


def save_app_data(data):
  if db:
    db.collection("app_data").document("main_config").set(data)


def load_users_db():
  if not db:
    return {}
  users_ref = db.collection("users")
  docs = users_ref.stream()
  users = {}
  for doc in docs:
    users[doc.id] = doc.to_dict()
  return users


def save_user_to_db(email, user_data):
  if db:
    db.collection("users").document(email).set(user_data)


app_data = load_app_data()
users_db = load_users_db()


def hash_password(text):
  return hashlib.sha256(text.encode()).hexdigest()


def is_valid_email(email):
  pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
  return re.match(pattern, email) is not None


# Helper: Haversine formula to compute travel time between coordinates
def calculate_travel_time(lat1, lon1, lat2, lon2):
  R = 6371.0
  dlat = math.radians(lat2 - lat1)
  dlon = math.radians(lon2 - lon1)
  a = (
      math.sin(dlat / 2) ** 2
      + math.cos(math.radians(lat1))
      * math.cos(math.radians(lat2))
      * math.sin(dlon / 2) ** 2
  )
  c = 2 * math.asin(math.sqrt(a))
  distance_km = R * c

  speed_kmh = 30.0
  travel_hours = distance_km / speed_kmh
  travel_minutes = int(travel_hours * 60)
  return max(5, travel_minutes)


# --- Email Notification Helper ---
def send_email_notification(to_email, patient_name, slot, date_str, travel_mins):
  sender_email = "waitwise09@gmail.com"
  sender_password = "yjzrumhvtteqekiy"

  try:
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = "Appointment Confirmation - Wait Wise"

    body = (
        f"Hello {patient_name},\n\nYour appointment has been successfully"
        f" booked!\n\n- Date: {date_str}\n- Time Slot: {slot}\n- Estimated"
        f" Travel Time to Clinic: {travel_mins} mins\n\nThank you for"
        f" using Wait Wise."
    )
    msg.attach(MIMEText(body, "plain"))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(sender_email, sender_password)
    server.sendmail(sender_email, to_email, msg.as_string())
    server.quit()
    return True
  except Exception as e:
    return False


# ==========================================
# 1. AUTHENTICATION SCREEN (LOGIN / SIGN UP)
# ==========================================
if not st.session_state.logged_in:
  col1, col2, col3 = st.columns([1, 2, 1])

  with col2:
    if os.path.exists("logo.png"):
      st.image("logo.png", width=200, use_container_width=False)

    st.title("Wait Wise Portal")

    auth_mode = st.radio("Choose action", ["Log In", "Sign Up"], horizontal=True)

    if auth_mode == "Log In":
      st.write("Sign in with your email and password.")
      with st.form("login_form"):
        login_role = st.selectbox("I am logging in as:", ["Patient", "Doctor"])
        email = st.text_input("Email Address")
        password = st.text_input("Password", type="password")

        doctor_login_code = ""
        if login_role == "Doctor":
          doctor_login_code = st.text_input(
              "Your Doctor Secret Code", type="password"
          )

        login_submit = st.form_submit_button("Log In")

        if login_submit:
          hashed_pw = hash_password(password)
          if email in users_db and users_db[email]["password"] == hashed_pw:
            if users_db[email]["role"] != login_role:
              st.error(
                  f"This account is registered as a"
                  f" {users_db[email]['role']}, not a {login_role}."
              )
            elif login_role == "Doctor":
              hashed_input_code = hash_password(doctor_login_code)
              if (
                  users_db[email].get("secret_code")
                  != hashed_input_code
              ):
                st.error("Incorrect Doctor Secret Code.")
              else:
                st.session_state.logged_in = True
                st.session_state.user_email = email
                st.session_state.user_role = "Doctor"
                st.success("Doctor Login Successful!")
                st.rerun()
            else:
              st.session_state.logged_in = True
              st.session_state.user_email = email
              st.session_state.user_role = "Patient"
              st.success("Patient Login Successful!")
              st.rerun()
          else:
            st.error("Invalid email or password. Please try again.")

    else:
      st.write("Create a new account.")

      full_name = st.text_input(
          "Full Name",
          value=st.session_state["signup_name"],
          key="input_full_name",
      )
      st.session_state["signup_name"] = full_name

      email = st.text_input(
          "Email Address",
          value=st.session_state["signup_email"],
          key="input_email",
      )
      st.session_state["signup_email"] = email

      password = st.text_input(
          "Create Password",
          type="password",
          value=st.session_state["signup_password"],
          key="input_password",
      )
      st.session_state["signup_password"] = password

      phone_number = st.text_input(
          "Phone Number",
          value=st.session_state["signup_phone"],
          key="input_phone",
      )
      st.session_state["signup_phone"] = phone_number

      role_selection = st.selectbox("Select Your Role", ["Patient", "Doctor"])

      patient_lat = None
      patient_lon = None
      custom_clinic_address = ""
      doc_lat = None
      doc_lon = None
      secret_code = ""
      specialty = "General Physician"
      experience_years = 5
      consultation_fee = 500

      if role_selection == "Patient":
        st.markdown("---")
        st.write("📍 **Browser Live Location (Compulsory)**")
        loc_data = streamlit_geolocation()

        if loc_data and loc_data.get("latitude") is not None:
          patient_lat = loc_data.get("latitude")
          patient_lon = loc_data.get("longitude")
          st.success(
              f"Live Location Captured! Lat: {patient_lat}, Lon: {patient_lon}"
          )
        else:
          st.warning(
              "Please click the button above and allow location access in your"
              " browser."
          )
      else:
        st.markdown("---")
        st.write("🏥 **Doctor Professional & Clinic Details**")

        specialty = st.text_input("Specialty (e.g. Cardiologist, Dentist, General Physician)", value="General Physician")
        experience_years = st.number_input("Years of Experience", min_value=1, max_value=50, value=5)
        consultation_fee = st.number_input("Consultation Fee (₹)", min_value=0, max_value=10000, value=500, step=50)

        custom_clinic_address = st.text_input(
            "Enter Clinic Name & Address (e.g., City Health Clinic, Main Bazaar)"
        )

        st.write("📍 **Clinic GPS Coordinates (Required for distance math):**")
        st.write(
            "You can copy these from Google Maps by dropping a pin on your"
            " clinic."
        )

        col_lat, col_lon = st.columns(2)
        with col_lat:
          doc_lat = st.number_input(
              "Clinic Latitude", format="%.6f", value=26.8467
          )
        with col_lon:
          doc_lon = st.number_input(
              "Clinic Longitude", format="%.6f", value=80.9462
          )

        secret_code = st.text_input(
            "Set Your Secret Code", type="password", key="input_secret_code"
        )

      if st.button("Complete Sign Up"):
        if not full_name or not email or not password or not phone_number:
          st.error("Please fill in all general profile fields.")
        elif not is_valid_email(email):
          st.error("Please enter a valid email address.")
        elif email in users_db:
          st.error("An account with this email already exists.")
        elif role_selection == "Patient" and (
            patient_lat is None or patient_lon is None
        ):
          st.error(
              "Live location permission is compulsory! Please fetch your live"
              " location before signing up."
          )
        elif role_selection == "Doctor" and (
            not custom_clinic_address
            or not secret_code
            or doc_lat is None
            or doc_lon is None
        ):
          st.error(
              "Please fill in your clinic address, coordinates, and secret code."
          )
        else:
          if role_selection == "Patient":
            new_user_data = {
                "full_name": full_name,
                "password": hash_password(password),
                "role": "Patient",
                "phone": phone_number,
                "lat": patient_lat,
                "lon": patient_lon,
            }
          else:
            new_user_data = {
                "full_name": full_name,
                "password": hash_password(password),
                "role": "Doctor",
                "phone": phone_number,
                "specialty": specialty,
                "experience": experience_years,
                "fee": consultation_fee,
                "clinic": custom_clinic_address,
                "lat": float(doc_lat),
                "lon": float(doc_lon),
                "secret_code": hash_password(secret_code),
            }

          save_user_to_db(email, new_user_data)
          st.success(
              f"Account created successfully as a {role_selection}! Please"
              " switch to Log In."
          )

# ==========================================
# 2. DASHBOARD VIEW
# ==========================================
else:
  if os.path.exists("logo.png"):
    st.image("logo.png", width=200)

  if st.sidebar.button("Log Out"):
    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.session_state.user_role = ""
    st.rerun()

  current_user_info = users_db.get(st.session_state.user_email, {})
  user_display_name = current_user_info.get("full_name", st.session_state.user_email)

  # ----------------------------------------
  # DOCTOR VIEW
  # ----------------------------------------
  if st.session_state.user_role == "Doctor":
    st.title("Doctor Live Schedule & Queue Management")
    st.write(f"Welcome Dr. **{user_display_name}**!")
    st.write(f"🩺 **Specialty:** {current_user_info.get('specialty', 'General')} | 💼 **Experience:** {current_user_info.get('experience', 0)} years | 💵 **Fee:** ₹{current_user_info.get('fee', 0)}")
    st.write(f"📞 **Phone:** {current_user_info.get('phone', 'N/A')}")
    st.write(f"🏥 **Clinic:** {current_user_info.get('clinic', 'N/A')}")
    st.write(f"📊 **Current Rolling Average Consultation Time:** ~{app_data.get('avg_consultation_time', 10)} mins/patient")

    st.markdown("---")
    st.subheader("Manage Slots by Date")
    doc_selected_date = st.date_input("Select Date to Manage")
    date_str = str(doc_selected_date)

    with st.form("add_slot_form"):
      st.write(f"Add Time Slot for **{date_str}**")
      new_slot = st.text_input("Enter Time Slot (e.g., 10:00 AM)")
      add_button = st.form_submit_button("Add Slot")

      if add_button:
        if new_slot:
          if "slots_by_date" not in app_data:
            app_data["slots_by_date"] = {}
          if date_str not in app_data["slots_by_date"]:
            app_data["slots_by_date"][date_str] = {}
          if st.session_state.user_email not in app_data["slots_by_date"][date_str]:
            app_data["slots_by_date"][date_str][st.session_state.user_email] = []

          if new_slot not in app_data["slots_by_date"][date_str][st.session_state.user_email]:
            app_data["slots_by_date"][date_str][st.session_state.user_email].append(new_slot)
            save_app_data(app_data)
            st.success(f"Added slot '{new_slot}' for {date_str} successfully!")
            st.rerun()
          else:
            st.error("This time slot already exists for this date.")
        else:
          st.error("Please enter a valid time slot.")

    st.markdown("---")
    st.subheader(f"Active Slots on {date_str}")
    current_date_slots = app_data.get("slots_by_date", {}).get(date_str, {}).get(st.session_state.user_email, [])

    if current_date_slots:
      for slot in list(current_date_slots):
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
          st.write(f"• {slot}")
        with col_s2:
          if st.button("Delete Slot", key=f"del_{date_str}_{slot}"):
            app_data["slots_by_date"][date_str][st.session_state.user_email].remove(slot)
            if not app_data["slots_by_date"][date_str][st.session_state.user_email]:
              del app_data["slots_by_date"][date_str][st.session_state.user_email]
            save_app_data(app_data)
            st.success(f"Removed slot '{slot}'")
            st.rerun()
    else:
      st.info(f"No slots configured for {date_str} yet.")

    st.markdown("---")
    st.subheader("🔴 Live Patient Queue Dashboard")
    date_bookings = [
        b for b in app_data["booked_appointments"] 
        if b["date"] == date_str and b.get("doctor_email") == st.session_state.user_email
    ]

    if date_bookings:
      for idx, booking in enumerate(date_bookings):
        st.write(f"### Patient {idx + 1}: {booking['name']}")
        duration_info = f" | ⏱️ **Duration:** {booking['duration_mins']} mins" if "duration_mins" in booking else ""
        st.write(
            f"🕒 **Slot:** {booking['slot']} | 📞 **Phone:**"
            f" {booking.get('phone', 'N/A')} | 🚗 **Est. Travel:**"
            f" {booking.get('travel_time_mins', 'N/A')} mins{duration_info}"
        )
        st.write(f"Current Status: **{booking.get('status', 'Waiting')}**")

        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
          if st.button("⏳ Set Waiting", key=f"wait_{date_str}_{idx}"):
            booking["status"] = "Waiting"
            save_app_data(app_data)
            st.rerun()
        with col_b2:
          if st.button("🩺 In Consultation", key=f"clinic_{date_str}_{idx}"):
            booking["status"] = "In Consultation"
            save_app_data(app_data)
            st.rerun()
        with col_b3:
          if st.button("✅ Over / Completed", key=f"over_{date_str}_{idx}"):
            booking["status"] = "Completed"
            
            actual_duration = st.number_input(
                f"Enter actual minutes taken for {booking['name']}:", 
                min_value=1, max_value=120, value=10, 
                key=f"dur_{date_str}_{idx}"
            )
            booking["duration_mins"] = actual_duration

            completed_bookings = [
                item for item in app_data["booked_appointments"] 
                if item.get("status") == "Completed" and "duration_mins" in item
            ]
            if completed_bookings:
                total_mins = sum(item["duration_mins"] for item in completed_bookings)
                app_data["avg_consultation_time"] = round(total_mins / len(completed_bookings))

            save_app_data(app_data)
            st.success(f"Marked completed! Recorded duration: {actual_duration} mins.")
            st.rerun()
        st.markdown("---")
    else:
      st.info(f"No patient bookings found for {date_str}.")

  # ----------------------------------------
  # PATIENT VIEW
  # ----------------------------------------
  else:
    st.title("Patient Appointment & Live Status Dashboard")
    st.write(f"Welcome, **{user_display_name}**!")

    st.subheader("🟢 Your Live Booking Status")
    user_bookings = [
        b
        for b in app_data["booked_appointments"]
        if b["booked_by"] == st.session_state.user_email
    ]

    if user_bookings:
      for b in user_bookings:
        status_color = "🟡"
        if b.get("status") == "In Consultation":
          status_color = "🔴"
        elif b.get("status") == "Completed":
          status_color = "🟢"

        date_str_b = b["date"]
        doc_email_b = b.get("doctor_email")
        all_date_bookings = [
            item for item in app_data["booked_appointments"] 
            if item["date"] == date_str_b and item.get("doctor_email") == doc_email_b
        ]
        
        patients_ahead = 0
        for patient in all_date_bookings:
            if patient["booked_by"] == b["booked_by"] and patient["slot"] == b["slot"]:
                break
            if patient.get("status") != "Completed":
                patients_ahead += 1

        dynamic_avg_time = app_data.get("avg_consultation_time", 10)
        estimated_queue_wait = patients_ahead * dynamic_avg_time
        total_estimated_time = estimated_queue_wait + b.get("travel_time_mins", 0)

        st.info(
            f"**Doctor:** {b.get('doctor_name', 'N/A')} ({b.get('doctor_specialty', 'General')})\n\n"
            f"* **Patient Name:** {b['name']}\n"
            f"* **Date:** {b['date']}\n"
            f"* **Slot:** {b['slot']}\n"
            f"* **Queue Position:** #{patients_ahead + 1} in line ({patients_ahead} patients ahead of you)\n"
            f"* **Clinic Rolling Average Speed:** ~{dynamic_avg_time} mins per patient\n"
            f"* **Estimated Travel Time:** {b.get('travel_time_mins')} minutes\n"
            f"* **Total Estimated Wait:** ~{total_estimated_time} minutes\n"
            f"* **Live Status:** {status_color} **{b.get('status', 'Waiting')}**"
        )
    else:
      st.write("You have no active appointments booked right now.")

    st.markdown("---")
    st.subheader("👨‍⚕️ Available Doctors Directory & Booking")

    doctors_list = {email: data for email, data in users_db.items() if data.get("role") == "Doctor"}

    if not doctors_list:
      st.warning("No doctors are currently registered in the system.")
    else:
      st.write("Browse available doctors below, review their expertise, fees, and clinic details, and select one to book:")
      
      doc_options = {f"Dr. {data['full_name']} — {data.get('specialty', 'General')} (Fee: ₹{data.get('fee', 0)}, Exp: {data.get('experience', 0)} yrs)": email for email, data in doctors_list.items()}
      
      selected_doc_label = st.selectbox("Select a Doctor", list(doc_options.keys()))
      selected_doc_email = doc_options[selected_doc_label]
      selected_doc_info = doctors_list[selected_doc_email]

      # Display selected doctor card details
      st.markdown(
          f"### Dr. {selected_doc_info['full_name']}\n"
          f"* **Specialty:** {selected_doc_info.get('specialty', 'General')}\n"
          f"* **Experience:** {selected_doc_info.get('experience', 0)} years\n"
          f"* **Consultation Fee:** ₹{selected_doc_info.get('fee', 0)}\n"
          f"* **Clinic:** {selected_doc_info.get('clinic', 'N/A')}\n"
          f"* **Phone:** {selected_doc_info.get('phone', 'N/A')}"
      )

      pat_selected_date = st.date_input("Select Preferred Appointment Date")
      pat_date_str = str(pat_selected_date)

      already_booked_for_date = any(
          b["date"] == pat_date_str and b["booked_by"] == st.session_state.user_email and b.get("doctor_email") == selected_doc_email
          for b in app_data["booked_appointments"]
      )

      if already_booked_for_date:
        st.success(
            f"✅ You already have an appointment booked with Dr. {selected_doc_info['full_name']} for {pat_date_str}."
        )
      else:
        patient_name = st.text_input("Patient Full Name")
        patient_phone = st.text_input(
            "Patient Phone Number", value=current_user_info.get("phone", "")
        )

        st.markdown("---")
        st.write("📍 **Live Trip Location Check:**")
        st.info(
            "Please click below to fetch your current device's live location for"
            " this trip calculation."
        )
        trip_loc = streamlit_geolocation()

        trip_lat = None
        trip_lon = None

        if trip_loc and trip_loc.get("latitude") is not None:
          trip_lat = trip_loc.get("latitude")
          trip_lon = trip_loc.get("longitude")
          st.success(
              f"Current Device Location Captured! Lat: {trip_lat}, Lon: {trip_lon}"
          )
        else:
          st.warning(
              "Click the geolocation button above to record your current"
              " position before booking."
          )

        available_slots_for_date = app_data.get("slots_by_date", {}).get(
            pat_date_str, {}
        ).get(selected_doc_email, [])

        if available_slots_for_date:
          selected_slot = st.selectbox(
              f"Available Time Slots for Dr. {selected_doc_info['full_name']} on {pat_date_str}",
              available_slots_for_date,
          )
        else:
          selected_slot = None
          st.warning(
              f"Dr. {selected_doc_info['full_name']} has not set any available time slots for {pat_date_str}."
          )

        if st.button("Confirm Booking"):
          if not patient_name or not patient_phone:
            st.error("Please provide both patient name and phone number.")
          elif trip_lat is None or trip_lon is None:
            st.error(
                "Live location is required to calculate travel time! Please fetch"
                " your location using the button above."
            )
          elif not selected_slot:
            st.error("No slot selected or available to book.")
          else:
            d_lat = selected_doc_info.get("lat", 0.0)
            d_lon = selected_doc_info.get("lon", 0.0)

            travel_mins = calculate_travel_time(
                trip_lat, trip_lon, d_lat, d_lon
            )

            app_data["slots_by_date"][pat_date_str][selected_doc_email].remove(selected_slot)
            if not app_data["slots_by_date"][pat_date_str][selected_doc_email]:
              del app_data["slots_by_date"][pat_date_str][selected_doc_email]
            if not app_data["slots_by_date"][pat_date_str]:
              del app_data["slots_by_date"][pat_date_str]

            app_data["booked_appointments"].append({
                "name": patient_name,
                "phone": patient_phone,
                "slot": selected_slot,
                "date": pat_date_str,
                "booked_by": st.session_state.user_email,
                "doctor_email": selected_doc_email,
                "doctor_name": selected_doc_info["full_name"],
                "doctor_specialty": selected_doc_info.get("specialty", "General"),
                "status": "Waiting",
                "travel_time_mins": travel_mins,
            })
            save_app_data(app_data)

            st.success(
                f"🎉 **Booking Confirmed!** Slot {selected_slot} with"
                f" Dr. {selected_doc_info['full_name']} on {pat_date_str} is successfully reserved. Estimated travel"
                f" time: {travel_mins} mins."
            )

            with st.spinner("Processing email notification..."):
              email_sent = send_email_notification(
                  st.session_state.user_email,
                  patient_name,
                  selected_slot,
                  pat_date_str,
                  travel_mins,
              )

            if email_sent:
              st.info("📧 Confirmation email sent to your inbox.")
            else:
              st.warning(
                  "📧 Email not sent (Make sure to configure your valid Gmail and"
                  " App Password in the send_email_notification function)."
              )

            st.balloons()
            st.rerun()