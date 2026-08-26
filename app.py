import json
import os
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
    /* Main App Headers */
    h1, h2, h3 {
        color: #008080 !important;
    }
    
    /* Custom Styling for Streamlit Buttons */
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
    
    /* Sidebar styling tweak */
    [data-testid="stSidebar"] {
        background-color: #f0f7f7;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# --- Session State for Login Tracking ---
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False

# --- JSON Data Storage Handling ---
DATA_FILE = "appointments.json"


def load_data():
  if not os.path.exists(DATA_FILE):
    default_data = {
        "available_slots": [
            "09:00 AM",
            "10:00 AM",
            "11:00 AM",
            "02:00 PM",
            "03:00 PM",
            "04:00 PM",
        ],
        "booked_appointments": [],
    }
    save_data(default_data)
    return default_data

  with open(DATA_FILE, "r") as f:
    return json.load(f)


def save_data(data):
  with open(DATA_FILE, "w") as f:
    json.dump(data, f, indent=4)


data = load_data()

# ==========================================
# 1. LOGIN SCREEN VIEW
# ==========================================
if not st.session_state.logged_in:
  # Using columns to perfectly center everything on the login page
  col1, col2, col3 = st.columns([1, 2, 1])

  with col2:
    # Display the logo centered
    if os.path.exists("logo.png"):
      # Centering the image element using container alignment or standard render
      st.image("logo.png", width=200, use_container_width=False)
    else:
      st.warning("⚠️ 'logo.png' not found in folder.")

    st.title("Wait Wise Login")
    st.write("Please sign in to access the portal.")

    with st.form("login_form"):
      user_id = st.text_input("User ID")
      password = st.text_input("Password", type="password")
      login_submit = st.form_submit_button("Log In")

      if login_submit:
        # Secure check without exposing credentials in the error message
        if user_id == "1234" and password == "4321":
          st.session_state.logged_in = True
          st.success("Login Successful!")
          st.rerun()
        else:
          st.error("Invalid User ID or Password. Please try again.")

# ==========================================
# 2. MAIN DASHBOARD VIEW (AFTER LOGIN)
# ==========================================
else:
  # Display the logo at the top of the dashboard
  if os.path.exists("logo.png"):
    st.image("logo.png", width=200)

  st.title("Doctor Appointment Scheduler")
  st.write("Welcome to your **Wait Wise** dashboard. Manage your bookings below.")

  # Logout button inside the sidebar
  if st.sidebar.button("Log Out"):
    st.session_state.logged_in = False
    st.rerun()

  # Sidebar: Admin view of booked appointments made by this account
  st.sidebar.title("Dashboard Admin")
  st.sidebar.markdown("---")
  st.sidebar.write("### Booked Appointments")

  if data["booked_appointments"]:
    for idx, booking in enumerate(data["booked_appointments"], 1):
      st.sidebar.info(
          f"**{idx}. Patient:** {booking['name']}\n\n* **Slot:**"
          f" {booking['slot']}\n* **Date:** {booking['date']}"
      )
  else:
    st.sidebar.write("No appointments booked yet.")

  # Main Booking Form Section
  st.markdown("---")
  with st.form("appointment_form"):
    st.subheader("Book a New Consultation Slot")
    patient_name = st.text_input("Patient Name")
    appointment_date = st.date_input("Appointment Date")

    if data["available_slots"]:
      selected_slot = st.selectbox(
          "Choose an Available Time Slot", data["available_slots"]
      )
    else:
      selected_slot = None
      st.warning("All time slots are currently booked!")

    submit_booking = st.form_submit_button("Confirm Booking")

    if submit_booking:
      if not patient_name:
        st.error("Please provide the patient name.")
      elif not selected_slot:
        st.error("No slots available to book.")
      else:
        data["available_slots"].remove(selected_slot)
        data["booked_appointments"].append({
            "name": patient_name,
            "slot": selected_slot,
            "date": str(appointment_date),
        })
        save_data(data)
        st.success(
            f"Successfully booked slot for {patient_name} at {selected_slot} on"
            f" {appointment_date}!"
        )
        st.rerun()
