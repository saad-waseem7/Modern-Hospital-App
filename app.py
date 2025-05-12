from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
)
import pyodbc
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = "hospitalmanagement123"  # Required for flash messages and sessions

conn_str = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=HP-ProBook;"
    "Database=modHospital;"
    "Trusted_Connection=yes;"
)

# User roles
ROLE_ADMIN = "admin"
ROLE_DOCTOR = "doctor"
ROLE_PATIENT = "patient"


def query(sql, params=None):
    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()
    if params:
        cur.execute(sql, params)
    else:
        cur.execute(sql)
    rows = cur.fetchall()
    conn.close()
    return rows


def execute_query(sql, params=None):
    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()
    try:
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        conn.commit()
        return True, "Operation successful"
    except pyodbc.Error as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def get_by_id(table, id_col, id_val):
    sql = f"SELECT * FROM {table} WHERE {id_col} = ?"
    result = query(sql, (id_val,))
    if result:
        return result[0]
    return None


# Ensure all required roles exist in the database
def ensure_roles_exist():
    # Check if Patient role exists
    patient_role = query("SELECT RoleID FROM Roles WHERE RoleName = 'Patient'")
    if not patient_role:
        # Add Patient role
        execute_query("INSERT INTO Roles (RoleName) VALUES ('Patient')")
        print("Added 'Patient' role to the database")

    # Check if UserID column exists in Patients table
    try:
        # Try to query using UserID to see if it exists
        query("SELECT TOP 1 UserID FROM Patients")
        print("UserID column exists in Patients table")
    except:
        # If error, the column doesn't exist, so add it
        try:
            execute_query("ALTER TABLE Patients ADD UserID INT NULL")
            print("Added UserID column to Patients table")

            # Add foreign key constraint (wrapped in try/except as it might fail if there's existing NULL data)
            try:
                execute_query(
                    """
                    ALTER TABLE Patients
                    ADD CONSTRAINT FK_Patients_Users
                    FOREIGN KEY (UserID) REFERENCES Users(UserID)
                """
                )
                print("Added foreign key constraint from Patients to Users")
            except Exception as e:
                print(f"Could not add foreign key constraint: {e}")
        except Exception as e:
            print(f"Error adding UserID column: {e}")


# Call this function at startup
try:
    ensure_roles_exist()
except Exception as e:
    print(f"Error ensuring roles exist: {e}")


# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


# Admin only decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page", "danger")
            return redirect(url_for("login"))
        if session.get("role") != ROLE_ADMIN:
            flash("You do not have permission to access this page", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)

    return decorated_function


# Doctor only decorator
def doctor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page", "danger")
            return redirect(url_for("login"))
        if session.get("role") != ROLE_DOCTOR:
            flash("You do not have permission to access this page", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)

    return decorated_function


