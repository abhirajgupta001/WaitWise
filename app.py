import hashlib
import json
import os
import re
import streamlit as st

# --- Page Configuration ---
st.set_page_config(
    page_title="Wait Wise - Doctor Appointment",
    page_icon="🩺",
    layout="centered",
)

# --- Teal Theme & Custom Styling ---
st.markdown(
    """
    <style>
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
        background-color: #f0f7f7;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# --- Session State Tracking ---
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False
if "user_email" not in st.session_state:
  st.session_state.user_email = ""
if "user_role" not in st.session_state:
  st.session_state.user_role = ""

# --- Data Storage Setup ---
DATA_FILE = "appointments.json"
USERS_FILE = "users.json"


def load_json(filename, default_structure):
  if not os.path.exists(filename):
    save_json(filename, default_structure)
    return default_structure
  with open(filename, "r") as f:
    return json.load(f)


def save_json(filename, data):
  with open(filename, "w") as f:
    json.dump(data, f, indent=4)


# Load data (Using slots_by_date dictionary structure)
app_data = load_json(
    DATA_FILE,
    {
        "slots_by_date": {},
        "booked_appointments": [],
    },
)
users_db = load_json(USERS_FILE, {})


def hash_password(text):
  return hashlib.sha256(text.encode()).hexdigest()


def is_valid_email(email):
  pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
  return re.match(pattern, email) is not None


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
      with st.form("signup_form"):
        full_name = st.text_input("Full Name")
        email = st.text_input("Email Address")
        password = st.text_input("Create Password", type="password")
        role_selection = st.selectbox(
            "Select Your Role", ["Patient", "Doctor"]
        )

        phone_number = ""
        clinic_address = ""
        secret_code = ""

        if role_selection == "Doctor":
          phone_number = st.text_input("Phone Number")
          clinic_address = st.text_input("Clinic Address")
          secret_code = st.text_input(
              "Set Your Personal Secret Code (For Future Logins)",
              type="password",
          )

        signup_submit = st.form_submit_button("Sign Up")

        if signup_submit:
          if not full_name or not email or not password:
            st.error("Please fill in all required fields.")
          elif not is_valid_email(email):
            st.error(
                "Please enter a valid email address (e.g., name@gmail.com)."
            )
          elif email in users_db:
            st.error(
                "An account with this email already exists. Please log in."
            )
          elif role_selection == "Doctor" and (
              not phone_number or not clinic_address or not secret_code
          ):
            st.error(
                "Doctors must provide a phone number, clinic address, and a"
                " secret code."
            )
          else:
            users_db[email] = {
                "full_name": full_name,
                "password": hash_password(password),
                "role": role_selection,
                "phone": phone_number,
                "clinic": clinic_address,
                "secret_code": hash_password(secret_code)
                if role_selection == "Doctor"
                else "",
            }
            save_json(USERS_FILE, users_db)
            st.success(
                f"Account created successfully as a {role_selection}! Please"
                " switch to Log In."
            )

# ==========================================
# 2. DASHBOARD VIEW (DIFFERENT FOR DOCTOR VS PATIENT)
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
    st.title("Doctor Schedule Management")
    st.write(f"Welcome Dr. **{user_display_name}**!")
    st.write(f"📞 **Phone:** {current_user_info.get('phone', 'N/A')}")
    st.write(f"🏥 **Clinic:** {current_user_info.get('clinic', 'N/A')}")

    st.markdown("---")
    st.subheader("Manage Schedule by Date")

    # Calendar Date Picker for Doctor
    doc_selected_date = st.date_input("Select Date to Manage Slots")
    date_str = str(doc_selected_date)

    # Add slot form for the selected date
    with st.form("add_slot_form"):
      st.write(f"Add Time Slot for **{date_str}**")
      new_slot = st.text_input("Enter Time Slot (e.g., 10:00 AM)")
      add_button = st.form_submit_button("Add Slot")

      if add_button:
        if new_slot:
          if "slots_by_date" not in app_data:
            app_data["slots_by_date"] = {}
          if date_str not in app_data["slots_by_date"]:
            app_data["slots_by_date"][date_str] = []

          if new_slot not in app_data["slots_by_date"][date_str]:
            app_data["slots_by_date"][date_str].append(new_slot)
            save_json(DATA_FILE, app_data)
            st.success(f"Added slot '{new_slot}' for {date_str} successfully!")
            st.rerun()
          else:
            st.error("This time slot already exists for this date.")
        else:
          st.error("Please enter a valid time slot.")

    st.markdown("---")
    st.subheader(f"Active Slots on {date_str}")
    current_date_slots = app_data.get("slots_by_date", {}).get(date_str, [])

    if current_date_slots:
      for slot in list(current_date_slots):
        col_slot, col_btn = st.columns([3, 1])
        with col_slot:
          st.write(f"• {slot}")
        with col_btn:
          if st.button("Delete", key=f"del_{date_str}_{slot}"):
            app_data["slots_by_date"][date_str].remove(slot)
            if not app_data["slots_by_date"][date_str]:
              del app_data["slots_by_date"][date_str]
            save_json(DATA_FILE, app_data)
            st.success(f"Removed slot '{slot}'")
            st.rerun()
    else:
      st.info(f"No slots configured for {date_str} yet.")

    st.sidebar.title("Doctor Admin")
    st.sidebar.markdown("---")
    st.sidebar.write("### Patient Bookings")
    if app_data["booked_appointments"]:
      for idx, booking in enumerate(app_data["booked_appointments"], 1):
        st.sidebar.info(
            f"**{idx}. Patient:** {booking['name']}\n\n* **Date:**"
            f" {booking['date']}\n* **Slot:** {booking['slot']}\n* **Booked"
            f" By:** {booking['booked_by']}"
        )
    else:
      st.sidebar.write("No appointments booked yet.")

  # ----------------------------------------
  # PATIENT VIEW
  # ----------------------------------------
  else:
    st.title("Patient Appointment Booking")
    st.write(f"Welcome, **{user_display_name}**!")

    st.sidebar.title("Your Information")
    st.sidebar.markdown("---")
    st.sidebar.write(
        "Select a date from the calendar to view available slots set by the"
        " doctor."
    )

    with st.form("appointment_form"):
      st.subheader("Book a Consultation Slot")
      patient_name = st.text_input("Patient Full Name")

      # Calendar Date Picker for Patient
      pat_selected_date = st.date_input("Select Preferred Appointment Date")
      pat_date_str = str(pat_selected_date)

      available_slots_for_date = (
          app_data.get("slots_by_date", {}).get(pat_date_str, [])
      )

      if available_slots_for_date:
        selected_slot = st.selectbox(
            f"Available Time Slots for {pat_date_str}",
            available_slots_for_date,
        )
      else:
        selected_slot = None
        st.warning(
            f"The doctor has not set any available time slots for"
            f" {pat_date_str}. Please choose another date!"
        )

      submit_booking = st.form_submit_button("Confirm Booking")

      if submit_booking:
        if not patient_name:
          st.error("Please provide the patient name.")
        elif not selected_slot:
          st.error("No slot selected or available to book.")
        else:
          # Remove booked slot from that date's list
          app_data["slots_by_date"][pat_date_str].remove(selected_slot)
          if not app_data["slots_by_date"][pat_date_str]:
            del app_data["slots_by_date"][pat_date_str]

          app_data["booked_appointments"].append({
              "name": patient_name,
              "slot": selected_slot,
              "date": pat_date_str,
              "booked_by": st.session_state.user_email,
          })
          save_json(DATA_FILE, app_data)
          st.success(
              f"Successfully booked slot for {patient_name} at {selected_slot} on"
              f" {pat_date_str}!"
          )
          st.rerun()
