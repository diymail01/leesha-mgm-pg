import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from io import BytesIO
from fpdf import FPDF

DB_NAME = "pg_management.db"

def create_tables():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT UNIQUE NOT NULL,
            floor INTEGER NOT NULL,
            capacity INTEGER NOT NULL,
            current_occupants INTEGER DEFAULT 0,
            monthly_rent INTEGER NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            room_id INTEGER,
            rent_status TEXT DEFAULT 'Not Paid',
            mode_of_payment TEXT,
            monthly_rent INTEGER,
            security_deposit INTEGER,
            joined_date DATE DEFAULT CURRENT_DATE,
            left_date DATE,
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )
    ''')
    conn.commit()
    conn.close()

def add_room(room_number, floor, capacity, rent):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO rooms (room_number, floor, capacity, monthly_rent) VALUES (?, ?, ?, ?)",
                       (room_number, floor, capacity, rent))
        conn.commit()
        st.success("Room added successfully.")
    except sqlite3.IntegrityError:
        st.error("Room number must be unique.")
    finally:
        conn.close()

def add_student(name, address, phone_number, room_id, rent, deposit):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT capacity, current_occupants FROM rooms WHERE id=?", (room_id,))
    room = cursor.fetchone()
    if room and room[1] < room[0]:
        cursor.execute('''
            INSERT INTO students (name, address, phone_number, room_id, monthly_rent, security_deposit)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, address, phone_number, room_id, rent, deposit))
        cursor.execute("UPDATE rooms SET current_occupants = current_occupants + 1 WHERE id=?", (room_id,))
        conn.commit()
        st.success("Student added successfully.")
    else:
        st.error("Room is already full.")
    conn.close()

def get_available_rooms():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, room_number FROM rooms WHERE capacity > current_occupants")
    rooms = cursor.fetchall()
    conn.close()
    return rooms

def update_rent_status(student_id, rent_status, payment_mode):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE students SET rent_status=?, mode_of_payment=? WHERE student_id=?",
                   (rent_status, payment_mode, student_id))
    conn.commit()
    conn.close()

def mark_student_left(student_id, left_date):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE students SET left_date=? WHERE student_id=?", (left_date, student_id))
    cursor.execute("UPDATE rooms SET current_occupants = current_occupants - 1 WHERE id = (SELECT room_id FROM students WHERE student_id=?)", (student_id,))
    conn.commit()
    conn.close()

def export_to_pdf(df, title):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, title, ln=True, align='C')
    pdf.set_font("Arial", size=10)
    col_width = 190 / len(df.columns)
    
    pdf.ln(5)
    for col in df.columns:
        pdf.cell(col_width, 10, col, border=1)
    pdf.ln()
    for _, row in df.iterrows():
        for item in row:
            pdf.cell(col_width, 10, str(item), border=1)
        pdf.ln()
    
    buffer = BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()

st.set_page_config(page_title="Royal Homes PG", layout="wide")
st.title("🏠 Royal Homes PG Management System")
create_tables()

menu = st.sidebar.radio("Navigation", ["Home", "Add Room", "Add Student", "View Rooms", "View Students", "Update Rent Status", "Student Exit"])

if menu == "Home":
    st.markdown("""
    ## Welcome to Royal Homes PG Management
    Use the sidebar to manage rooms, students, and rent status.
    """)

elif menu == "Add Room":
    st.subheader("Add New Room")
    room_number = st.text_input("Room Number")
    floor = st.number_input("Floor", min_value=0)
    capacity = st.number_input("Capacity", min_value=1)
    rent = st.number_input("Monthly Rent", min_value=0)
    if st.button("Add Room"):
        if room_number:
            add_room(room_number, floor, capacity, rent)
        else:
            st.error("Room number cannot be empty.")

elif menu == "Add Student":
    st.subheader("Add New Student")
    name = st.text_input("Student Name")
    address = st.text_input("Address")
    phone = st.text_input("Phone Number")
    rent = st.number_input("Monthly Rent", min_value=0)
    deposit = st.number_input("Security Deposit", min_value=0)
    rooms = get_available_rooms()
    room_dict = {f"Room {r[1]} (ID {r[0]})": r[0] for r in rooms}
    selected_room = st.selectbox("Available Rooms", list(room_dict.keys())) if rooms else None

    if st.button("Add Student"):
        if name and address and phone and selected_room:
            add_student(name, address, phone, room_dict[selected_room], rent, deposit)
        else:
            st.error("All fields are required.")

elif menu == "View Rooms":
    st.subheader("All Rooms")
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT room_number, floor, capacity, current_occupants, monthly_rent FROM rooms", conn)
    conn.close()
    st.dataframe(df)

elif menu == "View Students":
    st.subheader("All Students")
    show_history = st.checkbox("Show student history (left students)")
    conn = sqlite3.connect(DB_NAME)
    if show_history:
        query = '''
            SELECT s.student_id, s.name, s.address, s.phone_number, r.room_number,
                   s.rent_status, s.mode_of_payment, s.monthly_rent, s.security_deposit,
                   s.joined_date, s.left_date
            FROM students s
            JOIN rooms r ON s.room_id = r.id
            WHERE s.left_date IS NOT NULL
        '''
        title = "Left Students Report"
    else:
        query = '''
            SELECT s.student_id, s.name, s.address, s.phone_number, r.room_number,
                   s.rent_status, s.mode_of_payment, s.monthly_rent, s.security_deposit,
                   s.joined_date, s.left_date
            FROM students s
            JOIN rooms r ON s.room_id = r.id
            WHERE s.left_date IS NULL
        '''
        title = "Current Students Report"
    df = pd.read_sql_query(query, conn)
    conn.close()
    st.dataframe(df)

    if st.button("Export as PDF"):
        pdf_bytes = export_to_pdf(df, title)
        st.download_button(label="📄 Download PDF", data=pdf_bytes, file_name=f"{title}.pdf", mime="application/pdf")

elif menu == "Update Rent Status":
    st.subheader("Update Rent Status")
    conn = sqlite3.connect(DB_NAME)
    students = pd.read_sql_query("SELECT student_id, name FROM students WHERE left_date IS NULL", conn)
    if not students.empty:
        student_dict = {f"{row['name']} (ID {row['student_id']})": row['student_id'] for idx, row in students.iterrows()}
        selected = st.selectbox("Select Student", list(student_dict.keys()))
        status = st.selectbox("Rent Status", ["Paid", "Not Paid"])
        mode = st.text_input("Mode of Payment")
        if st.button("Update Status"):
            update_rent_status(student_dict[selected], status, mode)
            st.success("Rent status updated.")
    else:
        st.info("No active students found.")
    conn.close()

elif menu == "Student Exit":
    st.subheader("Mark Student as Left")
    conn = sqlite3.connect(DB_NAME)
    students = pd.read_sql_query("SELECT student_id, name FROM students WHERE left_date IS NULL", conn)
    if not students.empty:
        student_dict = {f"{row['name']} (ID {row['student_id']})": row['student_id'] for idx, row in students.iterrows()}
        selected = st.selectbox("Select Student", list(student_dict.keys()))
        left_date = st.date_input("Select Leaving Date", datetime.today())
        if st.button("Mark as Left"):
            mark_student_left(student_dict[selected], left_date)
            st.success("Student marked as left.")
    else:
        st.info("No active students to mark as left.")
    conn.close()