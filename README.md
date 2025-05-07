# 🌟 ModernHospital: Your All-in-One Healthcare Companion 🏥

ModernHospital is a powerful yet easy-to-use web application designed to simplify healthcare operations. Whether you're an administrator, doctor, or patient, this app has everything you need to make healthcare management seamless and efficient. Built with Python (Flask) and SQL Server, ModernHospital is here to revolutionize the way healthcare works! 🚀

## ✨ Features

### 👥 User Roles and Access
- **Admins**: Manage users, billing, and reports effortlessly.
- **Doctors**: Handle appointments, view patient details, and issue prescriptions.
- **Patients**: Book appointments, view prescriptions, and track your medical history.
- **Staff**: Take care of room assignments, emergency cases, and more.

### 🏥 Core Functionalities
- **📋 Patient Management**: Register and manage patient profiles with ease.
- **👨‍⚕️ Doctor Management**: Keep track of doctor profiles, specialties, and availability.
- **📅 Appointment Scheduling**: Book, edit, and manage appointments in just a few clicks.
- **💳 Billing System**: Generate and manage bills effortlessly.
- **💊 Pharmacy Inventory**: Monitor medication stock and manage prescriptions.
- **🛏️ Room Management**: Assign and track room usage efficiently.
- **🧪 Lab Reports**: Add and view lab test results.
- **🛡️ Insurance Claims**: Manage patient insurance details and claims.
- **🚨 Emergency Cases**: Record and handle emergencies quickly.

### 🌟 Additional Perks
- **⭐ Feedback System**: Collect and manage feedback from patients.
- **📊 Role-Based Dashboards**: Tailored views for admins, doctors, and patients.
- **🔒 Secure Authentication**: Role-based access control to keep your data safe.

## 🚀 Getting Started

### Prerequisites
- Python 3.8 or higher 🐍
- SQL Server 🗄️
- Windows OS (recommended) 💻

### Installation Steps
1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd ModernHospital
   ```
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Set up the database**:
   - Create a database in SQL Server.
   - Run the `hospital.sql` script to initialize the schema.
   - Update the `conn_str` in `app.py` with your database connection details.
4. **Start the application**:
   ```bash
   python app.py
   ```
5. **Access the app**:
   Open your browser and navigate to `http://127.0.0.1:5000` 🌐.

## 📂 Folder Structure
- **app.py**: Main application file.
- **hospital.sql**: Database schema.
- **static/**: Contains static files like CSS.
- **templates/**: HTML templates for the frontend.
- **templates/admin/**: Admin-specific templates.

## 🙌 Acknowledgments
- Flask Framework: [Flask](https://flask.palletsprojects.com/)
- SQL Server: [Microsoft SQL Server](https://www.microsoft.com/en-us/sql-server)

---

ModernHospital: Making healthcare simple, efficient, and accessible for everyone! ❤️