# Authentication routes
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # Check if user exists
        user = query(
            "SELECT * FROM Users WHERE Username = ? AND Password = ?",
            (username, password),
        )

        if user:
            user = user[0]
            user_id = user[0]
            session["user_id"] = user_id
            session["username"] = user[1]

            # Get role
            role = get_by_id("Roles", "RoleID", user[3])
            session["role"] = role[1].lower()

            # Get additional information based on role
            if session["role"] == ROLE_DOCTOR:
                doctor = query(
                    "SELECT DoctorID FROM Doctors WHERE UserID = ?", (user_id,)
                )
                if doctor:
                    session["doctor_id"] = doctor[0][0]
            elif session["role"] == ROLE_PATIENT:
                patient = query(
                    "SELECT PatientID FROM Patients WHERE UserID = ?", (user_id,)
                )
                if patient:
                    session["patient_id"] = patient[0][0]

            # Update last login time
            execute_query(
                "UPDATE Users SET LastLogin = GETDATE() WHERE UserID = ?", (user_id,)
            )

            flash(f"Welcome, {username}!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        password_confirm = request.form["password_confirm"]
        role = request.form["role"]

        # Validate inputs
        if password != password_confirm:
            flash("Passwords do not match", "danger")
            return render_template("register.html")

        # Check if username is available
        existing_user = query("SELECT * FROM Users WHERE Username = ?", (username,))
        if existing_user:
            flash("Username already taken", "danger")
            return render_template("register.html")

        # For security, only allow patient registration through the public form
        if role != ROLE_PATIENT:
            flash("Only patient registration is allowed", "danger")
            return render_template("register.html")

        # Get role ID for patient
        role_id = query("SELECT RoleID FROM Roles WHERE RoleName = 'Patient'")

        if not role_id:
            flash("Unable to register at this time. Please try again later.", "danger")
            return render_template("register.html")

        # Insert new user
        sql = "INSERT INTO Users (Username, Password, RoleID) VALUES (?, ?, ?)"
        success, message = execute_query(sql, (username, password, role_id[0][0]))

        if success:
            # Get the new user's ID
            new_user = query(
                "SELECT UserID FROM Users WHERE Username = ?", (username,)
            )[0][0]

            # Create a patient record
            name = request.form["name"]
            dob = request.form["dob"]
            gender = request.form["gender"]
            contact = request.form["contact"]
            address = request.form["address"]

            patient_sql = """INSERT INTO Patients (Name, DOB, Gender, Contact, Address, UserID) 
                            VALUES (?, ?, ?, ?, ?, ?)"""
            pat_success, pat_message = execute_query(
                patient_sql, (name, dob, gender, contact, address, new_user)
            )

            if not pat_success:
                # If patient creation fails, delete the user we just created
                execute_query("DELETE FROM Users WHERE UserID = ?", (new_user,))
                flash(f"Error creating patient record: {pat_message}", "danger")
                return render_template("register.html")

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        else:
            flash(f"Error: {message}", "danger")

    return render_template("register.html")


@app.route("/")
def index():
    # If user is not logged in, redirect to login page
    if "user_id" not in session:
        return redirect(url_for("login"))

    # If user is logged in, route to appropriate dashboard based on role
    role = session.get("role")

    if role == ROLE_ADMIN:
        # Admin dashboard data
        patient_count = query("SELECT COUNT(*) FROM Patients")[0][0]
        doctor_count = query("SELECT COUNT(*) FROM Doctors")[0][0]
        appointment_count = query("SELECT COUNT(*) FROM Appointments")[0][0]
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return render_template(
            "index.html",
            patient_count=patient_count,
            doctor_count=doctor_count,
            appointment_count=appointment_count,
            current_time=current_time,
        )

    elif role == ROLE_DOCTOR:
        # Redirect doctor to doctor dashboard
        return redirect(url_for("doctor_dashboard"))

    elif role == ROLE_PATIENT:
        # Redirect patient to patient dashboard
        return redirect(url_for("patient_dashboard"))

    # If role is not recognized, redirect to login
    session.clear()  # Clear invalid session
    flash("Unknown user role. Please log in again.", "danger")
    return redirect(url_for("login"))


# Patient Routes
@app.route("/patients")
@login_required
def patients():
    if session.get("role") == ROLE_ADMIN:
        rows = query("SELECT * FROM Patients")
        return render_template("patients.html", rows=rows)
    elif session.get("role") == ROLE_DOCTOR:
        doctor_id = session.get("doctor_id")
        rows = query(
            """
            SELECT p.PatientID, p.Name, p.DOB, p.Gender, p.Contact, p.Address, p.UserID
            FROM Patients p 
            JOIN Appointments a ON p.PatientID = a.PatientID 
            WHERE a.DoctorID = ?
            GROUP BY p.PatientID, p.Name, p.DOB, p.Gender, p.Contact, p.Address, p.UserID
        """,
            (doctor_id,),
        )
        return render_template("patients.html", rows=rows, is_doctor=True)
    elif session.get("role") == ROLE_PATIENT:
        patient_id = session.get("patient_id")
        rows = query("SELECT * FROM Patients WHERE PatientID = ?", (patient_id,))
        return render_template("patients.html", rows=rows, is_patient=True)

    return redirect(url_for("index"))


@app.route("/patients/add", methods=["GET", "POST"])
@admin_required
def add_patient():
    if request.method == "POST":
        name = request.form["name"]
        dob = request.form["dob"]
        gender = request.form["gender"]
        contact = request.form["contact"]
        address = request.form["address"]
        medical_history = request.form["medical_history"]

        sql = """INSERT INTO Patients (Name, DOB, Gender, Contact, Address, MedicalHistory) 
                VALUES (?, ?, ?, ?, ?, ?)"""
        success, message = execute_query(
            sql, (name, dob, gender, contact, address, medical_history)
        )

        if success:
            flash("Patient added successfully!", "success")
            return redirect(url_for("patients"))
        else:
            flash(f"Error: {message}", "danger")

    return render_template("patient_form.html", action="Add")


@app.route("/patients/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_patient(id):
    # Check if admin or if patient is editing their own profile
    is_admin = session.get("role") == ROLE_ADMIN
    is_own_profile = (
        session.get("role") == ROLE_PATIENT and session.get("patient_id") == id
    )

    if not (is_admin or is_own_profile):
        flash("You do not have permission to edit this patient", "danger")
        return redirect(url_for("patients"))

    if request.method == "POST":
        name = request.form["name"]
        dob = request.form["dob"]
        gender = request.form["gender"]
        contact = request.form["contact"]
        address = request.form["address"]

        # Only admin can edit medical history
        if is_admin and "medical_history" in request.form:
            medical_history = request.form["medical_history"]
            sql = """UPDATE Patients 
                    SET Name=?, DOB=?, Gender=?, Contact=?, Address=?, MedicalHistory=? 
                    WHERE PatientID=?"""
            success, message = execute_query(
                sql, (name, dob, gender, contact, address, medical_history, id)
            )
        else:
            sql = """UPDATE Patients 
                    SET Name=?, DOB=?, Gender=?, Contact=?, Address=? 
                    WHERE PatientID=?"""
            success, message = execute_query(
                sql, (name, dob, gender, contact, address, id)
            )

        if success:
            flash("Patient updated successfully!", "success")
            if is_own_profile:
                return redirect(url_for("index"))
            else:
                return redirect(url_for("patients"))
        else:
            flash(f"Error: {message}", "danger")

    patient = get_by_id("Patients", "PatientID", id)
    if patient:
        return render_template(
            "patient_form.html", patient=patient, action="Edit", is_admin=is_admin
        )

    flash("Patient not found", "danger")
    return redirect(url_for("patients"))


@app.route("/patients/delete/<int:id>")
@admin_required
def delete_patient(id):
    # Check for related records
    related_appointments = query(
        "SELECT COUNT(*) FROM Appointments WHERE PatientID = ?", (id,)
    )[0][0]

    related_prescriptions = query(
        "SELECT COUNT(*) FROM Prescriptions WHERE PatientID = ?", (id,)
    )[0][0]

    related_bills = query("SELECT COUNT(*) FROM Bills WHERE PatientID = ?", (id,))[0][0]

    if related_appointments > 0 or related_prescriptions > 0 or related_bills > 0:
        message = """
            <strong>Cannot delete patient record</strong><br>
            This patient has active records that need to be handled first:<br>
            <ul>
        """
        if related_appointments > 0:
            message += (
                f"<li>{related_appointments} scheduled/pending appointment(s)</li>"
            )
        if related_prescriptions > 0:
            message += f"<li>{related_prescriptions} active prescription(s)</li>"
        if related_bills > 0:
            message += f"<li>{related_bills} outstanding bill(s)</li>"
        message += """
            </ul>
            <br>
            <strong>Required actions:</strong><br>
            <ul>
                <li>Cancel or complete all scheduled appointments</li>
                <li>Wait for active prescriptions to expire or mark them as completed</li>
                <li>Process or archive all outstanding bills</li>
            </ul>
            Please handle these records before attempting to delete this patient's profile.
        """
        flash(message, "danger")
        return redirect(url_for("patients"))

    # Get UserID before deleting patient
    patient = get_by_id("Patients", "PatientID", id)
    user_id = (
        patient[7] if patient and len(patient) > 7 else None
    )  # UserID is at index 7

    # Delete the patient
    sql = "DELETE FROM Patients WHERE PatientID=?"
    success, message = execute_query(sql, (id,))

    if success:
        # If patient had a user account, delete that too
        if user_id:
            execute_query("DELETE FROM Users WHERE UserID = ?", (user_id,))
        flash("Patient deleted successfully!", "success")
    else:
        flash(f"Error: {message}", "danger")

    return redirect(url_for("patients"))


@app.route("/patients/view/<int:id>")
@login_required
def view_patient(id):
    # Check permissions
    is_admin = session.get("role") == ROLE_ADMIN
    is_doctor = session.get("role") == ROLE_DOCTOR
    is_own_profile = (
        session.get("role") == ROLE_PATIENT and session.get("patient_id") == id
    )

    # Doctors can only view their own patients
    if is_doctor:
        doctor_id = session.get("doctor_id")
        has_appointment = query(
            """
            SELECT COUNT(*) FROM Appointments 
            WHERE PatientID = ? AND DoctorID = ?
        """,
            (id, doctor_id),
        )[0][0]

        if not has_appointment:
            flash("You do not have permission to view this patient", "danger")
            return redirect(url_for("patients"))

    # Patients can only view their own profile
    if session.get("role") == ROLE_PATIENT and not is_own_profile:
        flash("You do not have permission to view this patient", "danger")
        return redirect(url_for("patients"))

    patient = get_by_id("Patients", "PatientID", id)
    if patient:
        # Get related data - only for admin or the patient's doctor or the patient themselves
        appointments = []
        prescriptions = []
        bills = []

        if is_admin or is_doctor or is_own_profile:
            if is_doctor:
                # Doctors see only appointments with them
                doctor_id = session.get("doctor_id")
                appointments = query(
                    """
                    SELECT * FROM Appointments 
                    WHERE PatientID=? AND DoctorID=?
                """,
                    (id, doctor_id),
                )

                prescriptions = query(
                    """
                    SELECT * FROM Prescriptions 
                    WHERE PatientID=? AND DoctorID=?
                """,
                    (id, doctor_id),
                )
            else:
                appointments = query(
                    "SELECT * FROM Appointments WHERE PatientID=?", (id,)
                )
                prescriptions = query(
                    "SELECT * FROM Prescriptions WHERE PatientID=?", (id,)
                )

            if is_admin or is_own_profile:
                bills = query("SELECT * FROM Bills WHERE PatientID=?", (id,))

        return render_template(
            "patient_view.html",
            patient=patient,
            appointments=appointments,
            prescriptions=prescriptions,
            bills=bills,
            is_admin=is_admin,
            is_doctor=is_doctor,
            is_own_profile=is_own_profile,
        )

    flash("Patient not found", "danger")
    return redirect(url_for("patients"))


@app.route("/doctors")
@login_required
def doctors():
    # Everyone can see the list of doctors
    rows = query("SELECT * FROM Doctors")

    is_admin = session.get("role") == ROLE_ADMIN
    is_doctor = session.get("role") == ROLE_DOCTOR

    return render_template(
        "doctors.html", rows=rows, is_admin=is_admin, is_doctor=is_doctor
    )


@app.route("/doctors/add", methods=["GET", "POST"])
@admin_required
def add_doctor():
    if request.method == "POST":
        name = request.form["name"]
        specialty = request.form["specialty"]
        availability = request.form["availability"]
        username = request.form["username"]
        password = request.form["password"]

        # Create user account for doctor
        # Get the doctor role ID
        role_id = query("SELECT RoleID FROM Roles WHERE RoleName = 'Doctor'")[0][0]

        # Check if username is available
        existing_user = query("SELECT * FROM Users WHERE Username = ?", (username,))
        if existing_user:
            flash("Username already taken", "danger")
            return render_template("doctor_form.html", action="Add")

        # Insert new user
        user_sql = "INSERT INTO Users (Username, Password, RoleID) VALUES (?, ?, ?)"
        user_success, user_message = execute_query(
            user_sql, (username, password, role_id)
        )

        if not user_success:
            flash(f"Error creating user account: {user_message}", "danger")
            return render_template("doctor_form.html", action="Add")

        # Get the new user's ID
        new_user_id = query("SELECT UserID FROM Users WHERE Username = ?", (username,))[
            0
        ][0]

        # Insert doctor with user ID
        sql = """INSERT INTO Doctors (Name, Specialty, Availability, UserID) 
                VALUES (?, ?, ?, ?)"""
        success, message = execute_query(
            sql, (name, specialty, availability, new_user_id)
        )

        if success:
            flash("Doctor added successfully!", "success")
            return redirect(url_for("doctors"))
        else:
            # If doctor creation fails, delete the user we just created
            execute_query("DELETE FROM Users WHERE UserID = ?", (new_user_id,))
            flash(f"Error: {message}", "danger")

    return render_template("doctor_form.html", action="Add")


@app.route("/doctors/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_doctor(id):
    # Check if admin or if doctor is editing their own profile
    is_admin = session.get("role") == ROLE_ADMIN
    is_own_profile = (
        session.get("role") == ROLE_DOCTOR and session.get("doctor_id") == id
    )

    if not (is_admin or is_own_profile):
        flash("You do not have permission to edit this doctor", "danger")
        return redirect(url_for("doctors"))

    if request.method == "POST":
        name = request.form["name"]
        specialty = request.form["specialty"]
        availability = request.form["availability"]

        sql = """UPDATE Doctors 
                SET Name=?, Specialty=?, Availability=? 
                WHERE DoctorID=?"""
        success, message = execute_query(sql, (name, specialty, availability, id))

        if success:
            flash("Doctor updated successfully!", "success")
            if is_own_profile:
                return redirect(url_for("index"))
            else:
                return redirect(url_for("doctors"))
        else:
            flash(f"Error: {message}", "danger")

    doctor = get_by_id("Doctors", "DoctorID", id)
    if doctor:
        return render_template("doctor_form.html", doctor=doctor, action="Edit")

    flash("Doctor not found", "danger")
    return redirect(url_for("doctors"))


@app.route("/doctors/delete/<int:id>")
@admin_required
def delete_doctor(id):
    # Check for related records
    related_appointments = query(
        "SELECT COUNT(*) FROM Appointments WHERE DoctorID = ?", (id,)
    )[0][0]

    related_prescriptions = query(
        "SELECT COUNT(*) FROM Prescriptions WHERE DoctorID = ?", (id,)
    )[0][0]

    if related_appointments > 0 or related_prescriptions > 0:
        message = """
            <strong>Cannot delete doctor record</strong><br>
            This doctor has active responsibilities that need to be handled first:<br>
            <ul>
        """
        if related_appointments > 0:
            message += (
                f"<li>{related_appointments} scheduled/active appointment(s)</li>"
            )
        if related_prescriptions > 0:
            message += f"<li>{related_prescriptions} active prescription(s) under their care</li>"
        message += """
            </ul>
            <br>
            <strong>Required actions:</strong><br>
            <ul>
                <li>Reassign patients to other doctors or complete scheduled appointments</li>
                <li>Ensure all prescriptions are completed or transferred to another doctor</li>
            </ul>
            Please handle these records before attempting to delete this doctor's profile.
        """
        flash(message, "danger")
        return redirect(url_for("doctors"))

    # Get UserID first before deleting doctor
    doctor = get_by_id("Doctors", "DoctorID", id)
    if doctor and len(doctor) > 4:  # Make sure UserID column exists
        user_id = doctor[4]  # Assuming UserID is the 5th column

        # Delete doctor first
        doctor_sql = "DELETE FROM Doctors WHERE DoctorID=?"
        doctor_success, doctor_message = execute_query(doctor_sql, (id,))

        if doctor_success:
            # Then delete the user account
            user_sql = "DELETE FROM Users WHERE UserID=?"
            execute_query(user_sql, (user_id,))
            flash("Doctor deleted successfully!", "success")
        else:
            flash(f"Error: {doctor_message}", "danger")
    else:
        sql = "DELETE FROM Doctors WHERE DoctorID=?"
        success, message = execute_query(sql, (id,))

        if success:
            flash("Doctor deleted successfully!", "success")
        else:
            flash(f"Error: {message}", "danger")

    return redirect(url_for("doctors"))


@app.route("/doctors/view/<int:id>")
@login_required
def view_doctor(id):
    doctor = get_by_id("Doctors", "DoctorID", id)
    if doctor:
        # Get related data based on role
        is_admin = session.get("role") == ROLE_ADMIN
        is_own_profile = (
            session.get("role") == ROLE_DOCTOR and session.get("doctor_id") == id
        )

        appointments = []
        prescriptions = []

        if is_admin or is_own_profile:
            appointments = query("SELECT * FROM Appointments WHERE DoctorID=?", (id,))
            prescriptions = query("SELECT * FROM Prescriptions WHERE DoctorID=?", (id,))

        return render_template(
            "doctor_view.html",
            doctor=doctor,
            appointments=appointments,
            prescriptions=prescriptions,
            is_admin=is_admin,
            is_own_profile=is_own_profile,
        )

    flash("Doctor not found", "danger")
    return redirect(url_for("doctors"))


@app.route("/appointments")
@login_required
def appointments():
    is_admin = session.get("role") == ROLE_ADMIN
    is_doctor = session.get("role") == ROLE_DOCTOR
    is_patient = session.get("role") == ROLE_PATIENT

    if is_admin:
        rows = query("SELECT * FROM Appointments")
    elif is_doctor:
        doctor_id = session.get("doctor_id")
        rows = query("SELECT * FROM Appointments WHERE DoctorID = ?", (doctor_id,))
    elif is_patient:
        patient_id = session.get("patient_id")
        rows = query("SELECT * FROM Appointments WHERE PatientID = ?", (patient_id,))
    else:
        rows = []

    # Get doctor and patient names for displaying in the template
    doctors_dict = {}
    patients_dict = {}

    doctors = query("SELECT DoctorID, Name FROM Doctors")
    for doctor in doctors:
        doctors_dict[doctor[0]] = doctor[1]

    patients = query("SELECT PatientID, Name FROM Patients")
    for patient in patients:
        patients_dict[patient[0]] = patient[1]

    return render_template(
        "appointments.html",
        rows=rows,
        doctors=doctors_dict,
        patients=patients_dict,
        is_admin=is_admin,
        is_doctor=is_doctor,
        is_patient=is_patient,
    )


@app.route("/appointments/add", methods=["GET", "POST"])
@login_required
def add_appointment():
    is_admin = session.get("role") == ROLE_ADMIN
    is_doctor = session.get("role") == ROLE_DOCTOR
    is_patient = session.get("role") == ROLE_PATIENT

    if request.method == "POST":
        # For admin, both patient and doctor can be selected
        if is_admin:
            patient_id = request.form["patient_id"]
            doctor_id = request.form["doctor_id"]
        # For doctor, patient can be selected but doctor is fixed
        elif is_doctor:
            patient_id = request.form["patient_id"]
            doctor_id = session.get("doctor_id")
        # For patient, doctor can be selected but patient is fixed
        elif is_patient:
            patient_id = session.get("patient_id")
            doctor_id = request.form["doctor_id"]
        else:
            flash("You do not have permission to add appointments", "danger")
            return redirect(url_for("appointments"))

        datetime_val = request.form["datetime"]
        status = request.form["status"] if "status" in request.form else "Scheduled"

        # Validate the appointment time against doctor's availability
        doctor = get_by_id("Doctors", "DoctorID", doctor_id)
        if not doctor:
            flash("Doctor not found", "danger")
            return redirect(url_for("appointments"))

        # Validate if the requested time is within the doctor's availability
        # This is a simple check - you might want to implement a more sophisticated availability system
        availability = doctor[3]  # Assuming Availability is the 4th column

        sql = """INSERT INTO Appointments (PatientID, DoctorID, DateTime, Status) 
                VALUES (?, ?, ?, ?)"""
        success, message = execute_query(
            sql, (patient_id, doctor_id, datetime_val, status)
        )

        if success:
            flash("Appointment added successfully!", "success")
            return redirect(url_for("appointments"))
        else:
            flash(f"Error: {message}", "danger")

    # Get list of patients and doctors for dropdowns
    patients = query("SELECT PatientID, Name FROM Patients")
    doctors = query("SELECT DoctorID, Name FROM Doctors")

    return render_template(
        "appointment_form.html",
        patients=patients,
        doctors=doctors,
        action="Add",
        is_admin=is_admin,
        is_doctor=is_doctor,
        is_patient=is_patient,
    )


@app.route("/appointments/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_appointment(id):
    is_admin = session.get("role") == ROLE_ADMIN
    is_doctor = session.get("role") == ROLE_DOCTOR
    is_patient = session.get("role") == ROLE_PATIENT

    # Get the appointment
    appointment = get_by_id("Appointments", "AppointmentID", id)
    if not appointment:
        flash("Appointment not found", "danger")
        return redirect(url_for("appointments"))

    # Check permissions
    if is_doctor and appointment[2] != session.get("doctor_id"):
        flash("You can only edit your own appointments", "danger")
        return redirect(url_for("appointments"))

    if is_patient and appointment[1] != session.get("patient_id"):
        flash("You can only edit your own appointments", "danger")
        return redirect(url_for("appointments"))

    if request.method == "POST":
        # For admin, both patient and doctor can be changed
        if is_admin:
            patient_id = request.form["patient_id"]
            doctor_id = request.form["doctor_id"]
        # For doctor, only the datetime and status can be changed
        elif is_doctor:
            patient_id = appointment[1]
            doctor_id = session.get("doctor_id")
        # For patient, only cancellation is possible
        elif is_patient:
            patient_id = session.get("patient_id")
            doctor_id = appointment[2]
        else:
            flash("You do not have permission to edit appointments", "danger")
            return redirect(url_for("appointments"))

        # If patient is canceling, use the original datetime to avoid conversion issues
        if (
            is_patient
            and "original_datetime" in request.form
            and request.form["status"] == "Cancelled"
        ):
            datetime_val = appointment[
                3
            ]  # Use the original datetime from the appointment
        else:
            # Format datetime in SQL Server compatible format
            try:
                from datetime import datetime

                # Parse the input datetime string
                dt = datetime.fromisoformat(
                    request.form["datetime"].replace("Z", "+00:00")
                )
                # Format datetime in SQL Server format
                datetime_val = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                flash("Invalid date/time format", "danger")
                return redirect(url_for("appointments"))

        status = request.form["status"] if "status" in request.form else appointment[4]

        sql = """UPDATE Appointments 
                SET PatientID=?, DoctorID=?, DateTime=?, Status=? 
                WHERE AppointmentID=?"""
        success, message = execute_query(
            sql, (patient_id, doctor_id, datetime_val, status, id)
        )

        if success:
            flash("Appointment updated successfully!", "success")
            return redirect(url_for("appointments"))
        else:
            flash(f"Error: {message}", "danger")

    # Get list of patients and doctors for dropdowns
    patients = query("SELECT PatientID, Name FROM Patients")
    doctors = query("SELECT DoctorID, Name FROM Doctors")

    return render_template(
        "appointment_form.html",
        appointment=appointment,
        patients=patients,
        doctors=doctors,
        action="Edit",
        is_admin=is_admin,
        is_doctor=is_doctor,
        is_patient=is_patient,
    )


@app.route("/appointments/delete/<int:id>")
@login_required
def delete_appointment(id):
    is_admin = session.get("role") == ROLE_ADMIN
    is_doctor = session.get("role") == ROLE_DOCTOR

    # Only admin and doctors can delete appointments
    if not (is_admin or is_doctor):
        flash("You do not have permission to delete appointments", "danger")
        return redirect(url_for("appointments"))

    # Get the appointment
    appointment = get_by_id("Appointments", "AppointmentID", id)
    if not appointment:
        flash("Appointment not found", "danger")
        return redirect(url_for("appointments"))

    # Doctors can only delete their own appointments
    if is_doctor and appointment[2] != session.get("doctor_id"):
        flash("You can only delete your own appointments", "danger")
        return redirect(url_for("appointments"))

    sql = "DELETE FROM Appointments WHERE AppointmentID=?"
    success, message = execute_query(sql, (id,))

    if success:
        flash("Appointment deleted successfully!", "success")
    else:
        flash(f"Error: {message}", "danger")

    return redirect(url_for("appointments"))


@app.route("/bills")
@login_required
def bills():
    status_filter = request.args.get("status", "")

    # Base SQL queries with filtering
    base_sql_admin = """
        SELECT b.*, p.Name as PatientName 
        FROM Bills b
        JOIN Patients p ON b.PatientID = p.PatientID
    """

    base_sql_doctor = """
        SELECT b.BillID, b.PatientID, b.Amount, b.Status, b.Description, b.CreatedAt, p.Name as PatientName 
        FROM Bills b
        JOIN Patients p ON b.PatientID = p.PatientID
        WHERE EXISTS (
            SELECT 1 FROM Appointments a 
            WHERE a.PatientID = b.PatientID AND a.DoctorID = ?
        )
    """

    base_sql_patient = """
        SELECT b.*, p.Name as PatientName 
        FROM Bills b
        JOIN Patients p ON b.PatientID = p.PatientID
        WHERE b.PatientID = ?
    """

    # Add status filter if provided
    if status_filter:
        base_sql_admin += " WHERE b.Status = ?"
        base_sql_doctor += " AND b.Status = ?"
        base_sql_patient += " AND b.Status = ?"

    # Ordering
    base_sql_admin += " ORDER BY b.CreatedAt DESC"
    base_sql_doctor += " ORDER BY b.CreatedAt DESC"
    base_sql_patient += " ORDER BY b.CreatedAt DESC"

    if session.get("role") == ROLE_ADMIN:
        # Admin sees all bills
        if status_filter:
            rows = query(base_sql_admin, (status_filter,))
        else:
            rows = query(base_sql_admin)
    elif session.get("role") == ROLE_DOCTOR:
        # Doctors can see bills for their patients with completed appointments
        if status_filter:
            rows = query(base_sql_doctor, (session.get("doctor_id"), status_filter))
        else:
            rows = query(base_sql_doctor, (session.get("doctor_id"),))
    elif session.get("role") == ROLE_PATIENT:
        # Patients see only their own bills
        if status_filter:
            rows = query(base_sql_patient, (session.get("patient_id"), status_filter))
        else:
            rows = query(base_sql_patient, (session.get("patient_id"),))
    else:
        rows = []

    return render_template("bills.html", rows=rows)


@app.route("/bills/add", methods=["GET", "POST"])
@login_required
def add_bill():
    # Only admin and doctors can add bills
    if session.get("role") not in [ROLE_ADMIN, ROLE_DOCTOR]:
        flash("You do not have permission to access this page", "danger")
        return redirect(url_for("bills"))

    if request.method == "POST":
        patient_id = request.form["patient_id"]
        amount = request.form["amount"]
        status = request.form["status"]
        description = request.form["description"]

        sql = """
            INSERT INTO Bills (PatientID, Amount, Status, Description, CreatedAt) 
            VALUES (?, ?, ?, ?, GETDATE())
        """
        success, message = execute_query(sql, (patient_id, amount, status, description))

        if success:
            flash("Bill added successfully", "success")
            return redirect(url_for("bills"))
        else:
            flash(f"Error adding bill: {message}", "danger")

    # Get list of patients
    if session.get("role") == ROLE_ADMIN:
        patients = query("SELECT PatientID, Name FROM Patients ORDER BY Name")
    else:  # Doctor role
        # For doctors, show only their patients
        patients = query(
            """
            SELECT DISTINCT p.PatientID, p.Name 
            FROM Patients p
            JOIN Appointments a ON p.PatientID = a.PatientID
            WHERE a.DoctorID = ?
            ORDER BY p.Name
        """,
            (session.get("doctor_id"),),
        )

    return render_template("bill_form.html", patients=patients)


@app.route("/bills/edit/<int:id>", methods=["GET", "POST"])
def edit_bill(id):
    if request.method == "POST":
        patient_id = request.form["patient_id"]
        amount = request.form["amount"]
        status = request.form["status"]

        sql = """UPDATE Bills 
                SET PatientID=?, Amount=?, Status=? 
                WHERE BillID=?"""
        success, message = execute_query(sql, (patient_id, amount, status, id))

        if success:
            flash("Bill updated successfully!", "success")
            return redirect(url_for("bills"))
        else:
            flash(f"Error: {message}", "danger")

    bill = get_by_id("Bills", "BillID", id)
    if bill:
        # Get list of patients for dropdown
        patients = query("SELECT PatientID, Name FROM Patients")

        return render_template(
            "bill_form.html", bill=bill, patients=patients, action="Edit"
        )

    flash("Bill not found", "danger")
    return redirect(url_for("bills"))


@app.route("/bills/delete/<int:id>")
def delete_bill(id):
    sql = "DELETE FROM Bills WHERE BillID=?"
    success, message = execute_query(sql, (id,))

    if success:
        flash("Bill deleted successfully!", "success")
    else:
        flash(f"Error: {message}", "danger")

    return redirect(url_for("bills"))


@app.route("/prescriptions")
@login_required
def prescriptions():
    current_date = datetime.now()

    if session.get("role") == ROLE_ADMIN:
        # Admin sees all prescriptions
        sql = """
            SELECT pr.*, p.Name as PatientName, d.Name as DoctorName 
            FROM Prescriptions pr
            JOIN Patients p ON pr.PatientID = p.PatientID
            JOIN Doctors d ON pr.DoctorID = d.DoctorID
            ORDER BY pr.DateIssued DESC
        """
        rows = query(sql)
    elif session.get("role") == ROLE_DOCTOR:
        # Doctors see prescriptions they issued
        sql = """
            SELECT pr.*, p.Name as PatientName, d.Name as DoctorName 
            FROM Prescriptions pr
            JOIN Patients p ON pr.PatientID = p.PatientID
            JOIN Doctors d ON pr.DoctorID = d.DoctorID
            WHERE pr.DoctorID = ?
            ORDER BY pr.DateIssued DESC
        """
        rows = query(sql, (session.get("doctor_id"),))
    elif session.get("role") == ROLE_PATIENT:
        # Patients see their own prescriptions
        sql = """
            SELECT pr.*, p.Name as PatientName, d.Name as DoctorName 
            FROM Prescriptions pr
            JOIN Patients p ON pr.PatientID = p.PatientID
            JOIN Doctors d ON pr.DoctorID = d.DoctorID
            WHERE pr.PatientID = ?
            ORDER BY pr.DateIssued DESC
        """
        rows = query(sql, (session.get("patient_id"),))
    else:
        rows = []

    return render_template("prescriptions.html", rows=rows, current_date=current_date)


@app.route("/prescriptions/add", methods=["GET", "POST"])
@doctor_required
def add_prescription():
    medication_param = request.args.get("medication", "")

    if request.method == "POST":
        patient_id = request.form["patient_id"]
        medication = request.form["medication"]
        dosage = request.form["dosage"]
        valid_days = int(request.form.get("valid_days", 30))

        # Calculate valid until date
        sql = """
            INSERT INTO Prescriptions (PatientID, DoctorID, Medication, Dosage, DateIssued, ValidUntil) 
            VALUES (?, ?, ?, ?, GETDATE(), DATEADD(day, ?, GETDATE()))
        """
        success, message = execute_query(
            sql, (patient_id, session.get("doctor_id"), medication, dosage, valid_days)
        )

        if success:
            flash("Prescription added successfully", "success")

            # Update medication stock if needed
            # This is a basic implementation - in a real system, you might want to link
            # medications more directly to pharmacy inventory
            try:
                execute_query(
                    """
                    UPDATE PharmacyInventory 
                    SET Stock = Stock - 1, LastUpdated = GETDATE() 
                    WHERE Name = ? AND Stock > 0
                """,
                    (medication,),
                )
            except:
                # If medication doesn't exist in inventory or other error, just ignore
                pass

            return redirect(url_for("prescriptions"))
        else:
            flash(f"Error adding prescription: {message}", "danger")

    # Get list of patients (only this doctor's patients)
    patients = query(
        """
        SELECT DISTINCT p.PatientID, p.Name 
        FROM Patients p
        JOIN Appointments a ON p.PatientID = a.PatientID
        WHERE a.DoctorID = ?
        ORDER BY p.Name
    """,
        (session.get("doctor_id"),),
    )

    # Get available medications
    medications = query("SELECT * FROM PharmacyInventory WHERE Stock > 0 ORDER BY Name")

    return render_template(
        "prescription_form.html",
        patients=patients,
        medications=medications,
        medication_param=medication_param,
    )


@app.route("/prescriptions/edit/<int:id>", methods=["GET", "POST"])
def edit_prescription(id):
    if request.method == "POST":
        patient_id = request.form["patient_id"]
        doctor_id = request.form["doctor_id"]
        medication = request.form["medication"]
        dosage = request.form["dosage"]

        sql = """UPDATE Prescriptions 
                SET PatientID=?, DoctorID=?, Medication=?, Dosage=? 
                WHERE PrescriptionID=?"""
        success, message = execute_query(
            sql, (patient_id, doctor_id, medication, dosage, id)
        )

        if success:
            flash("Prescription updated successfully!", "success")
            return redirect(url_for("prescriptions"))
        else:
            flash(f"Error: {message}", "danger")

    prescription = get_by_id("Prescriptions", "PrescriptionID", id)
    if prescription:
        # Get list of patients and doctors for dropdowns
        patients = query("SELECT PatientID, Name FROM Patients")
        doctors = query("SELECT DoctorID, Name FROM Doctors")

        return render_template(
            "prescription_form.html",
            prescription=prescription,
            patients=patients,
            doctors=doctors,
            action="Edit",
        )

    flash("Prescription not found", "danger")
    return redirect(url_for("prescriptions"))


@app.route("/prescriptions/delete/<int:id>")
def delete_prescription(id):
    sql = "DELETE FROM Prescriptions WHERE PrescriptionID=?"
    success, message = execute_query(sql, (id,))

    if success:
        flash("Prescription deleted successfully!", "success")
    else:
        flash(f"Error: {message}", "danger")

    return redirect(url_for("prescriptions"))


@app.route("/pharmacy")
@login_required
def pharmacy():
    stock_filter = request.args.get("stock", "")

    if stock_filter == "low":
        sql = """
            SELECT * FROM PharmacyInventory 
            WHERE Stock <= Threshold AND Stock > 0
            ORDER BY (Stock * 1.0 / Threshold), Name
        """
        rows = query(sql)
    elif stock_filter == "out":
        sql = "SELECT * FROM PharmacyInventory WHERE Stock = 0 ORDER BY Name"
        rows = query(sql)
    else:
        sql = "SELECT * FROM PharmacyInventory ORDER BY Name"
        rows = query(sql)

    return render_template("pharmacy.html", rows=rows)


@app.route("/pharmacy/add", methods=["GET", "POST"])
@admin_required
def add_pharmacy_item():
    if request.method == "POST":
        name = request.form["name"]
        stock = request.form["stock"]
        threshold = request.form["threshold"]
        price = request.form["price"]

        # Check if medication already exists
        existing = query("SELECT * FROM PharmacyInventory WHERE Name = ?", (name,))
        if existing:
            flash("Medication already exists in inventory", "danger")
            return render_template("pharmacy_form.html")

        sql = """
            INSERT INTO PharmacyInventory (Name, Stock, Threshold, Price, LastUpdated) 
            VALUES (?, ?, ?, ?, GETDATE())
        """
        success, message = execute_query(sql, (name, stock, threshold, price))

        if success:
            flash("Medication added successfully", "success")
            return redirect(url_for("pharmacy"))
        else:
            flash(f"Error adding medication: {message}", "danger")

    return render_template("pharmacy_form.html")


@app.route("/pharmacy/edit/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_pharmacy_item(id):
    item = get_by_id("PharmacyInventory", "ItemID", id)

    if not item:
        flash("Medication not found", "danger")
        return redirect(url_for("pharmacy"))

    if request.method == "POST":
        name = request.form["name"]
        stock = request.form["stock"]
        threshold = request.form["threshold"]
        price = request.form["price"]

        # Check if medication name already exists (excluding current item)
        existing = query(
            "SELECT * FROM PharmacyInventory WHERE Name = ? AND ItemID != ?", (name, id)
        )
        if existing:
            flash("Medication name already exists in inventory", "danger")
            return render_template("pharmacy_form.html", item=item)

        sql = """
            UPDATE PharmacyInventory 
            SET Name = ?, Stock = ?, Threshold = ?, Price = ?, LastUpdated = GETDATE() 
            WHERE ItemID = ?
        """
        success, message = execute_query(sql, (name, stock, threshold, price, id))

        if success:
            flash("Medication updated successfully", "success")
            return redirect(url_for("pharmacy"))
        else:
            flash(f"Error updating medication: {message}", "danger")

    return render_template("pharmacy_form.html", item=item)


@app.route("/pharmacy/delete/<int:id>")
@admin_required
def delete_pharmacy_item(id):
    # Check if medication is currently used in any active prescriptions
    active_prescriptions = query(
        """
        SELECT COUNT(*) FROM Prescriptions 
        WHERE Medication LIKE ? AND ValidUntil > GETDATE()
    """,
        (f"%{id}%",),
    )

    if active_prescriptions and active_prescriptions[0][0] > 0:
        flash(
            "Cannot delete medication that is currently used in active prescriptions",
            "danger",
        )
        return redirect(url_for("pharmacy"))

    success, message = execute_query(
        "DELETE FROM PharmacyInventory WHERE ItemID = ?", (id,)
    )

    if success:
        flash("Medication deleted successfully", "success")
    else:
        flash(f"Error deleting medication: {message}", "danger")

    return redirect(url_for("pharmacy"))


@app.route("/lab_reports")
def lab_reports():
    rows = query("SELECT * FROM LabReports")
    return render_template("lab_reports.html", rows=rows)


@app.route("/lab_reports/add", methods=["GET", "POST"])
def add_lab_report():
    if request.method == "POST":
        patient_id = request.form["patient_id"]
        test_type = request.form["test_type"]
        result = request.form["result"]
        date_taken = request.form["date_taken"]

        sql = """INSERT INTO LabReports (PatientID, TestType, Result, DateTaken) 
                VALUES (?, ?, ?, ?)"""
        success, message = execute_query(
            sql, (patient_id, test_type, result, date_taken)
        )

        if success:
            flash("Lab report added successfully!", "success")
            return redirect(url_for("lab_reports"))
        else:
            flash(f"Error: {message}", "danger")

    # Get list of patients for dropdown
    patients = query("SELECT PatientID, Name FROM Patients")

    return render_template("lab_report_form.html", patients=patients, action="Add")


@app.route("/lab_reports/edit/<int:id>", methods=["GET", "POST"])
def edit_lab_report(id):
    if request.method == "POST":
        patient_id = request.form["patient_id"]
        test_type = request.form["test_type"]
        result = request.form["result"]
        date_taken = request.form["date_taken"]

        sql = """UPDATE LabReports 
                SET PatientID=?, TestType=?, Result=?, DateTaken=? 
                WHERE ReportID=?"""
        success, message = execute_query(
            sql, (patient_id, test_type, result, date_taken, id)
        )

        if success:
            flash("Lab report updated successfully!", "success")
            return redirect(url_for("lab_reports"))
        else:
            flash(f"Error: {message}", "danger")

    report = get_by_id("LabReports", "ReportID", id)
    if report:
        # Get list of patients for dropdown
        patients = query("SELECT PatientID, Name FROM Patients")

        return render_template(
            "lab_report_form.html", report=report, patients=patients, action="Edit"
        )

    flash("Lab report not found", "danger")
    return redirect(url_for("lab_reports"))


@app.route("/lab_reports/delete/<int:id>")
def delete_lab_report(id):
    sql = "DELETE FROM LabReports WHERE ReportID=?"
    success, message = execute_query(sql, (id,))

    if success:
        flash("Lab report deleted successfully!", "success")
    else:
        flash(f"Error: {message}", "danger")

    return redirect(url_for("lab_reports"))


@app.route("/staff")
@login_required
def staff():
    role_filter = request.args.get("role", "")

    if role_filter:
        sql = """
            SELECT s.*, u.Username 
            FROM Staff s
            LEFT JOIN Users u ON s.UserID = u.UserID
            WHERE s.Role = ?
            ORDER BY s.Name
        """
        rows = query(sql, (role_filter,))
    else:
        sql = """
            SELECT s.*, u.Username 
            FROM Staff s
            LEFT JOIN Users u ON s.UserID = u.UserID
            ORDER BY s.Name
        """
        rows = query(sql)

    return render_template("staff.html", rows=rows)


@app.route("/staff/add", methods=["GET", "POST"])
@admin_required
def add_staff():
    if request.method == "POST":
        name = request.form["name"]
        role = request.form["role"]
        contact = request.form["contact"]

        # First check if a staff member with the same name already exists
        existing_staff = query("SELECT * FROM Staff WHERE Name = ?", (name,))
        if existing_staff:
            flash("A staff member with this name already exists", "danger")
            return render_template("staff_form.html")

        # Insert without specifying UserID column at all
        sql = "INSERT INTO Staff (Name, Role, Contact) VALUES (?, ?, ?)"
        success, message = execute_query(sql, (name, role, contact))

        if success:
            flash("Staff member added successfully", "success")
            return redirect(url_for("staff"))
        else:
            flash(f"Error adding staff member: {message}", "danger")

    return render_template("staff_form.html")


@app.route("/staff/edit/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_staff(id):
    staff = get_by_id("Staff", "StaffID", id)

    if not staff:
        flash("Staff member not found", "danger")
        return redirect(url_for("staff"))

    if request.method == "POST":
        name = request.form["name"]
        role = request.form["role"]
        contact = request.form["contact"]

        sql = """
            UPDATE Staff 
            SET Name = ?, Role = ?, Contact = ? 
            WHERE StaffID = ?
        """
        success, message = execute_query(sql, (name, role, contact, id))

        if success:
            flash("Staff member updated successfully", "success")
            return redirect(url_for("staff"))
        else:
            flash(f"Error updating staff member: {message}", "danger")

    return render_template("staff_form.html", staff=staff)


@app.route("/staff/delete/<int:id>")
@admin_required
def delete_staff(id):
    # Check if staff has a user account
    staff = get_by_id("Staff", "StaffID", id)

    if not staff:
        flash("Staff member not found", "danger")
        return redirect(url_for("staff"))

    # If staff has a user account, delete that first
    if staff[4]:  # UserID is at index 4
        execute_query("DELETE FROM Users WHERE UserID = ?", (staff[4],))

    # Now delete the staff record
    success, message = execute_query("DELETE FROM Staff WHERE StaffID = ?", (id,))

    if success:
        flash("Staff member deleted successfully", "success")
    else:
        flash(f"Error deleting staff member: {message}", "danger")

    return redirect(url_for("staff"))


@app.route("/emergency")
def emergency():
    rows = query("SELECT * FROM EmergencyCases")
    return render_template("emergency.html", rows=rows)


@app.route("/emergency/add", methods=["GET", "POST"])
def add_emergency():
    if request.method == "POST":
        patient_id = request.form["patient_id"]
        case_details = request.form["case_details"]
        ambulance_assigned = 1 if "ambulance_assigned" in request.form else 0

        sql = """INSERT INTO EmergencyCases (PatientID, CaseDetails, AmbulanceAssigned) 
                VALUES (?, ?, ?)"""
        success, message = execute_query(
            sql, (patient_id, case_details, ambulance_assigned)
        )

        if success:
            flash("Emergency case added successfully!", "success")
            return redirect(url_for("emergency"))
        else:
            flash(f"Error: {message}", "danger")

    # Get list of patients for dropdown
    patients = query("SELECT PatientID, Name FROM Patients")

    return render_template("emergency_form.html", patients=patients, action="Add")


@app.route("/emergency/edit/<int:id>", methods=["GET", "POST"])
def edit_emergency(id):
    if request.method == "POST":
        patient_id = request.form["patient_id"]
        case_details = request.form["case_details"]
        ambulance_assigned = 1 if "ambulance_assigned" in request.form else 0

        sql = """UPDATE EmergencyCases 
                SET PatientID=?, CaseDetails=?, AmbulanceAssigned=? 
                WHERE CaseID=?"""
        success, message = execute_query(
            sql, (patient_id, case_details, ambulance_assigned, id)
        )

        if success:
            flash("Emergency case updated successfully!", "success")
            return redirect(url_for("emergency"))
        else:
            flash(f"Error: {message}", "danger")

    case = get_by_id("EmergencyCases", "CaseID", id)
    if case:
        # Get list of patients for dropdown
        patients = query("SELECT PatientID, Name FROM Patients")

        return render_template(
            "emergency_form.html", case=case, patients=patients, action="Edit"
        )

    flash("Emergency case not found", "danger")
    return redirect(url_for("emergency"))


@app.route("/emergency/delete/<int:id>")
def delete_emergency(id):
    sql = "DELETE FROM EmergencyCases WHERE CaseID=?"
    success, message = execute_query(sql, (id,))

    if success:
        flash("Emergency case deleted successfully!", "success")
    else:
        flash(f"Error: {message}", "danger")

    return redirect(url_for("emergency"))


@app.route("/rooms")
@login_required
def rooms():
    status_filter = request.args.get("status", "")

    if status_filter:
        sql = "SELECT * FROM Rooms WHERE Status = ? ORDER BY RoomNumber"
        rows = query(sql, (status_filter,))
    else:
        sql = "SELECT * FROM Rooms ORDER BY RoomNumber"
        rows = query(sql)

    return render_template("rooms.html", rows=rows)


@app.route("/rooms/add", methods=["GET", "POST"])
@admin_required
def add_room():
    if request.method == "POST":
        room_number = request.form["room_number"]
        room_type = request.form["type"]
        status = request.form["status"]
        price = request.form["price"] or None  # Convert empty string to None

        # Check if room number already exists
        existing = query("SELECT * FROM Rooms WHERE RoomNumber = ?", (room_number,))
        if existing:
            flash("Room number already exists", "danger")
            return render_template("room_form.html")

        sql = "INSERT INTO Rooms (RoomNumber, Type, Status, PricePerDay) VALUES (?, ?, ?, ?)"
        success, message = execute_query(sql, (room_number, room_type, status, price))

        if success:
            flash("Room added successfully", "success")
            return redirect(url_for("rooms"))
        else:
            flash(f"Error adding room: {message}", "danger")

    return render_template("room_form.html")


@app.route("/rooms/edit/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_room(id):
    room = get_by_id("Rooms", "RoomID", id)

    if not room:
        flash("Room not found", "danger")
        return redirect(url_for("rooms"))

    if request.method == "POST":
        room_number = request.form["room_number"]
        room_type = request.form["type"]
        status = request.form["status"]
        price = request.form["price"] or None

        # Check if room number already exists (excluding current room)
        existing = query(
            "SELECT * FROM Rooms WHERE RoomNumber = ? AND RoomID != ?",
            (room_number, id),
        )
        if existing:
            flash("Room number already exists", "danger")
            return render_template("room_form.html", room=room)

        sql = """UPDATE Rooms 
                 SET RoomNumber = ?, Type = ?, Status = ?, PricePerDay = ? 
                 WHERE RoomID = ?"""
        success, message = execute_query(
            sql, (room_number, room_type, status, price, id)
        )

        if success:
            flash("Room updated successfully", "success")
            return redirect(url_for("rooms"))
        else:
            flash(f"Error updating room: {message}", "danger")

    return render_template("room_form.html", room=room)


@app.route("/rooms/delete/<int:id>")
@admin_required
def delete_room(id):
    # Check if room is currently assigned
    assigned = query(
        """
        SELECT * FROM RoomAssignments 
        WHERE RoomID = ? AND EndDate IS NULL
    """,
        (id,),
    )

    if assigned:
        flash("Cannot delete room that is currently assigned to patients", "danger")
        return redirect(url_for("rooms"))

    success, message = execute_query("DELETE FROM Rooms WHERE RoomID = ?", (id,))

    if success:
        flash("Room deleted successfully", "success")
    else:
        flash(f"Error deleting room: {message}", "danger")

    return redirect(url_for("rooms"))


@app.route("/rooms/assignments/<int:room_id>")
@login_required
def room_assignments(room_id):
    room = get_by_id("Rooms", "RoomID", room_id)

    if not room:
        flash("Room not found", "danger")
        return redirect(url_for("rooms"))

    # Get all assignments for this room
    sql = """
        SELECT ra.*, p.Name as PatientName, s.Name as StaffName  
        FROM RoomAssignments ra
        JOIN Patients p ON ra.PatientID = p.PatientID
        LEFT JOIN Staff s ON ra.AssignedBy = s.StaffID
        WHERE ra.RoomID = ?
        ORDER BY ra.StartDate DESC
    """
    assignments = query(sql, (room_id,))

    return render_template("room_assignments.html", room=room, assignments=assignments)


@app.route("/room_assignments/add", methods=["GET", "POST"])
def add_room_assignment():
    if request.method == "POST":
        patient_id = request.form["patient_id"]
        room_id = request.form["room_id"]
        start_date = request.form["start_date"]
        end_date = request.form["end_date"] if request.form["end_date"] else None

        sql = """INSERT INTO RoomAssignments (PatientID, RoomID, StartDate, EndDate) 
                VALUES (?, ?, ?, ?)"""
        success, message = execute_query(
            sql, (patient_id, room_id, start_date, end_date)
        )

        if success:
            # Update room status to Occupied
            update_sql = "UPDATE Rooms SET Status = 'Occupied' WHERE RoomID = ?"
            execute_query(update_sql, (room_id,))

            flash("Room assignment added successfully!", "success")
            return redirect(url_for("room_assignments", room_id=room_id))
        else:
            flash(f"Error: {message}", "danger")

    # Get list of patients and available rooms for dropdowns
    patients = query("SELECT PatientID, Name FROM Patients")
    rooms = query("SELECT RoomID, RoomNumber FROM Rooms WHERE Status='Available'")

    # Get today's date for the default start date
    today = datetime.now().strftime("%Y-%m-%d")

    return render_template(
        "room_assignment_form.html",
        patients=patients,
        rooms=rooms,
        action="Add",
        today=today,
    )


@app.route("/room_assignments/edit/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_room_assignment(id):
    # Get the assignment details
    assignment = get_by_id("RoomAssignments", "AssignmentID", id)

    if not assignment:
        flash("Assignment not found", "danger")
        return redirect(url_for("rooms"))

    room_id = assignment[2]  # RoomID is at index 2

    if request.method == "POST":
        end_date = request.form["end_date"]

        # Update the assignment with the end date
        sql = "UPDATE RoomAssignments SET EndDate = ? WHERE AssignmentID = ?"
        success, message = execute_query(sql, (end_date, id))

        if success:
            # Check if there are any active assignments for this room
            active_assignments = query(
                "SELECT COUNT(*) FROM RoomAssignments WHERE RoomID = ? AND EndDate IS NULL AND AssignmentID != ?",
                (room_id, id),
            )

            # If no active assignments, update room status to Available
            if active_assignments[0][0] == 0:
                update_sql = "UPDATE Rooms SET Status = 'Available' WHERE RoomID = ?"
                execute_query(update_sql, (room_id,))

            flash("Room assignment ended successfully", "success")
            return redirect(url_for("room_assignments", room_id=room_id))
        else:
            flash(f"Error: {message}", "danger")

    # Get the room and patient info for display
    room = get_by_id("Rooms", "RoomID", room_id)
    patient = get_by_id("Patients", "PatientID", assignment[1])

    # Set today's date as the default end date
    today = datetime.now().strftime("%Y-%m-%d")

    return render_template(
        "room_assignment_form.html",
        assignment=assignment,
        room=room,
        patient=patient,
        end_date=today,
        action="End",
    )


@app.route("/insurance")
def insurance():
    rows = query("SELECT * FROM InsuranceClaims")
    return render_template("insurance.html", rows=rows)


@app.route("/insurance/add", methods=["GET", "POST"])
def add_insurance():
    if request.method == "POST":
        patient_id = request.form["patient_id"]
        insurer = request.form["insurer"]
        policy_number = request.form["policy_number"]
        claim_status = request.form["claim_status"]

        sql = """INSERT INTO InsuranceClaims (PatientID, Insurer, PolicyNumber, ClaimStatus) 
                VALUES (?, ?, ?, ?)"""
        success, message = execute_query(
            sql, (patient_id, insurer, policy_number, claim_status)
        )

        if success:
            flash("Insurance claim added successfully!", "success")
            return redirect(url_for("insurance"))
        else:
            flash(f"Error: {message}", "danger")

    # Get list of patients for dropdown
    patients = query("SELECT PatientID, Name FROM Patients")

    return render_template("insurance_form.html", patients=patients, action="Add")


@app.route("/insurance/edit/<int:id>", methods=["GET", "POST"])
def edit_insurance(id):
    if request.method == "POST":
        patient_id = request.form["patient_id"]
        insurer = request.form["insurer"]
        policy_number = request.form["policy_number"]
        claim_status = request.form["claim_status"]

        sql = """UPDATE InsuranceClaims 
                SET PatientID=?, Insurer=?, PolicyNumber=?, ClaimStatus=? 
                WHERE ClaimID=?"""
        success, message = execute_query(
            sql, (patient_id, insurer, policy_number, claim_status, id)
        )

        if success:
            flash("Insurance claim updated successfully!", "success")
            return redirect(url_for("insurance"))
        else:
            flash(f"Error: {message}", "danger")

    claim = get_by_id("InsuranceClaims", "ClaimID", id)
    if claim:
        # Get list of patients for dropdown
        patients = query("SELECT PatientID, Name FROM Patients")

        return render_template(
            "insurance_form.html", claim=claim, patients=patients, action="Edit"
        )

    flash("Insurance claim not found", "danger")
    return redirect(url_for("insurance"))


@app.route("/insurance/delete/<int:id>")
def delete_insurance(id):
    sql = "DELETE FROM InsuranceClaims WHERE ClaimID=?"
    success, message = execute_query(sql, (id,))

    if success:
        flash("Insurance claim deleted successfully!", "success")
    else:
        flash(f"Error: {message}", "danger")

    return redirect(url_for("insurance"))


@app.route("/feedback")
def feedback():
    rows = query("SELECT * FROM Feedback")
    return render_template("feedback.html", rows=rows)


@app.route("/feedback/add", methods=["GET", "POST"])
def add_feedback():
    if request.method == "POST":
        patient_id = request.form["patient_id"]
        doctor_id = request.form["doctor_id"]
        rating = request.form["rating"]
        comments = request.form["comments"]

        sql = """INSERT INTO Feedback (PatientID, DoctorID, Rating, Comments) 
                VALUES (?, ?, ?, ?)"""
        success, message = execute_query(sql, (patient_id, doctor_id, rating, comments))

        if success:
            flash("Feedback added successfully!", "success")
            return redirect(url_for("feedback"))
        else:
            flash(f"Error: {message}", "danger")

    # Get list of patients and doctors for dropdowns
    patients = query("SELECT PatientID, Name FROM Patients")
    doctors = query("SELECT DoctorID, Name FROM Doctors")

    return render_template(
        "feedback_form.html", patients=patients, doctors=doctors, action="Add"
    )


@app.route("/feedback/edit/<int:id>", methods=["GET", "POST"])
def edit_feedback(id):
    if request.method == "POST":
        patient_id = request.form["patient_id"]
        doctor_id = request.form["doctor_id"]
        rating = request.form["rating"]
        comments = request.form["comments"]

        sql = """UPDATE Feedback 
                SET PatientID=?, DoctorID=?, Rating=?, Comments=? 
                WHERE FeedbackID=?"""
        success, message = execute_query(
            sql, (patient_id, doctor_id, rating, comments, id)
        )

        if success:
            flash("Feedback updated successfully!", "success")
            return redirect(url_for("feedback"))
        else:
            flash(f"Error: {message}", "danger")

    feedback_item = get_by_id("Feedback", "FeedbackID", id)
    if feedback_item:
        # Get list of patients and doctors for dropdowns
        patients = query("SELECT PatientID, Name FROM Patients")
        doctors = query("SELECT DoctorID, Name FROM Doctors")

        return render_template(
            "feedback_form.html",
            feedback=feedback_item,
            patients=patients,
            doctors=doctors,
            action="Edit",
        )

    flash("Feedback not found", "danger")
    return redirect(url_for("feedback"))


@app.route("/feedback/delete/<int:id>")
def delete_feedback(id):
    sql = "DELETE FROM Feedback WHERE FeedbackID=?"
    success, message = execute_query(sql, (id,))

    if success:
        flash("Feedback deleted successfully!", "success")
    else:
        flash(f"Error: {message}", "danger")

    return redirect(url_for("feedback"))


@app.route("/book_appointment", methods=["GET", "POST"])
@login_required
def book_appointment():
    # Only patients can book appointments
    if session.get("role") != ROLE_PATIENT:
        flash("Only patients can book appointments", "danger")
        return redirect(url_for("index"))

    patient_id = session.get("patient_id")

    if request.method == "POST":
        doctor_id = request.form["doctor_id"]
        date = request.form["date"]
        time = request.form["time"]

        # Combine date and time into datetime format
        datetime_val = f"{date} {time}"
        status = "Scheduled"

        # Check if doctor is available at the selected time
        doctor = get_by_id("Doctors", "DoctorID", doctor_id)
        if not doctor:
            flash("Doctor not found", "danger")
            return render_template("book_appointment.html", doctors=doctors)

        # Check if doctor already has an appointment at this time
        existing_appointment = query(
            """
            SELECT COUNT(*) FROM Appointments 
            WHERE DoctorID = ? AND DateTime = ? AND Status != 'Cancelled'
        """,
            (doctor_id, datetime_val),
        )[0][0]

        if existing_appointment > 0:
            flash(
                "The doctor is not available at this time. Please choose another time.",
                "warning",
            )
            doctors = query(
                "SELECT DoctorID, Name, Specialty, Availability FROM Doctors"
            )
            return render_template("book_appointment.html", doctors=doctors)

        sql = """INSERT INTO Appointments (PatientID, DoctorID, DateTime, Status) 
                VALUES (?, ?, ?, ?)"""
        success, message = execute_query(
            sql, (patient_id, doctor_id, datetime_val, status)
        )

        if success:
            flash("Appointment booked successfully!", "success")
            return redirect(url_for("appointments"))
        else:
            flash(f"Error: {message}", "danger")

    # Get list of doctors
    doctors = query("SELECT DoctorID, Name, Specialty, Availability FROM Doctors")
    return render_template("book_appointment.html", doctors=doctors)


@app.route("/patient_dashboard")
@login_required
def patient_dashboard():
    if session.get("role") != ROLE_PATIENT:
        flash("Access denied", "danger")
        return redirect(url_for("index"))

    patient_id = session.get("patient_id")
    patient = get_by_id("Patients", "PatientID", patient_id)

    # Get appointments with doctor information
    appointments = query(
        """
        SELECT a.*, d.Name as DoctorName 
        FROM Appointments a 
        JOIN Doctors d ON a.DoctorID = d.DoctorID 
        WHERE a.PatientID = ? 
        ORDER BY a.DateTime DESC
        """,
        (patient_id,),
    )

    # Get prescriptions
    prescriptions = query(
        """
        SELECT p.*, d.Name as DoctorName 
        FROM Prescriptions p 
        JOIN Doctors d ON p.DoctorID = d.DoctorID 
        WHERE p.PatientID = ? 
        ORDER BY p.DateIssued DESC
        """,
        (patient_id,),
    )

    # Get bills
    bills = query(
        "SELECT * FROM Bills WHERE PatientID = ? ORDER BY CreatedAt DESC", (patient_id,)
    )

    # Create dictionary of doctor names for easier lookup
    doctors_dict = {}
    doctors = query("SELECT DoctorID, Name FROM Doctors")
    for doctor in doctors:
        doctors_dict[doctor[0]] = doctor[1]

    return render_template(
        "patient_dashboard.html",
        patient=patient,
        appointments=appointments,
        prescriptions=prescriptions,
        bills=bills,
        doctors_dict=doctors_dict,
    )


@app.route("/doctor_dashboard")
@login_required
def doctor_dashboard():
    if session.get("role") != ROLE_DOCTOR:
        flash("Access denied", "danger")
        return redirect(url_for("index"))

    doctor_id = session.get("doctor_id")
    doctor = get_by_id("Doctors", "DoctorID", doctor_id)

    # Today's appointments - include all appointments for today, including cancelled ones for display
    today_appointments = query(
        """
        SELECT a.*, p.Name as PatientName 
        FROM Appointments a 
        JOIN Patients p ON a.PatientID = p.PatientID 
        WHERE a.DoctorID = ? AND CAST(a.DateTime AS DATE) = CAST(GETDATE() AS DATE) 
        ORDER BY a.DateTime
        """,
        (doctor_id,),
    )

    # Upcoming appointments - only include scheduled future appointments
    upcoming_appointments = query(
        """
        SELECT a.*, p.Name as PatientName 
        FROM Appointments a 
        JOIN Patients p ON a.PatientID = p.PatientID 
        WHERE a.DoctorID = ? 
        AND a.DateTime > GETDATE() 
        AND a.Status = 'Scheduled'
        AND a.Status = 'Scheduled'
        ORDER BY a.DateTime
        """,
        (doctor_id,),
    )

    # Count only active (non-cancelled) appointments for statistics
    active_today_count = sum(1 for appt in today_appointments if appt[4] != "Cancelled")
    active_upcoming_count = sum(
        1 for appt in upcoming_appointments if appt[4] != "Cancelled"
    )

    # Recent patients - only count patients with active appointments
    # Modified to fix SQL error - either include MAX(a.DateTime) in SELECT or remove DISTINCT
    recent_patients = query(
        """
        SELECT p.PatientID, p.Name, p.DOB, p.Gender, p.Contact, p.Address, p.UserID
        FROM Patients p 
        JOIN Appointments a ON p.PatientID = a.PatientID 
        WHERE a.DoctorID = ? AND a.Status != 'Cancelled'
        GROUP BY p.PatientID, p.Name, p.DOB, p.Gender, p.Contact, p.Address, p.UserID
        ORDER BY MAX(a.DateTime) DESC
        """,
        (doctor_id,),
    )

    return render_template(
        "doctor_dashboard.html",
        doctor=doctor,
        today_appointments=today_appointments,
        upcoming_appointments=upcoming_appointments,
        recent_patients=recent_patients,
        active_today_count=active_today_count,
        active_upcoming_count=active_upcoming_count,
    )


# User management routes (admin only)
@app.route("/admin/users")
@admin_required
def admin_users():
    # Get all users with role information
    users = query(
        """
        SELECT u.UserID, u.Username, r.RoleName, u.CreatedAt, u.LastLogin,
            CASE 
                WHEN r.RoleName = 'Doctor' THEN (SELECT DoctorID FROM Doctors WHERE UserID = u.UserID)
                WHEN r.RoleName = 'Patient' THEN (SELECT PatientID FROM Patients WHERE UserID = u.UserID)
                ELSE NULL
            END as EntityID
        FROM Users u
        JOIN Roles r ON u.RoleID = r.RoleID
        ORDER BY r.RoleName, u.Username
    """
    )

    # Get available roles for adding new users
    roles = query("SELECT * FROM Roles ORDER BY RoleName")

    return render_template("admin/users.html", users=users, roles=roles)


@app.route("/admin/users/add", methods=["GET", "POST"])
@admin_required
def admin_add_user():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role_id = request.form["role_id"]

        # Check if username is available
        existing_user = query("SELECT * FROM Users WHERE Username = ?", (username,))
        if existing_user:
            flash("Username already taken", "danger")
            roles = query("SELECT * FROM Roles ORDER BY RoleName")
            return render_template("admin/user_form.html", roles=roles, action="Add")

        # Insert user
        sql = "INSERT INTO Users (Username, Password, RoleID) VALUES (?, ?, ?)"
        success, message = execute_query(sql, (username, password, role_id))

        if success:
            flash("User added successfully", "success")

            # Get the new user's ID
            new_user_id = query(
                "SELECT UserID FROM Users WHERE Username = ?", (username,)
            )[0][0]

            # Get the role name to determine if additional information is needed
            role_name = query(
                "SELECT RoleName FROM Roles WHERE RoleID = ?", (role_id,)
            )[0][0]

            if role_name == "Doctor":
                # Redirect to add doctor details
                return redirect(url_for("admin_add_doctor", user_id=new_user_id))
            elif role_name == "Patient":
                # Redirect to add patient details
                return redirect(url_for("admin_add_patient", user_id=new_user_id))
            elif role_name in ["Receptionist", "Nurse"]:
                # Redirect to add staff details
                return redirect(
                    url_for("admin_add_staff", user_id=new_user_id, role=role_name)
                )

            return redirect(url_for("admin_users"))
        else:
            flash(f"Error: {message}", "danger")

    # Get all roles
    roles = query("SELECT * FROM Roles ORDER BY RoleName")

    return render_template("admin/user_form.html", roles=roles, action="Add")


@app.route("/admin/users/edit/<int:id>", methods=["GET", "POST"])
@admin_required
def admin_edit_user(id):
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role_id = request.form["role_id"]

        # Check if username is already taken by another user
        existing_user = query(
            "SELECT UserID FROM Users WHERE Username = ? AND UserID != ?",
            (username, id),
        )
        if existing_user:
            flash("Username already taken by another user", "danger")
            roles = query("SELECT * FROM Roles ORDER BY RoleName")
            user = get_by_id("Users", "UserID", id)
            return render_template(
                "admin/user_form.html", user=user, roles=roles, action="Edit"
            )

        # Update user
        if password:
            # If password is provided, update it
            sql = "UPDATE Users SET Username = ?, Password = ?, RoleID = ? WHERE UserID = ?"
            success, message = execute_query(sql, (username, password, role_id, id))
        else:
            # If no password provided, don't update it
            sql = "UPDATE Users SET Username = ?, RoleID = ? WHERE UserID = ?"
            success, message = execute_query(sql, (username, role_id, id))

        if success:
            flash("User updated successfully", "success")
            return redirect(url_for("admin_users"))
        else:
            flash(f"Error: {message}", "danger")

    # Get the user and all roles
    user = get_by_id("Users", "UserID", id)
    roles = query("SELECT * FROM Roles ORDER BY RoleName")

    if user:
        return render_template(
            "admin/user_form.html", user=user, roles=roles, action="Edit"
        )

    flash("User not found", "danger")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/delete/<int:id>")
@admin_required
def admin_delete_user(id):
    # Check if this is the only admin account
    user_role = query(
        "SELECT r.RoleName FROM Users u JOIN Roles r ON u.RoleID = r.RoleID WHERE u.UserID = ?",
        (id,),
    )

    if user_role and user_role[0][0] == "Admin":
        admin_count = query(
            "SELECT COUNT(*) FROM Users u JOIN Roles r ON u.RoleID = r.RoleID WHERE r.RoleName = 'Admin'"
        )[0][0]
        if admin_count <= 1:
            flash("Cannot delete the only admin account", "danger")
            return redirect(url_for("admin_users"))

    # Delete related records based on role
    if user_role:
        role_name = user_role[0][0]
        if role_name == "Doctor":
            # Update the UserID to NULL in the Doctors table
            execute_query("UPDATE Doctors SET UserID = NULL WHERE UserID = ?", (id,))
        elif role_name == "Patient":
            # Update the UserID to NULL in the Patients table
            execute_query("UPDATE Patients SET UserID = NULL WHERE UserID = ?", (id,))
        elif role_name in ["Receptionist", "Nurse"]:
            # Update the UserID to NULL in the Staff table
            execute_query("UPDATE Staff SET UserID = NULL WHERE UserID = ?", (id,))

    # Delete the user
    success, message = execute_query("DELETE FROM Users WHERE UserID = ?", (id,))

    if success:
        flash("User deleted successfully", "success")
    else:
        flash(f"Error: {message}", "danger")

    return redirect(url_for("admin_users"))


@app.route("/admin/add_doctor/<int:user_id>", methods=["GET", "POST"])
@admin_required
def admin_add_doctor(user_id):
    # First check if this user exists and has doctor role
    user_role = query(
        """
        SELECT u.Username, r.RoleName 
        FROM Users u 
        JOIN Roles r ON u.RoleID = r.RoleID 
        WHERE u.UserID = ?
    """,
        (user_id,),
    )

    if not user_role or user_role[0][1] != "Doctor":
        flash("Invalid user ID or user is not a doctor", "danger")
        return redirect(url_for("admin_users"))

    username = user_role[0][0]

    if request.method == "POST":
        name = request.form["name"]
        specialty = request.form["specialty"]
        availability = request.form["availability"]

        sql = """INSERT INTO Doctors (Name, Specialty, Availability, UserID) 
                VALUES (?, ?, ?, ?)"""
        success, message = execute_query(sql, (name, specialty, availability, user_id))

        if success:
            flash("Doctor profile created successfully", "success")
            return redirect(url_for("admin_users"))
        else:
            flash(f"Error: {message}", "danger")

    return render_template(
        "admin/doctor_form.html", username=username, user_id=user_id, action="Create"
    )


@app.route("/admin/add_patient/<int:user_id>", methods=["GET", "POST"])
@admin_required
def admin_add_patient(user_id):
    # First check if this user exists and has patient role
    user_role = query(
        """
        SELECT u.Username, r.RoleName 
        FROM Users u 
        JOIN Roles r ON u.RoleID = r.RoleID 
        WHERE u.UserID = ?
    """,
        (user_id,),
    )

    if not user_role or user_role[0][1] != "Patient":
        flash("Invalid user ID or user is not a patient", "danger")
        return redirect(url_for("admin_users"))

    username = user_role[0][0]

    if request.method == "POST":
        name = request.form["name"]
        dob = request.form["dob"]
        gender = request.form["gender"]
        contact = request.form["contact"]
        address = request.form["address"]
        medical_history = request.form.get("medical_history", "")

        sql = """INSERT INTO Patients (Name, DOB, Gender, Contact, Address, MedicalHistory, UserID) 
                VALUES (?, ?, ?, ?, ?, ?, ?)"""
        success, message = execute_query(
            sql, (name, dob, gender, contact, address, medical_history, user_id)
        )

        if success:
            flash("Patient profile created successfully", "success")
            return redirect(url_for("admin_users"))
        else:
            flash(f"Error: {message}", "danger")

    return render_template(
        "admin/patient_form.html", username=username, user_id=user_id, action="Create"
    )


@app.route("/admin/add_staff/<int:user_id>", methods=["GET", "POST"])
@admin_required
def admin_add_staff(user_id):
    # Get the role parameter
    role = request.args.get("role", "")

    # First check if this user exists and has appropriate role
    user_role = query(
        """
        SELECT u.Username, r.RoleName 
        FROM Users u 
        JOIN Roles r ON u.RoleID = r.RoleID 
        WHERE u.UserID = ?
    """,
        (user_id,),
    )

    if not user_role or user_role[0][1] not in ["Receptionist", "Nurse"]:
        flash("Invalid user ID or user does not have a staff role", "danger")
        return redirect(url_for("admin_users"))

    username = user_role[0][0]

    if request.method == "POST":
        name = request.form["name"]
        contact = request.form["contact"]
        staff_role = request.form["role"]

        sql = "INSERT INTO Staff (Name, Role, Contact, UserID) VALUES (?, ?, ?, ?)"
        success, message = execute_query(sql, (name, staff_role, contact, user_id))

        if success:
            flash("Staff profile created successfully", "success")
            return redirect(url_for("admin_users"))
        else:
            flash(f"Error: {message}", "danger")

    return render_template(
        "admin/staff_form.html",
        username=username,
        user_id=user_id,
        role=role,
        action="Create",
    )


@app.route("/appointments/complete/<int:id>", methods=["GET", "POST"])
@doctor_required
def complete_appointment(id):
    # Get the appointment details
    appointment = get_by_id("Appointments", "AppointmentID", id)

    if not appointment:
        flash("Appointment not found", "danger")
        return redirect(url_for("appointments"))

    # Check if the appointment is for this doctor
    if appointment[2] != session.get("doctor_id"):
        flash("You can only complete your own appointments", "danger")
        return redirect(url_for("appointments"))

    # Check if appointment is already completed or cancelled
    if appointment[4] != "Scheduled":
        flash("Only scheduled appointments can be completed", "danger")
        return redirect(url_for("appointments"))

    # Get patient info
    patient = get_by_id("Patients", "PatientID", appointment[1])

    if request.method == "POST":
        # Update appointment status to completed
        notes = request.form.get("notes", "")

        update_sql = """
            UPDATE Appointments 
            SET Status = 'Completed', Notes = ? 
            WHERE AppointmentID = ?
        """
        success, message = execute_query(update_sql, (notes, id))

        if not success:
            flash(f"Error completing appointment: {message}", "danger")
            return redirect(url_for("appointments"))

        # Check if we need to create a bill
        if "create_bill" in request.form and request.form["create_bill"] == "yes":
            amount = request.form["amount"]
            description = request.form["description"]

            bill_sql = """
                INSERT INTO Bills (PatientID, Amount, Status, Description, CreatedAt) 
                VALUES (?, ?, 'Unpaid', ?, GETDATE())
            """
            bill_success, bill_message = execute_query(
                bill_sql, (appointment[1], amount, description)
            )

            if bill_success:
                flash("Appointment completed and bill created successfully", "success")
            else:
                flash(
                    f"Appointment completed but error creating bill: {bill_message}",
                    "warning",
                )
        else:
            flash("Appointment completed successfully", "success")

        # Check if we need to create a prescription
        if (
            "create_prescription" in request.form
            and request.form["create_prescription"] == "yes"
        ):
            medication = request.form["medication"]
            dosage = request.form["dosage"]
            valid_days = int(request.form.get("valid_days", 30))

            # Calculate valid until date
            prescription_sql = """
                INSERT INTO Prescriptions (PatientID, DoctorID, Medication, Dosage, DateIssued, ValidUntil) 
                VALUES (?, ?, ?, ?, GETDATE(), DATEADD(day, ?, GETDATE()))
            """
            prescription_success, prescription_message = execute_query(
                prescription_sql,
                (
                    appointment[1],
                    session.get("doctor_id"),
                    medication,
                    dosage,
                    valid_days,
                ),
            )

            if prescription_success:
                flash("Prescription created successfully", "success")
            else:
                flash(f"Error creating prescription: {prescription_message}", "warning")

        return redirect(url_for("appointments"))

    # Get available medications for prescription
    medications = query("SELECT * FROM PharmacyInventory WHERE Stock > 0 ORDER BY Name")

    return render_template(
        "complete_appointment.html",
        appointment=appointment,
        patient=patient,
        medications=medications,
    )


if __name__ == "__main__":
    app.run(debug=True)
